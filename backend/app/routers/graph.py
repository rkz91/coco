"""Knowledge Graph API — serves graphify data from graph.json."""
import json
import logging
import os
import threading
from collections import defaultdict, deque
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

from app.config import GRAPHIFY_GRAPH_PATH

log = logging.getLogger(__name__)
router = APIRouter(tags=["Graph"])

# ---------------------------------------------------------------------------
# In-memory graph store (loaded once, reloaded on file change)
# ---------------------------------------------------------------------------

_graph_lock = threading.Lock()
_graph_data: dict | None = None
_graph_mtime: float = 0.0


def _load_graph() -> dict | None:
    """Load graph.json into memory. Returns parsed dict or None."""
    global _graph_data, _graph_mtime

    if not GRAPHIFY_GRAPH_PATH.exists():
        log.debug("graph.json not found at %s", GRAPHIFY_GRAPH_PATH)
        return None

    mtime = os.path.getmtime(GRAPHIFY_GRAPH_PATH)
    with _graph_lock:
        if _graph_data is not None and mtime == _graph_mtime:
            return _graph_data

    try:
        raw = GRAPHIFY_GRAPH_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        # Build lookup indexes
        nodes = data.get("nodes", [])
        edges = data.get("links", []) or data.get("edges", [])

        node_index = {}
        for n in nodes:
            node_index[n["id"]] = n

        # Adjacency list
        adj: dict[str, list[dict]] = defaultdict(list)
        for e in edges:
            adj[e["source"]].append(e)
            adj[e["target"]].append(e)

        # Community index
        communities: dict[int, list[str]] = defaultdict(list)
        for n in nodes:
            cid = n.get("community")
            if cid is not None:
                communities[cid].append(n["id"])

        with _graph_lock:
            _graph_data = {
                "nodes": nodes,
                "edges": edges,
                "node_index": node_index,
                "adj": dict(adj),
                "communities": dict(communities),
                "mtime": mtime,
            }
            _graph_mtime = mtime
            log.info("graph_loaded", nodes=len(nodes), edges=len(edges),
                     communities=len(communities))
            return _graph_data

    except Exception as exc:
        log.error("graph_load_error: %s", exc)
        return None


def _get_graph():
    """Get graph data, loading if needed. Raises 503 if unavailable."""
    g = _load_graph()
    if g is None:
        raise HTTPException(503, "Graph data not available. Run graphify rebuild first.")
    return g


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/graph/stats")
def graph_stats():
    """Graph summary: node/edge/community counts, last build time."""
    g = _get_graph()
    type_counts: dict[str, int] = defaultdict(int)
    for n in g["nodes"]:
        type_counts[n.get("meta_type", "unknown")] += 1

    return {
        "available": True,
        "nodes": len(g["nodes"]),
        "edges": len(g["edges"]),
        "communities": len(g["communities"]),
        "last_built": g["mtime"],
        "node_types": dict(type_counts),
    }


@router.get("/api/graph/god-nodes")
def god_nodes(top_n: int = Query(20, ge=1, le=100)):
    """Most connected nodes (hubs) in the graph."""
    g = _get_graph()
    adj = g["adj"]
    node_index = g["node_index"]

    # Sort by degree
    degrees = [(nid, len(edges)) for nid, edges in adj.items()]
    degrees.sort(key=lambda x: x[1], reverse=True)

    results = []
    for nid, degree in degrees[:top_n]:
        node = node_index.get(nid, {})
        results.append({
            "id": nid,
            "label": node.get("label", nid),
            "meta_type": node.get("meta_type", "unknown"),
            "community": node.get("community"),
            "degree": degree,
            "meta_projects": node.get("meta_projects", ""),
        })
    return {"items": results}


@router.get("/api/graph/nodes")
def list_nodes(
    meta_type: str | None = None,
    community: int | None = None,
    project: str | None = None,
    min_degree: int = Query(0, ge=0),
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated node listing with filters."""
    g = _get_graph()
    adj = g["adj"]
    filtered = g["nodes"]

    if meta_type:
        filtered = [n for n in filtered if n.get("meta_type") == meta_type]
    if community is not None:
        filtered = [n for n in filtered if n.get("community") == community]
    if project:
        filtered = [n for n in filtered
                    if project in (n.get("meta_projects", "") or "")
                    or n.get("meta_project") == project]
    if min_degree > 0:
        filtered = [n for n in filtered if len(adj.get(n["id"], [])) >= min_degree]
    if q:
        ql = q.lower()
        filtered = [n for n in filtered if ql in (n.get("label", "") or "").lower()]

    total = len(filtered)
    page = filtered[offset:offset + limit]

    items = []
    for n in page:
        items.append({
            "id": n["id"],
            "label": n.get("label", n["id"]),
            "meta_type": n.get("meta_type", "unknown"),
            "community": n.get("community"),
            "degree": len(adj.get(n["id"], [])),
            "meta_project": n.get("meta_project", ""),
            "meta_projects": n.get("meta_projects", ""),
        })

    return {"items": items, "total": total}


@router.get("/api/graph/node/{node_id:path}")
def get_node(node_id: str):
    """Full node details + neighbors + edges."""
    g = _get_graph()
    node = g["node_index"].get(node_id)
    if not node:
        raise HTTPException(404, f"Node '{node_id}' not found")

    edges = g["adj"].get(node_id, [])
    neighbors = []
    for e in edges:
        neighbor_id = e["target"] if e["source"] == node_id else e["source"]
        neighbor = g["node_index"].get(neighbor_id, {})
        neighbors.append({
            "id": neighbor_id,
            "label": neighbor.get("label", neighbor_id),
            "meta_type": neighbor.get("meta_type", "unknown"),
            "relation": e.get("relation", "related"),
            "confidence": e.get("confidence", "EXTRACTED"),
        })

    return {
        **node,
        "degree": len(edges),
        "neighbors": neighbors,
    }


@router.get("/api/graph/communities")
def list_communities(limit: int = Query(50, ge=1, le=200)):
    """Community list with member counts and top members."""
    g = _get_graph()
    node_index = g["node_index"]
    adj = g["adj"]

    items = []
    for cid, member_ids in sorted(g["communities"].items(), key=lambda x: len(x[1]), reverse=True)[:limit]:
        # Top 5 members by degree
        members_with_degree = [
            (mid, len(adj.get(mid, []))) for mid in member_ids
        ]
        members_with_degree.sort(key=lambda x: x[1], reverse=True)
        top_members = [
            {"id": mid, "label": node_index.get(mid, {}).get("label", mid), "degree": deg}
            for mid, deg in members_with_degree[:5]
        ]

        items.append({
            "id": cid,
            "size": len(member_ids),
            "top_members": top_members,
        })

    return {"items": items, "total": len(g["communities"])}


@router.get("/api/graph/community/{community_id}")
def get_community(community_id: int, limit: int = Query(200, ge=1, le=1000)):
    """All nodes and internal edges for a community."""
    g = _get_graph()
    member_ids = g["communities"].get(community_id)
    if member_ids is None:
        raise HTTPException(404, f"Community {community_id} not found")

    member_set = set(member_ids)
    nodes = [g["node_index"][mid] for mid in member_ids[:limit] if mid in g["node_index"]]

    # Internal edges only
    edges = []
    seen = set()
    for mid in member_ids[:limit]:
        for e in g["adj"].get(mid, []):
            other = e["target"] if e["source"] == mid else e["source"]
            if other in member_set:
                edge_key = (min(e["source"], e["target"]), max(e["source"], e["target"]))
                if edge_key not in seen:
                    seen.add(edge_key)
                    edges.append(e)

    return {"community_id": community_id, "nodes": nodes, "edges": edges, "total_members": len(member_ids)}


@router.get("/api/graph/path")
def shortest_path(
    source: str = Query(..., description="Source node ID or label substring"),
    target: str = Query(..., description="Target node ID or label substring"),
    max_hops: int = Query(6, ge=1, le=10),
):
    """BFS shortest path between two nodes."""
    g = _get_graph()
    node_index = g["node_index"]
    adj = g["adj"]

    def _resolve(q: str) -> str | None:
        if q in node_index:
            return q
        ql = q.lower()
        for nid, node in node_index.items():
            if ql in (node.get("label", "") or "").lower():
                return nid
        return None

    src = _resolve(source)
    tgt = _resolve(target)
    if not src:
        raise HTTPException(404, f"Source node '{source}' not found")
    if not tgt:
        raise HTTPException(404, f"Target node '{target}' not found")

    # BFS
    visited = {src}
    queue = [(src, [src])]
    while queue:
        current, path = queue.pop(0)
        if current == tgt:
            path_nodes = [node_index.get(nid, {"id": nid}) for nid in path]
            return {"path": path_nodes, "hops": len(path) - 1}
        if len(path) > max_hops:
            continue
        for e in adj.get(current, []):
            neighbor = e["target"] if e["source"] == current else e["source"]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return {"path": [], "hops": -1, "message": f"No path found within {max_hops} hops"}


@router.get("/api/graph/subgraph")
def get_subgraph(
    center: str = Query(..., description="Center node ID or label"),
    depth: int = Query(1, ge=1, le=3),
    max_nodes: int = Query(100, ge=10, le=500),
):
    """BFS subgraph extraction around a center node.

    Resolves center by ID or label substring, then performs BFS up to *depth*
    hops.  When more nodes are reachable than *max_nodes*, higher-degree nodes
    are kept preferentially.  Only internal edges (both endpoints in the result
    set) are returned.
    """
    g = _get_graph()
    node_index = g["node_index"]
    adj = g["adj"]

    # --- resolve center node ---
    center_id: str | None = None
    if center in node_index:
        center_id = center
    else:
        cl = center.lower()
        for nid, node in node_index.items():
            if cl in (node.get("label", "") or "").lower():
                center_id = nid
                break
    if center_id is None:
        raise HTTPException(404, f"Center node '{center}' not found")

    # --- BFS up to depth hops ---
    visited: dict[str, int] = {center_id: 0}  # node_id -> hop distance
    queue: deque[tuple[str, int]] = deque([(center_id, 0)])
    while queue:
        current, d = queue.popleft()
        if d >= depth:
            continue
        for e in adj.get(current, []):
            neighbor = e["target"] if e["source"] == current else e["source"]
            if neighbor not in visited:
                visited[neighbor] = d + 1
                queue.append((neighbor, d + 1))

    # --- cap at max_nodes, prioritizing higher-degree nodes ---
    truncated = len(visited) > max_nodes
    if truncated:
        # Always keep center; rank the rest by degree descending
        others = [(nid, len(adj.get(nid, []))) for nid in visited if nid != center_id]
        others.sort(key=lambda x: x[1], reverse=True)
        keep = {center_id}
        for nid, _deg in others[: max_nodes - 1]:
            keep.add(nid)
    else:
        keep = set(visited.keys())

    # --- build response nodes ---
    nodes = []
    for nid in keep:
        node = node_index.get(nid, {})
        nodes.append({
            "id": nid,
            "label": node.get("label", nid),
            "meta_type": node.get("meta_type", "unknown"),
            "community": node.get("community"),
            "degree": len(adj.get(nid, [])),
            "hop": visited[nid],
        })

    # --- internal edges only (both endpoints in keep) ---
    edges = []
    seen_edges: set[tuple[str, str]] = set()
    for nid in keep:
        for e in adj.get(nid, []):
            other = e["target"] if e["source"] == nid else e["source"]
            if other in keep:
                edge_key = (min(e["source"], e["target"]), max(e["source"], e["target"]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(e)

    return {
        "nodes": nodes,
        "edges": edges,
        "center": center_id,
        "truncated": truncated,
    }


@router.get("/api/graph/collapsed")
def collapsed_view(limit: int = Query(43, ge=1, le=100)):
    """Community-collapsed view — one super-node per community.

    Returns aggregated inter-community edges with cross-edge counts so the
    frontend can render a high-level community map without loading every node.
    """
    g = _get_graph()
    node_index = g["node_index"]
    adj = g["adj"]
    communities = g["communities"]

    # --- build super-nodes (one per community, top member as representative) ---
    # Sort communities by size descending, take up to limit
    sorted_cids = sorted(communities.keys(), key=lambda c: len(communities[c]), reverse=True)[:limit]
    cid_set = set(sorted_cids)

    # Map each node to its community for edge aggregation
    node_to_community: dict[str, int] = {}
    for cid in sorted_cids:
        for nid in communities[cid]:
            node_to_community[nid] = cid

    super_nodes = []
    for cid in sorted_cids:
        member_ids = communities[cid]
        # Top member by degree
        top_member = max(member_ids, key=lambda nid: len(adj.get(nid, [])))
        top_label = node_index.get(top_member, {}).get("label", top_member)
        super_nodes.append({
            "id": f"community_{cid}",
            "label": top_label,
            "community": cid,
            "size": len(member_ids),
            "meta_type": "community",
        })

    # --- aggregate inter-community edges ---
    edge_counts: dict[tuple[int, int], int] = defaultdict(int)
    seen_raw: set[tuple[str, str]] = set()
    for e in g["edges"]:
        src, tgt = e["source"], e["target"]
        src_c = node_to_community.get(src)
        tgt_c = node_to_community.get(tgt)
        if src_c is None or tgt_c is None:
            continue
        if src_c == tgt_c:
            continue  # internal edge, skip
        # Deduplicate raw edges
        raw_key = (min(src, tgt), max(src, tgt))
        if raw_key in seen_raw:
            continue
        seen_raw.add(raw_key)
        edge_key = (min(src_c, tgt_c), max(src_c, tgt_c))
        edge_counts[edge_key] += 1

    super_edges = [
        {
            "source": f"community_{c1}",
            "target": f"community_{c2}",
            "weight": count,
        }
        for (c1, c2), count in sorted(edge_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "nodes": super_nodes,
        "edges": super_edges,
        "total_communities": len(communities),
    }

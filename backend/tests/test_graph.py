"""Tests for the graph router (app.routers.graph)."""
import pytest
from collections import defaultdict
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixture graph data (raw, as it would appear in graph.json)
# ---------------------------------------------------------------------------

FIXTURE_GRAPH = {
    "nodes": [
        {"id": "person_alice", "label": "Alice", "meta_type": "person", "community": 0},
        {"id": "person_bob", "label": "Bob", "meta_type": "person", "community": 0},
        {"id": "project_x", "label": "Project X", "meta_type": "project", "community": 1},
        {"id": "team_eng", "label": "Engineering", "meta_type": "team", "community": 1},
    ],
    "links": [
        {"source": "person_alice", "target": "project_x", "relation": "works_on", "confidence": "EXTRACTED"},
        {"source": "person_bob", "target": "project_x", "relation": "works_on", "confidence": "EXTRACTED"},
        {"source": "person_alice", "target": "person_bob", "relation": "collaborates", "confidence": "INFERRED"},
        {"source": "team_eng", "target": "project_x", "relation": "owns", "confidence": "EXTRACTED"},
    ],
}


def _build_graph_data(raw: dict) -> dict:
    """Mimic what _load_graph builds internally — indexes, adjacency, communities."""
    nodes = raw["nodes"]
    edges = raw.get("links", []) or raw.get("edges", [])

    node_index = {n["id"]: n for n in nodes}

    adj: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        adj[e["source"]].append(e)
        adj[e["target"]].append(e)

    communities: dict[int, list[str]] = defaultdict(list)
    for n in nodes:
        cid = n.get("community")
        if cid is not None:
            communities[cid].append(n["id"])

    return {
        "nodes": nodes,
        "edges": edges,
        "node_index": node_index,
        "adj": dict(adj),
        "communities": dict(communities),
        "mtime": 1700000000.0,
    }


BUILT_GRAPH = _build_graph_data(FIXTURE_GRAPH)


def _make_test_app() -> FastAPI:
    """Lightweight FastAPI app with only the graph router — no lifespan overhead."""
    test_app = FastAPI()
    from app.routers.graph import router
    test_app.include_router(router)
    return test_app


@pytest.fixture()
def client():
    """TestClient with _load_graph patched to return the fixture graph."""
    with patch("app.routers.graph._load_graph", return_value=BUILT_GRAPH):
        app = _make_test_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/graph/stats
# ---------------------------------------------------------------------------

class TestGraphStats:
    def test_returns_counts(self, client):
        resp = client.get("/api/graph/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["nodes"] == 4
        assert data["edges"] == 4
        assert data["communities"] == 2
        assert data["last_built"] == 1700000000.0

    def test_node_type_breakdown(self, client):
        resp = client.get("/api/graph/stats")
        types = resp.json()["node_types"]
        assert types["person"] == 2
        assert types["project"] == 1
        assert types["team"] == 1


# ---------------------------------------------------------------------------
# GET /api/graph/god-nodes
# ---------------------------------------------------------------------------

class TestGodNodes:
    def test_returns_sorted_by_degree(self, client):
        resp = client.get("/api/graph/god-nodes")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        # degrees should be non-increasing
        degrees = [i["degree"] for i in items]
        assert degrees == sorted(degrees, reverse=True)

    def test_top_node_is_project_x(self, client):
        """project_x appears in 3 edges (alice, bob, team_eng) so degree=3."""
        resp = client.get("/api/graph/god-nodes?top_n=1")
        item = resp.json()["items"][0]
        assert item["id"] == "project_x"
        assert item["degree"] == 3

    def test_top_n_limits(self, client):
        resp = client.get("/api/graph/god-nodes?top_n=2")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

    def test_includes_expected_fields(self, client):
        resp = client.get("/api/graph/god-nodes?top_n=1")
        item = resp.json()["items"][0]
        assert "id" in item
        assert "label" in item
        assert "meta_type" in item
        assert "degree" in item


# ---------------------------------------------------------------------------
# GET /api/graph/nodes
# ---------------------------------------------------------------------------

class TestListNodes:
    def test_filter_by_meta_type(self, client):
        resp = client.get("/api/graph/nodes?meta_type=person")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["meta_type"] == "person"

    def test_filter_by_community(self, client):
        resp = client.get("/api/graph/nodes?community=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # project_x and team_eng
        ids = {i["id"] for i in data["items"]}
        assert ids == {"project_x", "team_eng"}

    def test_search_by_label(self, client):
        resp = client.get("/api/graph/nodes?q=alice")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["id"] == "person_alice"

    def test_returns_all_without_filter(self, client):
        resp = client.get("/api/graph/nodes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    def test_pagination(self, client):
        resp = client.get("/api/graph/nodes?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 2

        resp2 = client.get("/api/graph/nodes?limit=2&offset=2")
        data2 = resp2.json()
        assert len(data2["items"]) == 2
        # No overlap
        ids1 = {i["id"] for i in data["items"]}
        ids2 = {i["id"] for i in data2["items"]}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# GET /api/graph/node/{node_id}
# ---------------------------------------------------------------------------

class TestGetNode:
    def test_returns_node_with_neighbors(self, client):
        resp = client.get("/api/graph/node/person_alice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "person_alice"
        assert data["label"] == "Alice"
        assert data["meta_type"] == "person"
        assert "neighbors" in data
        # person_alice is source in 2 edges: works_on(project_x), collaborates(bob)
        assert data["degree"] == 2
        neighbor_ids = {n["id"] for n in data["neighbors"]}
        assert neighbor_ids == {"project_x", "person_bob"}

    def test_node_with_high_degree(self, client):
        resp = client.get("/api/graph/node/project_x")
        assert resp.status_code == 200
        data = resp.json()
        assert data["degree"] == 3  # alice, bob, team_eng all link to project_x

    def test_not_found(self, client):
        resp = client.get("/api/graph/node/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/graph/communities
# ---------------------------------------------------------------------------

class TestCommunities:
    def test_returns_community_list(self, client):
        resp = client.get("/api/graph/communities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        items = data["items"]
        assert len(items) == 2
        # Each community has id, size, top_members
        for item in items:
            assert "id" in item
            assert "size" in item
            assert "top_members" in item
            assert isinstance(item["top_members"], list)

    def test_community_sizes(self, client):
        resp = client.get("/api/graph/communities")
        items = resp.json()["items"]
        sizes = {i["id"]: i["size"] for i in items}
        assert sizes[0] == 2  # person_alice, person_bob
        assert sizes[1] == 2  # project_x, team_eng


# ---------------------------------------------------------------------------
# GET /api/graph/path
# ---------------------------------------------------------------------------

class TestShortestPath:
    def test_finds_direct_path(self, client):
        # Alice -> Project X is a direct edge
        resp = client.get("/api/graph/path?source=Alice&target=Project X")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hops"] == 1
        assert len(data["path"]) == 2

    def test_finds_path_via_intermediate(self, client):
        # Alice -> Engineering: Alice -> project_x -> team_eng (2 hops)
        resp = client.get("/api/graph/path?source=Alice&target=Engineering")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hops"] == 2
        assert len(data["path"]) == 3

    def test_source_not_found_404(self, client):
        resp = client.get("/api/graph/path?source=nonexistent&target=Alice")
        assert resp.status_code == 404

    def test_target_not_found_404(self, client):
        resp = client.get("/api/graph/path?source=Alice&target=nonexistent")
        assert resp.status_code == 404

    def test_resolves_by_label_substring(self, client):
        # "Eng" should match "Engineering"
        resp = client.get("/api/graph/path?source=Alice&target=Eng")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hops"] >= 1


# ---------------------------------------------------------------------------
# Graph unavailable (503)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /api/graph/subgraph
# ---------------------------------------------------------------------------

class TestSubgraph:
    def test_center_by_id(self, client):
        resp = client.get("/api/graph/subgraph?center=person_alice&depth=1&max_nodes=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center"] == "person_alice"
        assert any(n["id"] == "person_alice" for n in data["nodes"])
        assert "edges" in data

    def test_center_by_label(self, client):
        resp = client.get("/api/graph/subgraph?center=Alice&depth=1&max_nodes=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center"] == "person_alice"

    def test_depth_expansion(self, client):
        """depth=2 from Alice should reach Engineering (Alice->project_x->team_eng)."""
        resp_d1 = client.get("/api/graph/subgraph?center=person_alice&depth=1&max_nodes=50")
        resp_d2 = client.get("/api/graph/subgraph?center=person_alice&depth=2&max_nodes=50")
        assert resp_d1.status_code == 200
        assert resp_d2.status_code == 200
        nodes_d1 = {n["id"] for n in resp_d1.json()["nodes"]}
        nodes_d2 = {n["id"] for n in resp_d2.json()["nodes"]}
        # depth=2 should include at least as many nodes as depth=1
        assert nodes_d1.issubset(nodes_d2)
        # team_eng is 2 hops from Alice; should appear at depth=2
        assert "team_eng" in nodes_d2

    def test_max_nodes_cap(self, client):
        """With max_nodes=10 (minimum), result should not exceed that count."""
        resp = client.get("/api/graph/subgraph?center=project_x&depth=3&max_nodes=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) <= 10

    def test_center_not_found(self, client):
        resp = client.get("/api/graph/subgraph?center=nonexistent&depth=1&max_nodes=50")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/graph/collapsed
# ---------------------------------------------------------------------------

class TestCollapsed:
    def test_returns_community_super_nodes(self, client):
        resp = client.get("/api/graph/collapsed")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "total_communities" in data
        # Should have super-nodes with meta_type "community"
        for node in data["nodes"]:
            assert node["meta_type"] == "community"
            assert "size" in node
            assert node["id"].startswith("community_")

    def test_inter_community_edges(self, client):
        """There should be inter-community edges between community 0 and 1.

        In the fixture graph, person_alice (community 0) -> project_x (community 1)
        and person_bob (community 0) -> project_x (community 1), so there
        should be at least one inter-community edge with weight >= 1.
        """
        resp = client.get("/api/graph/collapsed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["edges"]) >= 1
        for edge in data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "weight" in edge
            assert edge["weight"] >= 1

    def test_limit_param(self, client):
        resp = client.get("/api/graph/collapsed?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        # Should have at most 1 super-node
        assert len(data["nodes"]) <= 1


# ---------------------------------------------------------------------------
# Graph unavailable (503)
# ---------------------------------------------------------------------------

class TestGraphUnavailable:
    def test_stats_503_when_no_graph(self):
        with patch("app.routers.graph._load_graph", return_value=None):
            app = _make_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/graph/stats")
                assert resp.status_code == 503

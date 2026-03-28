"""CoCo Platform MCP Server — HTTP-based, zero app imports.

This server has NO imports from the FastAPI application. It connects to
the running Platform backend over HTTP (localhost:3001) and reads/writes
local CoCo files (~/.coco/) directly.

If the backend is not running, HTTP-based tools return a clear error.
Local tools (brain, queue, config, sessions) always work.

This design ensures that code changes to the FastAPI app can NEVER break
the MCP server. The only dependency is that the backend is running.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PLATFORM_URL = os.environ.get("COCO_PLATFORM_URL", "http://localhost:3001")
COCO_DIR = Path.home() / ".coco"
BRAIN_JSON = COCO_DIR / "brain.json"
QUEUE_JSON = COCO_DIR / "queue.json"
CONFIG_JSON = COCO_DIR / "config.json"
SESSIONS_DIR = COCO_DIR / "sessions"

_client = httpx.Client(base_url=PLATFORM_URL, timeout=15.0)

mcp = FastMCP(
    "coco-platform",
    instructions="CoCo Platform — PM control plane. 22 tools for dashboard, todos, decisions, brain, YOLO autonomy, and verification.",
)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _api(method: str, path: str, **kwargs) -> dict:
    """Call the Platform REST API. Returns JSON or error dict."""
    try:
        resp = _client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        return {
            "error": "CoCo Platform backend not running.",
            "fix": "Start with: cd ~/projects/coco-platform && scripts/dev.sh",
        }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:300]}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Local file helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    """Read a JSON file. Returns {} if missing or corrupt."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    """Atomic write: write to .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.rename(path)


# ===================================================================
# HTTP TOOLS — call the Platform backend REST API
# ===================================================================


@mcp.tool()
def coco_activate() -> dict:
    """Get the full CoCo dashboard: greeting, projects, todos, health, attention, costs, queue.

    Call this at the start of a session to see the complete picture.
    """
    return _api("GET", "/api/home")


@mcp.tool()
def coco_briefing() -> dict:
    """Get a smart briefing: what changed since last session, key items, action items due."""
    return _api("GET", "/api/home/briefing")


@mcp.tool()
def coco_status() -> dict:
    """Compact status: project count, health indicators, attention items, costs. Lighter than activate."""
    home = _api("GET", "/api/home")
    if "error" in home:
        return home
    return {
        "projects_active": len([p for p in home.get("projects", []) if p.get("active")]),
        "todos_open": home.get("todos", {}).get("total_open", 0),
        "health": home.get("health", []),
        "attention": home.get("attention", {}),
        "costs": home.get("costs", {}),
    }


@mcp.tool()
def coco_search(query: str, project: str | None = None) -> dict:
    """Search across todos, agents, tasks, goals, and content.

    Args:
        query: Search text (substring match on titles).
        project: Optional project_id to filter results.
    """
    params = {"q": query, "limit": 20}
    if project:
        params["project"] = project
    return _api("GET", "/api/search", params=params)


@mcp.tool()
def coco_health() -> dict:
    """System health: backend uptime, database status, adapter sync status (email/voice/jira/confluence)."""
    return _api("GET", "/api/health")


@mcp.tool()
def coco_cost(days: int = 30) -> dict:
    """Cost summary: total spend, breakdown by model and project, daily average.

    Args:
        days: Number of days to look back. Default: 30.
    """
    return _api("GET", "/api/costs/summary", params={"days": days})


@mcp.tool()
def coco_process() -> dict:
    """Trigger the Knowledge Hub ingest + process pipeline. Pulls new emails, voice memos, Jira, Confluence."""
    return _api("POST", "/api/home/process")


@mcp.tool()
def coco_context(project: str) -> dict:
    """Get project collaboration context: shared docs, handoffs, active workflow.

    Args:
        project: The node_id (project/team ID) to get context for.
    """
    return _api("GET", f"/api/collaboration/context/{project}")


@mcp.tool()
def coco_approve(draft_id: str) -> dict:
    """Approve a Knowledge Hub draft.

    Args:
        draft_id: The UUID of the draft to approve.
    """
    return _api("POST", f"/api/drafts/{draft_id}/approve")


@mcp.tool()
def coco_reject(draft_id: str, reason: str | None = None) -> dict:
    """Reject a Knowledge Hub draft.

    Args:
        draft_id: The UUID of the draft to reject.
        reason: Optional reason for rejection.
    """
    body = {}
    if reason:
        body["reason"] = reason
    return _api("POST", f"/api/drafts/{draft_id}/reject", json=body)


@mcp.tool()
def coco_todo_list(status: str = "open", project: str | None = None) -> dict:
    """List todos filtered by status and optional project.

    Args:
        status: Filter: 'open', 'done', 'jira-created', 'dismissed', 'all'. Default: 'open'.
        project: Optional project slug to filter by.
    """
    params = {"status": status, "limit": 50}
    if project:
        params["project"] = project
    return _api("GET", "/api/todos", params=params)


@mcp.tool()
def coco_todo_add(title: str, project: str | None = None, priority: str = "medium") -> dict:
    """Add a new todo.

    Args:
        title: Todo title.
        project: Optional project slug.
        priority: 'high', 'medium', or 'low'. Default: 'medium'.
    """
    body = {"title": title, "priority": priority, "source_type": "manual"}
    if project:
        body["project_id"] = project
    return _api("POST", "/api/todos", json=body)


@mcp.tool()
def coco_todo_done(todo_id: str) -> dict:
    """Mark a todo as done.

    Args:
        todo_id: The todo UUID to complete.
    """
    return _api("PATCH", f"/api/todos/{todo_id}/transition", json={"to_status": "done"})


@mcp.tool()
def coco_verify(workflow_id: str | None = None) -> dict:
    """Run verification gates on the active workflow. Returns gate results (PASS/FAIL/WARN).

    Args:
        workflow_id: Optional workflow ID. If omitted, verifies the most recent active workflow.
    """
    if workflow_id:
        return _api("POST", f"/api/workflows/{workflow_id}/verify")
    return {"error": "No workflow_id provided. Pass the active workflow ID to verify."}


# ===================================================================
# LOCAL TOOLS — read/write CoCo files directly (no backend needed)
# ===================================================================


@mcp.tool()
def coco_session_log() -> dict:
    """Read the most recent CoCo session log. Returns start time, launch type, commands used."""
    try:
        if not SESSIONS_DIR.exists():
            return {"error": "No sessions directory."}
        files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return {"error": "No session files found."}
        return {"file": files[0].name, **_read_json(files[0])}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def coco_decide(item_index: int | None = None, action: str | None = None) -> dict:
    """List decision queue items, or act on one.

    Without arguments: returns all pending queue items.
    With item_index + action: applies 'approve', 'reject', 'defer', or 'dismiss'.

    Args:
        item_index: 0-based index of the queue item.
        action: One of 'approve', 'reject', 'defer', 'dismiss'.
    """
    data = _read_json(QUEUE_JSON)
    items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    if item_index is None:
        return {"items": items, "total": len(items)}

    if item_index < 0 or item_index >= len(items):
        return {"error": f"Invalid index {item_index}. Queue has {len(items)} items."}
    if action not in ("approve", "reject", "defer", "dismiss"):
        return {"error": f"Invalid action '{action}'. Use: approve, reject, defer, dismiss."}

    target = items[item_index]
    target["status"] = f"{action}d" if action != "dismiss" else "dismissed"

    if action in ("defer", "dismiss"):
        items = [i for idx, i in enumerate(items) if idx != item_index]
        if action == "defer" and isinstance(data, dict):
            data.setdefault("deferred", []).append(target)

    if isinstance(data, dict):
        data["items"] = items
    else:
        data = items

    _write_json(QUEUE_JSON, data)
    return {"action": action, "item": target, "remaining": len(items)}


@mcp.tool()
def coco_teach(fact: str) -> dict:
    """Teach CoCo a fact about a person, project, or routing rule.

    Examples: 'Chris is my manager', 'Priya works on Reg COE', 'ACC meets Tuesdays 2pm'.

    Args:
        fact: Natural language fact to learn.
    """
    brain = _read_json(BRAIN_JSON)
    brain.setdefault("people", {})
    brain.setdefault("attention_rules", [])
    brain.setdefault("preferences", {})
    brain.setdefault("stats", {"rules_learned": 0})

    # Simple NLP: detect "X is my Y" or "X works on Y" patterns
    fact_lower = fact.lower().strip()
    result = {"fact": fact, "learned": False, "message": ""}

    # Pattern: "{name} is my {role}"
    for pattern in ["is my ", "is a ", "is the "]:
        if pattern in fact_lower:
            parts = fact_lower.split(pattern, 1)
            name = parts[0].strip().title()
            role = parts[1].strip().rstrip(".")
            slug = name.lower().replace(" ", "_")
            brain["people"][slug] = {
                "full_name": name,
                "role": role,
                "priority": "high" if role in ("manager", "lead", "director", "vp") else "normal",
                "projects": brain["people"].get(slug, {}).get("projects", []),
                "learned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "source": "taught",
            }
            brain["stats"]["rules_learned"] = brain["stats"].get("rules_learned", 0) + 1
            result.update({"learned": True, "message": f"Learned: {name} is {role} (priority: {'high' if role in ('manager', 'lead', 'director', 'vp') else 'normal'})."})
            break

    # Pattern: "{name} works on {project}"
    if not result["learned"] and "works on " in fact_lower:
        parts = fact_lower.split("works on ", 1)
        name = parts[0].strip().title()
        project = parts[1].strip().rstrip(".")
        slug = name.lower().replace(" ", "_")
        person = brain["people"].get(slug, {
            "full_name": name, "role": "collaborator", "priority": "normal",
            "projects": [], "learned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "source": "taught",
        })
        if project not in person.get("projects", []):
            person.setdefault("projects", []).append(project)
        brain["people"][slug] = person
        brain["stats"]["rules_learned"] = brain["stats"].get("rules_learned", 0) + 1
        result.update({"learned": True, "message": f"Learned: {name} works on {project}."})

    # Fallback: store as preference
    if not result["learned"]:
        brain["preferences"].setdefault("custom_rules", []).append({
            "rule": fact, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        brain["stats"]["rules_learned"] = brain["stats"].get("rules_learned", 0) + 1
        result.update({"learned": True, "message": f"Learned: '{fact}' (stored as custom rule)."})

    _write_json(BRAIN_JSON, brain)
    return result


@mcp.tool()
def coco_forget(person: str) -> dict:
    """Remove a person from CoCo's brain.

    Args:
        person: Name of the person to forget (case-insensitive).
    """
    brain = _read_json(BRAIN_JSON)
    people = brain.get("people", {})
    slug = person.lower().replace(" ", "_")

    if slug not in people:
        matches = [k for k in people if person.lower() in k]
        if not matches:
            return {"error": f"No person named '{person}' found.", "known": list(people.keys())}
        slug = matches[0]

    removed = people.pop(slug)
    # Also remove attention rules referencing this person
    rules = brain.get("attention_rules", [])
    brain["attention_rules"] = [r for r in rules if r.get("match", {}).get("value") != slug]
    brain["people"] = people

    _write_json(BRAIN_JSON, brain)
    return {"forgotten": slug, "full_name": removed.get("full_name", slug)}


@mcp.tool()
def coco_people() -> dict:
    """List all people in CoCo's brain with their roles, projects, and priority."""
    brain = _read_json(BRAIN_JSON)
    people = brain.get("people", {})
    rules = brain.get("attention_rules", [])

    entries = []
    for slug, data in sorted(people.items(), key=lambda x: (0 if x[1].get("priority") == "high" else 1, x[0])):
        entries.append({
            "slug": slug,
            "full_name": data.get("full_name", slug.title()),
            "role": data.get("role", "unknown"),
            "priority": data.get("priority", "normal"),
            "projects": data.get("projects", []),
            "source": data.get("source", "unknown"),
            "learned_at": data.get("learned_at"),
        })

    return {"people": entries, "total": len(entries), "attention_rules": len(rules)}


@mcp.tool()
def coco_yolo_activate(
    profile: str = "full",
    duration_minutes: int | None = None,
    project: str | None = None,
) -> dict:
    """Activate YOLO mode — full autonomy for CoCo actions.

    Args:
        profile: 'full' (max auto), 'code-only' (only code actions), 'comms-safe' (no external comms). Default: 'full'.
        duration_minutes: Optional auto-expire in minutes.
        project: Optional project scope.
    """
    config = _read_json(CONFIG_JSON)
    config["autonomy_mode"] = "yolo"
    config.setdefault("yolo", {})
    config["yolo"]["profile"] = profile
    config["yolo"]["duration_minutes"] = duration_minutes
    config["yolo"]["project_scope"] = project

    _write_json(CONFIG_JSON, config)

    msg = f"YOLO mode activated (profile={profile})."
    if duration_minutes:
        msg += f" Expires in {duration_minutes}m."
    if project:
        msg += f" Scoped to: {project}."
    return {"mode": "yolo", "profile": profile, "duration_minutes": duration_minutes, "project_scope": project, "message": msg}


@mcp.tool()
def coco_yolo_classify(action: str, context: str = "") -> dict:
    """Classify an action as safe or escalate based on YOLO rules.

    Args:
        action: Action description (e.g., 'send email', 'refactor utils.py').
        context: Additional context (project, agent role).
    """
    config = _read_json(CONFIG_JSON)
    mode = config.get("autonomy_mode", "normal")

    if mode != "yolo":
        return {"classification": "escalate", "reason": f"Mode is '{mode}', not YOLO. All actions need approval."}

    profile = config.get("yolo", {}).get("profile", "full")
    action_lower = action.lower()

    # Always escalate dangerous actions
    for kw in ("delete", "deploy to prod", "payment", "billing", "credential", "secret", "password"):
        if kw in action_lower:
            return {"classification": "escalate", "reason": f"Safety keyword '{kw}' — always requires approval."}

    if profile == "full":
        return {"classification": "safe", "reason": "Full YOLO — approved."}
    elif profile == "code-only":
        is_code = any(kw in action_lower for kw in ("code", "refactor", "test", "fix", "implement", "build", "commit"))
        return {"classification": "safe" if is_code else "escalate", "reason": "Code action." if is_code else "Non-code — needs approval."}
    elif profile == "comms-safe":
        is_comms = any(kw in action_lower for kw in ("email", "slack", "message", "notify", "send", "publish"))
        return {"classification": "escalate" if is_comms else "safe", "reason": "Comms need approval." if is_comms else "Non-comms — approved."}

    return {"classification": "safe", "reason": f"Unknown profile '{profile}' — defaulting safe."}


@mcp.tool()
def coco_mode(mode: str) -> dict:
    """Set CoCo's autonomy mode.

    Args:
        mode: 'yolo' (full autonomy), 'careful' (ask everything), 'normal' (balanced).
    """
    if mode not in ("yolo", "careful", "normal"):
        return {"error": f"Invalid mode '{mode}'. Must be: yolo, careful, normal."}

    config = _read_json(CONFIG_JSON)
    old = config.get("autonomy_mode", "normal")
    config["autonomy_mode"] = mode
    _write_json(CONFIG_JSON, config)
    return {"mode": mode, "previous": old, "message": f"Mode changed: {old} → {mode}."}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

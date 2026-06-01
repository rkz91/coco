"""Content-to-Action Pipeline service.

Two extraction modes:
  - regex: fast, free pattern matching for TODO/Action/Follow-up items
  - llm:   structured extraction via Claude Haiku (costs tokens)

Extracted items are staged in the `staged_actions` table.
YOLO mode auto-creates todos; Careful mode stages for human review.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, insert, update, text

from app.db.session import get_db
from app.db.tables import staged_actions, hub_content
from app.services.event_bus import event_bus

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Regex patterns for action extraction
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("todo", re.compile(
        r"(?:^|\n)\s*(?:TODO|TO-DO|TO DO)\s*[:\-]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )),
    ("todo", re.compile(
        r"(?:^|\n)\s*(?:Action(?:\s+item)?)\s*[:\-]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )),
    ("follow_up", re.compile(
        r"(?:^|\n)\s*(?:Follow[\s\-]?up)\s*[:\-]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )),
    ("todo", re.compile(
        r"@(\w+)\s+should\s+(.+?)(?:\.|;|\n|$)",
        re.IGNORECASE,
    )),
    ("todo", re.compile(
        r"(?:^|\n)\s*[\-\*]\s*\[[\s]*\]\s+(.+?)(?:\n|$)",
        re.IGNORECASE,
    )),
    ("decision", re.compile(
        r"(?:^|\n)\s*(?:Decision|Decided)\s*[:\-]\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )),
]

# Deadline patterns
_DEADLINE_RE = re.compile(
    r"(?:by|before|due|deadline)\s+"
    r"(\d{4}[\-/]\d{1,2}[\-/]\d{1,2}|"
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"[^.;]*)",
    re.IGNORECASE,
)

# Assignee patterns like "@name" or "assigned to NAME"
_ASSIGNEE_RE = re.compile(
    r"(?:@(\w+)|(?:assign(?:ed)?\s+to)\s+(\w[\w\s]{0,30}))",
    re.IGNORECASE,
)

# Priority keywords
_PRIORITY_KEYWORDS = {
    "urgent": "high",
    "critical": "high",
    "asap": "high",
    "important": "high",
    "high priority": "high",
    "low priority": "low",
    "nice to have": "low",
    "optional": "low",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _extract_deadline(text: str) -> str | None:
    m = _DEADLINE_RE.search(text)
    if m:
        raw = m.group(1).strip()
        # Try to parse YYYY-MM-DD style
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return raw  # Return as-is if we can't parse
    return None


def _extract_assignee(text: str) -> str | None:
    m = _ASSIGNEE_RE.search(text)
    if m:
        return (m.group(1) or m.group(2) or "").strip() or None
    return None


def _extract_priority(text: str) -> str:
    lower = text.lower()
    for keyword, priority in _PRIORITY_KEYWORDS.items():
        if keyword in lower:
            return priority
    return "medium"


# ---------------------------------------------------------------------------
# Regex extraction
# ---------------------------------------------------------------------------

def _regex_extract(content_text: str) -> list[dict]:
    """Extract action items using regex patterns. Returns list of raw dicts."""
    results: list[dict] = []
    seen_titles: set[str] = set()

    for action_type, pattern in _PATTERNS:
        for match in pattern.finditer(content_text):
            groups = match.groups()

            # Handle @name should ... pattern (2 groups)
            if len(groups) == 2 and action_type == "todo":
                assignee = groups[0]
                title = groups[1].strip()
            else:
                title = groups[0].strip() if groups[0] else ""
                assignee = _extract_assignee(title)

            if not title or len(title) < 5:
                continue

            # Dedupe by normalized title
            norm = title.lower().strip()
            if norm in seen_titles:
                continue
            seen_titles.add(norm)

            # Extract a surrounding context window as source quote
            start = max(0, match.start() - 50)
            end = min(len(content_text), match.end() + 50)
            source_quote = content_text[start:end].strip()

            results.append({
                "action_type": action_type,
                "title": title[:200],
                "description": title,
                "assignee": assignee,
                "due_date": _extract_deadline(title) or _extract_deadline(source_quote),
                "priority": _extract_priority(title),
                "source_quote": source_quote[:500],
                "confidence": 0.6,  # regex = moderate confidence
            })

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_content(content_id: str, mode: str = "regex") -> list[dict]:
    """Process a single content item and stage extracted actions.

    Returns list of staged action dicts.
    """
    with get_db() as conn:
        row = conn.execute(
            select(hub_content.c.id, hub_content.c.title, hub_content.c.body, hub_content.c.summary)
            .where(hub_content.c.id == content_id)
        ).fetchone()

    if not row:
        log.warning("action_pipeline_content_not_found", content_id=content_id)
        return []

    # row._mapping is keyed by the real column names (raw_text/processed_text),
    # not the .c.body/.c.summary key aliases — accept either so extraction
    # actually receives the content. (Reading .get("body") alone always
    # returned "" and silently produced zero actions.)
    m = row._mapping
    content_text = (
        m.get("body") or m.get("raw_text")
        or m.get("summary") or m.get("processed_text") or ""
    )
    if not content_text.strip():
        return []

    # Extract actions
    if mode == "regex":
        extracted = _regex_extract(content_text)
    else:
        # LLM mode placeholder -- falls back to regex for now
        log.info("action_pipeline_llm_mode_not_yet_implemented_falling_back_to_regex")
        extracted = _regex_extract(content_text)

    if not extracted:
        return []

    # Stage the actions
    now = _iso_now()
    staged: list[dict] = []

    with get_db() as conn:
        for item in extracted:
            action_id = str(uuid.uuid4())
            values = {
                "id": action_id,
                "content_id": content_id,
                "action_type": item["action_type"],
                "title": item["title"],
                "description": item.get("description"),
                "assignee": item.get("assignee"),
                "due_date": item.get("due_date"),
                "priority": item.get("priority", "medium"),
                "source_quote": item.get("source_quote"),
                "confidence": item.get("confidence", 0.5),
                "status": "staged",
                "created_at": now,
            }
            conn.execute(insert(staged_actions).values(**values))
            staged.append(values)

    event_bus.emit("actions.processed", {
        "content_id": content_id,
        "mode": mode,
        "count": len(staged),
    })
    return staged


def process_batch(limit: int = 20, mode: str = "regex") -> dict:
    """Process unprocessed content items in batch.

    Finds hub_content items that don't yet have staged_actions rows.
    Returns summary dict.
    """
    with get_db() as conn:
        # Find content IDs that already have staged actions
        already_processed = set()
        rows = conn.execute(
            select(staged_actions.c.content_id).distinct()
        ).fetchall()
        already_processed = {r.content_id for r in rows}

        # Get unprocessed content
        content_rows = conn.execute(
            select(hub_content.c.id)
            .where(hub_content.c.body.isnot(None))
            .order_by(hub_content.c.created_at.desc())
            .limit(limit + len(already_processed))
        ).fetchall()

    processed = 0
    total_actions = 0

    for row in content_rows:
        cid = row.id
        if cid in already_processed:
            continue
        if processed >= limit:
            break

        actions = process_content(cid, mode=mode)
        total_actions += len(actions)
        processed += 1

    return {
        "processed": processed,
        "actions_staged": total_actions,
        "mode": mode,
    }


def approve_action(action_id: str) -> dict | None:
    """Approve a staged action: create a todo and mark as approved."""
    with get_db() as conn:
        row = conn.execute(
            select(staged_actions).where(staged_actions.c.id == action_id)
        ).fetchone()

    if not row:
        return None

    action = dict(row._mapping)
    if action["status"] != "staged":
        return action  # Already processed

    # Create a todo via direct insert (same pattern as POST /api/todos)
    todo_id = str(uuid.uuid4())
    now = _iso_now()

    with get_db() as conn:
        conn.execute(
            text(
                "INSERT INTO todo_overrides "
                "(hub_todo_id, title, priority, owner, due_date, status, "
                "source_type, source_content_id, is_platform_native, created_at, updated_at) "
                "VALUES (:id, :title, :priority, :owner, :due_date, 'open', "
                "'action_pipeline', :content_id, 1, :now, :now)"
            ),
            {
                "id": todo_id,
                "title": action["title"],
                "priority": action.get("priority", "medium"),
                "owner": action.get("assignee"),
                "due_date": action.get("due_date"),
                "content_id": action["content_id"],
                "now": now,
            },
        )

    # Update staged action status
    with get_db() as conn:
        conn.execute(
            update(staged_actions)
            .where(staged_actions.c.id == action_id)
            .values(status="approved", created_todo_id=todo_id)
        )

    event_bus.emit("actions.approved", {
        "action_id": action_id,
        "todo_id": todo_id,
        "title": action["title"],
    })
    event_bus.emit("todo.created", {"id": todo_id, "title": action["title"]})

    action["status"] = "approved"
    action["created_todo_id"] = todo_id
    return action


def reject_action(action_id: str) -> dict | None:
    """Reject a staged action."""
    now = _iso_now()

    with get_db() as conn:
        row = conn.execute(
            select(staged_actions).where(staged_actions.c.id == action_id)
        ).fetchone()

    if not row:
        return None

    action = dict(row._mapping)
    if action["status"] != "staged":
        return action

    with get_db() as conn:
        conn.execute(
            update(staged_actions)
            .where(staged_actions.c.id == action_id)
            .values(status="rejected")
        )

    event_bus.emit("actions.rejected", {"action_id": action_id, "title": action["title"]})
    action["status"] = "rejected"
    return action


def approve_all() -> dict:
    """YOLO: approve all staged actions at once."""
    with get_db() as conn:
        rows = conn.execute(
            select(staged_actions).where(staged_actions.c.status == "staged")
        ).fetchall()

    approved = 0
    failed = 0
    for row in rows:
        try:
            result = approve_action(row.id)
            if result and result.get("status") == "approved":
                approved += 1
            else:
                failed += 1
        except Exception as e:
            log.warning("approve_all_failed_item", action_id=row.id, error=str(e))
            failed += 1

    return {"approved": approved, "failed": failed}

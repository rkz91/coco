"""Agent Session Store — persists SDK session state to agent_sessions table.

Maps agent_id to conversation state: message history, token counts, checkpoints.
"""

import json
import uuid
import structlog
from sqlalchemy import insert, select, update, delete

from app.db.session import get_db
from app.db.tables import agent_sessions

log = structlog.get_logger()


def save_session(
    agent_id: str,
    session_data: dict,
) -> dict:
    """Create or replace session for an agent.

    session_data keys:
        conversation_id, model, status, message_count,
        total_input_tokens, total_output_tokens,
        checkpoint_data (dict), messages (list)
    """
    session_id = session_data.get("id") or uuid.uuid4().hex

    checkpoint = session_data.get("checkpoint_data", {})
    if isinstance(checkpoint, dict):
        checkpoint = json.dumps(checkpoint)

    messages = session_data.get("messages", [])
    if isinstance(messages, list):
        messages = json.dumps(messages)

    with get_db() as conn:
        # Upsert: delete old then insert
        conn.execute(
            delete(agent_sessions).where(agent_sessions.c.agent_id == agent_id)
        )
        conn.execute(
            insert(agent_sessions).values(
                id=session_id,
                agent_id=agent_id,
                conversation_id=session_data.get("conversation_id"),
                model=session_data.get("model"),
                status=session_data.get("status", "active"),
                message_count=session_data.get("message_count", 0),
                total_input_tokens=session_data.get("total_input_tokens", 0),
                total_output_tokens=session_data.get("total_output_tokens", 0),
                checkpoint_data=checkpoint,
                messages_json=messages,
            )
        )
        log.info("session_saved", agent_id=agent_id, session_id=session_id)
        return _fetch_session(conn, agent_id)


def get_session(agent_id: str) -> dict | None:
    """Return session metadata for an agent, or None."""
    with get_db() as conn:
        return _fetch_session(conn, agent_id)


def delete_session(agent_id: str) -> bool:
    """Delete session for an agent. Returns True if a row was deleted."""
    with get_db() as conn:
        result = conn.execute(
            delete(agent_sessions).where(agent_sessions.c.agent_id == agent_id)
        )
        deleted = result.rowcount > 0
        if deleted:
            log.info("session_deleted", agent_id=agent_id)
        return deleted


def update_checkpoint(agent_id: str, checkpoint_data: dict) -> dict | None:
    """Update only the checkpoint_data for an agent session."""
    serialized = json.dumps(checkpoint_data)
    with get_db() as conn:
        result = conn.execute(
            update(agent_sessions)
            .where(agent_sessions.c.agent_id == agent_id)
            .values(checkpoint_data=serialized)
        )
        if result.rowcount == 0:
            return None
        log.info("checkpoint_updated", agent_id=agent_id)
        return _fetch_session(conn, agent_id)


def increment_tokens(
    agent_id: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Add token counts to the running session totals and bump message_count."""
    with get_db() as conn:
        row = conn.execute(
            select(
                agent_sessions.c.total_input_tokens,
                agent_sessions.c.total_output_tokens,
                agent_sessions.c.message_count,
            ).where(agent_sessions.c.agent_id == agent_id)
        ).fetchone()
        if not row:
            return
        m = row._mapping
        conn.execute(
            update(agent_sessions)
            .where(agent_sessions.c.agent_id == agent_id)
            .values(
                total_input_tokens=m["total_input_tokens"] + input_tokens,
                total_output_tokens=m["total_output_tokens"] + output_tokens,
                message_count=m["message_count"] + 1,
            )
        )


def update_status(agent_id: str, status: str) -> None:
    """Set session status (active / paused / completed / failed)."""
    with get_db() as conn:
        conn.execute(
            update(agent_sessions)
            .where(agent_sessions.c.agent_id == agent_id)
            .values(status=status)
        )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _fetch_session(conn, agent_id: str) -> dict | None:
    row = conn.execute(
        select(
            agent_sessions.c.id,
            agent_sessions.c.agent_id,
            agent_sessions.c.conversation_id,
            agent_sessions.c.model,
            agent_sessions.c.status,
            agent_sessions.c.message_count,
            agent_sessions.c.total_input_tokens,
            agent_sessions.c.total_output_tokens,
            agent_sessions.c.checkpoint_data,
            agent_sessions.c.messages_json,
            agent_sessions.c.created_at,
            agent_sessions.c.updated_at,
        ).where(agent_sessions.c.agent_id == agent_id)
    ).fetchone()
    if not row:
        return None
    d = dict(row._mapping)
    # Deserialize JSON fields
    try:
        d["checkpoint_data"] = json.loads(d["checkpoint_data"] or "{}")
    except (json.JSONDecodeError, TypeError):
        d["checkpoint_data"] = {}
    try:
        d["messages"] = json.loads(d["messages_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        d["messages"] = []
    d.pop("messages_json", None)
    return d

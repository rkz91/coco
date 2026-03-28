"""Content-to-Action Pipeline router.

Endpoints for processing content into action items, reviewing staged
actions, and approving/rejecting them into todos.
"""

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.tables import staged_actions, hub_content
from app.models.actions import ProcessContentBody, ProcessBatchBody
from app.services.action_pipeline import (
    process_content,
    process_batch,
    approve_action,
    reject_action,
    approve_all,
)

log = structlog.get_logger()

router = APIRouter(tags=["Actions"])


@router.post("/api/actions/process")
def api_process_content(body: ProcessContentBody):
    """Process a single content item to extract action items."""
    if body.mode not in ("regex", "llm"):
        raise HTTPException(400, "mode must be 'regex' or 'llm'")

    results = process_content(body.content_id, mode=body.mode)
    return {
        "content_id": body.content_id,
        "mode": body.mode,
        "actions": results,
        "count": len(results),
    }


@router.post("/api/actions/process-batch")
def api_process_batch(body: ProcessBatchBody):
    """Process unprocessed content items in batch."""
    if body.mode not in ("regex", "llm"):
        raise HTTPException(400, "mode must be 'regex' or 'llm'")

    result = process_batch(limit=body.limit, mode=body.mode)
    return result


@router.get("/api/actions/staged")
def api_list_staged(
    status: str = Query("staged", pattern="^(staged|approved|rejected)$"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List staged actions for review."""
    with get_db() as conn:
        query = (
            select(
                staged_actions,
                hub_content.c.title.label("content_title"),
            )
            .outerjoin(hub_content, staged_actions.c.content_id == hub_content.c.id)
            .where(staged_actions.c.status == status)
            .order_by(staged_actions.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = conn.execute(query).fetchall()

        # Get total count
        count_q = (
            select(func.count())
            .select_from(staged_actions)
            .where(staged_actions.c.status == status)
        )
        total = conn.execute(count_q).scalar() or 0

    items = []
    for row in rows:
        d = dict(row._mapping)
        items.append(d)

    return {"items": items, "total": total}


@router.get("/api/actions/stats")
def api_action_stats():
    """Get counts by status for the action pipeline."""
    with get_db() as conn:
        rows = conn.execute(
            select(
                staged_actions.c.status,
                func.count().label("count"),
            )
            .group_by(staged_actions.c.status)
        ).fetchall()

    stats = {r.status: r.count for r in rows}
    return {
        "staged": stats.get("staged", 0),
        "approved": stats.get("approved", 0),
        "rejected": stats.get("rejected", 0),
        "total": sum(stats.values()),
    }


@router.get("/api/actions/{action_id}")
def api_get_action(action_id: str):
    """Get a single staged action by ID."""
    with get_db() as conn:
        row = conn.execute(
            select(
                staged_actions,
                hub_content.c.title.label("content_title"),
            )
            .outerjoin(hub_content, staged_actions.c.content_id == hub_content.c.id)
            .where(staged_actions.c.id == action_id)
        ).fetchone()

    if not row:
        raise HTTPException(404, "Staged action not found")

    return dict(row._mapping)


@router.post("/api/actions/{action_id}/approve")
def api_approve_action(action_id: str):
    """Approve a staged action -- creates a todo and marks it approved."""
    result = approve_action(action_id)
    if not result:
        raise HTTPException(404, "Staged action not found")
    return result


@router.post("/api/actions/{action_id}/reject")
def api_reject_action(action_id: str):
    """Reject a staged action."""
    result = reject_action(action_id)
    if not result:
        raise HTTPException(404, "Staged action not found")
    return result


@router.post("/api/actions/approve-all")
def api_approve_all():
    """YOLO shortcut: approve all staged actions at once."""
    result = approve_all()
    return result

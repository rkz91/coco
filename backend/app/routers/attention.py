"""Attention router — user attention tracking and gap detection."""

import structlog
from fastapi import APIRouter, Query

from app.models.attention import ViewEventBody
from app.services.attention_tracker import attention_tracker

log = structlog.get_logger()

router = APIRouter(tags=["Attention"])


@router.get("/api/attention/scores")
def list_attention_scores():
    """All project attention scores sorted by score descending."""
    scores = attention_tracker.get_all_scores()
    return {"items": scores, "total": len(scores)}


@router.get("/api/attention/gaps")
def list_attention_gaps(days: int = Query(14, ge=1, le=365)):
    """Projects not viewed in the last N days."""
    gaps = attention_tracker.get_attention_gaps(days=days)
    return {"items": gaps, "total": len(gaps)}


@router.post("/api/attention/view")
def log_view_event(body: ViewEventBody):
    """Log a view event for a project."""
    valid_sources = {"knowledge", "graph", "content"}
    if body.source not in valid_sources:
        body.source = "content"

    result = attention_tracker.record_view(
        project_slug=body.project_slug,
        source=body.source,
    )
    return result

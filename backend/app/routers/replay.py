"""Replay router — generate, list, view, share, and delete agent replays."""

import gzip
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.replay import GenerateReplayBody, ReplayResponse, ReplayListResponse
from app.services.replay import replay_service

log = structlog.get_logger()

router = APIRouter(prefix="/api/replays", tags=["Replays"])


@router.get("/", response_model=ReplayListResponse)
def list_replays(agent_id: Optional[str] = None):
    """List all replays, optionally filtered by agent_id."""
    items = replay_service.list_replays(agent_id=agent_id)
    return ReplayListResponse(items=items, count=len(items))


@router.post("/", response_model=ReplayResponse, status_code=201)
def generate_replay(body: GenerateReplayBody):
    """Generate a new replay from an agent's stream-json output."""
    try:
        record = replay_service.generate_replay(body.agent_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        log.error("replay_generation_failed", agent_id=body.agent_id, error=str(e))
        raise HTTPException(500, f"Failed to generate replay: {e}")
    return record


@router.get("/share/{share_token}")
def get_shared_replay(share_token: str):
    """Serve a shared replay HTML file. Public endpoint — no auth."""
    html_path = replay_service.get_shared_replay(share_token)
    if not html_path:
        raise HTTPException(404, "Shared replay not found")

    html_bytes = html_path.read_bytes()

    # Gzip compress the response
    compressed = gzip.compress(html_bytes, compresslevel=6)

    return Response(
        content=compressed,
        media_type="text/html",
        headers={
            "Content-Encoding": "gzip",
            "Cache-Control": "public, max-age=3600",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )


@router.get("/{replay_id}", response_model=ReplayResponse)
def get_replay(replay_id: str):
    """Get a single replay record."""
    record = replay_service.get_replay(replay_id)
    if not record:
        raise HTTPException(404, "Replay not found")
    return record


@router.delete("/{replay_id}")
def delete_replay(replay_id: str):
    """Delete a replay and its HTML file."""
    deleted = replay_service.delete_replay(replay_id)
    if not deleted:
        raise HTTPException(404, "Replay not found")
    return {"status": "deleted", "replay_id": replay_id}

"""Attention Tracker Service — tracks user interactions and surfaces attention gaps.

Listens to event_bus for knowledge page views, graph node clicks, and content
views. Every hour, computes attention scores per project (weighted by recency
over the last 7 days) and stores them in the ``attention_scores`` table in
platform.db.

The service exposes ``get_attention_gaps(days)`` to surface projects that
have not been viewed in N days.

Pattern follows hub_sync.py — start/stop lifecycle with asyncio background loop.
"""

import asyncio
import structlog
from datetime import datetime, timezone

from sqlalchemy import select, insert, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.compat import now, days_ago
from app.db.engine import engine
from app.db.session import get_db
from app.db.tables import attention_scores, attention_events
from app.services.event_bus import event_bus

log = structlog.get_logger()

# Event types we listen for
_TRACKED_EVENTS = {
    "knowledge.page_view",
    "graph.node_click",
    "content.view",
    "attention.view",
}

# Source mapping from event type to source label
_EVENT_SOURCE_MAP = {
    "knowledge.page_view": "knowledge",
    "graph.node_click": "graph",
    "content.view": "content",
    "attention.view": "content",
}


class AttentionTrackerService:
    """Background service that computes per-project attention scores."""

    SCORE_INTERVAL = 3600  # seconds (1 hour)

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the background scoring loop."""
        self._running = True
        log.info("attention_tracker_starting")

        # Register event listener
        self._register_listeners()

        # Initial score computation
        try:
            self._compute_scores()
        except Exception as e:
            log.warning("attention_initial_score_failed", error=str(e))

        # Background loop
        while self._running:
            await asyncio.sleep(self.SCORE_INTERVAL)
            try:
                self._compute_scores()
            except Exception as e:
                log.error("attention_score_compute_failed", error=str(e))

    def stop(self):
        """Stop the background loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        log.info("attention_tracker_stopped")

    # ------------------------------------------------------------------
    # Event listener registration
    # ------------------------------------------------------------------

    def _register_listeners(self):
        """No-op for now — views are logged via the POST endpoint.

        In a future iteration this could subscribe to the event_bus
        async generator to auto-capture views from other services.
        """
        log.info("attention_tracker_listeners_registered")

    # ------------------------------------------------------------------
    # Record a view event
    # ------------------------------------------------------------------

    def record_view(self, project_slug: str, source: str = "content") -> dict:
        """Persist a view event and update the attention score for the project."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        with get_db() as conn:
            # Insert event
            conn.execute(
                insert(attention_events).values(
                    project_slug=project_slug,
                    source=source,
                    viewed_at=ts,
                )
            )

            # Upsert attention_scores: bump view_count + last_viewed_at
            stmt = sqlite_insert(attention_scores).values(
                project_slug=project_slug,
                score=1.0,
                view_count=1,
                last_viewed_at=ts,
                updated_at=ts,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["project_slug"],
                set_={
                    "view_count": attention_scores.c.view_count + 1,
                    "last_viewed_at": ts,
                    "updated_at": ts,
                },
            )
            conn.execute(stmt)

        # Emit event for SSE subscribers
        event_bus.emit("attention.view", {
            "project_slug": project_slug,
            "source": source,
            "viewed_at": ts,
        })

        return {
            "project_slug": project_slug,
            "source": source,
            "viewed_at": ts,
        }

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    def _compute_scores(self):
        """Recompute attention scores for all projects.

        Score = sum of views in the last 7 days, weighted by recency:
          - Views today:       weight 1.0
          - Views 1 day ago:   weight 0.85
          - Views 2 days ago:  weight 0.72
          - ...
          - Views 6 days ago:  weight 0.37
          - Older:             not counted

        Formula: weight = 0.85 ^ days_old
        """
        seven_days_ago = days_ago(7)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        with get_db() as conn:
            # Fetch all view events in the last 7 days
            rows = conn.execute(
                select(
                    attention_events.c.project_slug,
                    attention_events.c.viewed_at,
                ).where(attention_events.c.viewed_at >= seven_days_ago)
            ).fetchall()

            # Group by project and compute weighted scores
            project_scores: dict[str, float] = {}
            project_views: dict[str, int] = {}
            project_last_viewed: dict[str, str] = {}
            now_dt = datetime.now(timezone.utc)

            for row in rows:
                slug = row.project_slug
                viewed_at_str = row.viewed_at

                # Parse timestamp
                try:
                    if viewed_at_str.endswith("Z"):
                        viewed_dt = datetime.fromisoformat(viewed_at_str.replace("Z", "+00:00"))
                    else:
                        viewed_dt = datetime.fromisoformat(viewed_at_str)
                        if viewed_dt.tzinfo is None:
                            viewed_dt = viewed_dt.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    continue

                days_old = (now_dt - viewed_dt).total_seconds() / 86400.0
                weight = 0.85 ** days_old

                project_scores[slug] = project_scores.get(slug, 0.0) + weight
                project_views[slug] = project_views.get(slug, 0) + 1

                # Track most recent view
                if slug not in project_last_viewed or viewed_at_str > project_last_viewed[slug]:
                    project_last_viewed[slug] = viewed_at_str

            # Upsert scores
            for slug, score in project_scores.items():
                stmt = sqlite_insert(attention_scores).values(
                    project_slug=slug,
                    score=round(score, 4),
                    view_count=project_views[slug],
                    last_viewed_at=project_last_viewed.get(slug),
                    updated_at=ts,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["project_slug"],
                    set_={
                        "score": round(score, 4),
                        "view_count": project_views[slug],
                        "last_viewed_at": project_last_viewed.get(slug),
                        "updated_at": ts,
                    },
                )
                conn.execute(stmt)

            # Zero out scores for projects with no recent views
            conn.execute(
                attention_scores.update()
                .where(attention_scores.c.updated_at < ts)
                .values(score=0.0, view_count=0, updated_at=ts)
            )

        log.info(
            "attention_scores_computed",
            projects=len(project_scores),
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_all_scores(self) -> list[dict]:
        """Return all attention scores sorted by score descending."""
        with get_db() as conn:
            rows = conn.execute(
                select(attention_scores).order_by(
                    attention_scores.c.score.desc()
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def get_attention_gaps(self, days: int = 14) -> list[dict]:
        """Return projects not viewed in the last N days.

        This includes:
        1. Projects with a last_viewed_at older than N days ago
        2. Projects with NULL last_viewed_at (never viewed)
        """
        cutoff = days_ago(days)
        with get_db() as conn:
            rows = conn.execute(
                select(attention_scores).where(
                    (attention_scores.c.last_viewed_at < cutoff)
                    | (attention_scores.c.last_viewed_at.is_(None))
                ).order_by(attention_scores.c.last_viewed_at.asc().nullsfirst())
            ).fetchall()
        return [dict(r._mapping) for r in rows]


# Singleton
attention_tracker = AttentionTrackerService()

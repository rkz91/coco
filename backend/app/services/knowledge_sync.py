"""Knowledge Sync Service — polls knowledge.db generation_log and emits SSE events.

The Knowledge Engine cron runs as a separate process (not inside the Platform).
This service bridges the gap by polling generation_log every 60s for new entries
and emitting SSE events so the frontend can auto-refresh.

NOTE: knowledge.db is an EXTERNAL, read-only SQLite database owned by the
Knowledge Engine — it lives outside platform.db and has no tables.py
definitions. We open it via a dedicated SA Core engine in read-only mode and
use ``text()`` for queries (analogous to the FTS5 dialect-isolated pattern in
SPRINT6A_PLAN.md).
"""

import asyncio
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import KNOWLEDGE_DB_PATH
from app.services.event_bus import event_bus

log = structlog.get_logger()


# Module-level cached engine to defeat per-poll engine churn (defeats SA pooling).
# Built lazily on first request; reused for the process lifetime.
_cached_engine: Engine | None = None


def _build_knowledge_engine() -> Engine | None:
    """Return the cached read-only SA engine for the external knowledge.db.

    Returns None if knowledge.db does not exist yet (Knowledge Engine has not
    run). Uses SQLite URI mode=ro so writes are rejected at the driver level.

    The engine is cached at module scope: SA pool reuses connections across
    polls instead of paying per-poll create+dispose overhead.
    """
    global _cached_engine
    if _cached_engine is not None:
        return _cached_engine
    if not KNOWLEDGE_DB_PATH.exists():
        return None
    url = f"sqlite:///file:{KNOWLEDGE_DB_PATH}?mode=ro&uri=true"
    _cached_engine = create_engine(
        url,
        connect_args={"uri": True, "timeout": 10},
        pool_pre_ping=True,
    )
    return _cached_engine


class KnowledgeSyncService:
    """Polls knowledge.db generation_log for new activity, emits SSE events."""

    def __init__(self):
        self._running = False
        self._last_log_id = 0

    async def start(self):
        """Start the polling loop."""
        self._running = True

        # Initialize watermark from current max log ID
        self._last_log_id = self._get_max_log_id()
        log.info("knowledge_sync_started", watermark=self._last_log_id)

        while self._running:
            await asyncio.sleep(60)
            try:
                self._check_for_updates()
            except Exception as exc:
                log.warning("knowledge_sync_poll_error", error=str(exc))

    def stop(self):
        self._running = False
        log.info("knowledge_sync_stopped")

    def _get_engine(self) -> Engine | None:
        return _build_knowledge_engine()

    def _get_max_log_id(self) -> int:
        eng = self._get_engine()
        if eng is None:
            return 0
        try:
            with eng.connect() as conn:
                row = conn.execute(
                    text("SELECT MAX(id) FROM generation_log")
                ).fetchone()
                return (row[0] if row else 0) or 0
        except Exception:
            return 0

    def _check_for_updates(self):
        eng = self._get_engine()
        if eng is None:
            return

        try:
            with eng.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT id, phase, status, articles_generated, "
                        "duration_seconds, run_at "
                        "FROM generation_log "
                        "WHERE id > :last_id AND log_type = 'phase' "
                        "ORDER BY id"
                    ),
                    {"last_id": self._last_log_id},
                ).mappings().all()

                if not rows:
                    return

                for row in rows:
                    self._last_log_id = max(self._last_log_id, row["id"])

                    # Emit SSE event for each completed phase
                    event_bus.emit("knowledge.phase_complete", {
                        "phase": row["phase"],
                        "status": row["status"],
                        "articles_generated": row["articles_generated"],
                        "duration_seconds": row["duration_seconds"],
                        "run_at": row["run_at"],
                    })

                    # Special event for article-generating phases
                    if row["articles_generated"] and row["articles_generated"] > 0:
                        event_bus.emit("knowledge.articles_created", {
                            "count": row["articles_generated"],
                            "phase": row["phase"],
                        })

                # Get current article count for summary
                total_row = conn.execute(
                    text("SELECT COUNT(*) FROM articles")
                ).fetchone()
                total = total_row[0] if total_row else 0

                event_bus.emit("knowledge.updated", {
                    "new_phases": len(rows),
                    "total_articles": total,
                })

                log.info("knowledge_sync_updates",
                         new_phases=len(rows),
                         total_articles=total,
                         latest_log_id=self._last_log_id)
        except Exception:
            pass


knowledge_sync = KnowledgeSyncService()

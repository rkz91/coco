"""Knowledge Sync Service — polls knowledge.db generation_log and emits SSE events.

The Knowledge Engine cron runs as a separate process (not inside the Platform).
This service bridges the gap by polling generation_log every 60s for new entries
and emitting SSE events so the frontend can auto-refresh.
"""

import asyncio
import sqlite3
import structlog
from pathlib import Path

from app.config import KNOWLEDGE_DB_PATH
from app.services.event_bus import event_bus

log = structlog.get_logger()


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

    def _get_db(self):
        if not KNOWLEDGE_DB_PATH.exists():
            return None
        conn = sqlite3.connect(f"file:{KNOWLEDGE_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_max_log_id(self) -> int:
        conn = self._get_db()
        if not conn:
            return 0
        try:
            row = conn.execute("SELECT MAX(id) FROM generation_log").fetchone()
            return row[0] or 0
        except Exception:
            return 0
        finally:
            conn.close()

    def _check_for_updates(self):
        conn = self._get_db()
        if not conn:
            return

        try:
            rows = conn.execute(
                """SELECT id, phase, status, articles_generated, duration_seconds, run_at
                   FROM generation_log
                   WHERE id > ? AND log_type = 'phase'
                   ORDER BY id""",
                (self._last_log_id,),
            ).fetchall()

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
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            event_bus.emit("knowledge.updated", {
                "new_phases": len(rows),
                "total_articles": total,
            })

            log.info("knowledge_sync_updates",
                     new_phases=len(rows),
                     total_articles=total,
                     latest_log_id=self._last_log_id)

        finally:
            conn.close()


knowledge_sync = KnowledgeSyncService()

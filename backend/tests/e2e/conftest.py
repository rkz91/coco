"""E2E flow tests — fixtures + ASGI transport setup.

These tests exercise the canonical user flows from .planning/v3/E2E-TRACE.md
end-to-end against the in-memory FastAPI app. External dependencies
(Claude API, file watchers, network) are stubbed at module-level so the
tests run hermetically.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Isolate ~/.coco and platform.db to a tmpdir + create tables."""
    coco_home = tmp_path / "coco_home"
    coco_home.mkdir(parents=True, exist_ok=True)
    (coco_home / "queue.json").write_text('{"version": 2, "items": []}', encoding="utf-8")
    (coco_home / "brain.json").write_text('{"people": [], "rules": []}', encoding="utf-8")
    monkeypatch.setenv("COCO_DIR", str(coco_home))
    monkeypatch.setenv("HUB_DIR", str(tmp_path / "hub_home"))
    (tmp_path / "hub_home").mkdir(exist_ok=True)
    monkeypatch.setenv("COCO_OTEL_EXPORTER", "none")  # no-op tracer in tests
    monkeypatch.setenv("COCO_RATE_LIMIT", "false")
    monkeypatch.setenv("COCO_AUTH_TOKEN", "")  # disable PIN

    # Bind SA engine to a tmp DB + create tables.
    db_path = tmp_path / "platform.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from sqlalchemy import create_engine, event
    from app.db import engine as engine_mod
    from app.db import session as session_mod
    from app.db import tables as tables_mod

    new_engine = create_engine(db_url, connect_args={"timeout": 5}, pool_pre_ping=True)

    @event.listens_for(new_engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    monkeypatch.setattr(engine_mod, "engine", new_engine, raising=True)
    monkeypatch.setattr(session_mod, "engine", new_engine, raising=True)

    # Create all tables we know about (best-effort).
    try:
        tables_mod.metadata.create_all(new_engine)
    except Exception:
        pass

    # Also ensure the real config.PLATFORM_DB_PATH (used by middleware that
    # opens sqlite3 directly) exists with the idempotency_keys table — the
    # middleware doesn't go through SA Core.
    import sqlite3
    from app.config import PLATFORM_DB_PATH
    try:
        PLATFORM_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(PLATFORM_DB_PATH), timeout=5.0) as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT NOT NULL,
                    route TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_status INTEGER NOT NULL,
                    response_body TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (key, route)
                );
                """
            )
    except Exception:
        pass

    yield {"coco_home": str(coco_home), "db_path": str(db_path)}

    new_engine.dispose()


@pytest_asyncio.fixture
async def aclient(e2e_env):
    """An httpx.AsyncClient bound to the FastAPI app via ASGITransport."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.observability import init_tracing, configure_logging
    configure_logging()
    init_tracing(None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield client

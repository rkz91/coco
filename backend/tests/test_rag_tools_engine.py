"""Verification tests for backend/app/services/rag_tools knowledge engine.

Confirms the knowledge.db engine is constructed with the SQLite URI
read-only form so writes are rejected at the driver level.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.services import rag_tools


@pytest.fixture(autouse=True)
def _reset_engine_cache():
    """Reset the module-level cached engine before/after each test."""
    rag_tools._knowledge_engine = None
    yield
    eng = rag_tools._knowledge_engine
    if eng is not None:
        try:
            eng.dispose()
        except Exception:
            pass
    rag_tools._knowledge_engine = None


def test_knowledge_engine_url_uses_mode_ro(tmp_path, monkeypatch):
    """The engine URL must carry mode=ro so SQLite enforces read-only."""
    db_path = tmp_path / "knowledge.db"
    # Create a minimal SQLite file so KNOWLEDGE_DB_PATH.exists() is True.
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setattr(rag_tools, "KNOWLEDGE_DB_PATH", Path(db_path))

    eng = rag_tools._get_knowledge_engine()
    assert eng is not None

    url_str = str(eng.url)
    assert "mode=ro" in url_str, f"engine URL missing mode=ro: {url_str}"
    assert "uri=true" in url_str, f"engine URL missing uri=true: {url_str}"


def test_knowledge_engine_blocks_writes(tmp_path, monkeypatch):
    """A CREATE TABLE statement against the engine must raise (read-only DB)."""
    db_path = tmp_path / "knowledge.db"
    # Pre-create with a table so we have something queryable.
    c = sqlite3.connect(str(db_path))
    c.execute("CREATE TABLE seed (k TEXT)")
    c.execute("INSERT INTO seed VALUES ('x')")
    c.commit()
    c.close()

    monkeypatch.setattr(rag_tools, "KNOWLEDGE_DB_PATH", Path(db_path))

    eng = rag_tools._get_knowledge_engine()
    assert eng is not None

    # Read works.
    from sqlalchemy import text
    with eng.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM seed")).scalar() == 1

    # Write fails — readonly database.
    with pytest.raises(Exception) as exc_info:
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE writes_blocked (k TEXT)"))
    msg = str(exc_info.value).lower()
    assert "readonly" in msg or "read-only" in msg or "read only" in msg, (
        f"expected readonly DB error, got: {exc_info.value}"
    )


def test_knowledge_engine_returns_none_when_missing(tmp_path, monkeypatch):
    """If the DB file does not exist, the helper returns None (no engine)."""
    monkeypatch.setattr(rag_tools, "KNOWLEDGE_DB_PATH", Path(tmp_path / "missing.db"))
    assert rag_tools._get_knowledge_engine() is None

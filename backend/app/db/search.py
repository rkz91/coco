"""Full-text search abstraction over hub_content mirror table.

SQLite: uses FTS5 on hub_content_fts virtual table (falls back to LIKE).
PostgreSQL: tsvector (future — falls back to LIKE for now).
"""

import sqlite3
from app.config import PLATFORM_DB_PATH


def search_content(
    query: str,
    limit: int = 50,
    offset: int = 0,
    source_filter: str | None = None,
) -> dict:
    """Search hub_content using FTS5 (preferred) or LIKE (fallback).

    Returns {"items": [dict, ...], "total": int}.
    """
    conn = sqlite3.connect(str(PLATFORM_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        result = _fts5_search(conn, query, limit, offset, source_filter)
        if result is not None:
            return result
        return _like_search(conn, query, limit, offset, source_filter)
    finally:
        conn.close()


def _fts5_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict | None:
    """Try FTS5 search. Returns None if the virtual table doesn't exist."""
    try:
        # Verify FTS5 table exists
        conn.execute("SELECT 1 FROM hub_content_fts LIMIT 1")
    except Exception:
        return None

    try:
        # Build source filter clause
        source_clause = ""
        params: dict = {"q": query, "limit": limit, "offset": offset}
        if source_filter:
            source_clause = "AND c.source = :source"
            params["source"] = source_filter

        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM hub_content c
            JOIN hub_content_fts f ON c.rowid = f.rowid
            WHERE hub_content_fts MATCH :q {source_clause}
            """,
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT c.*, rank FROM hub_content c
            JOIN hub_content_fts f ON c.rowid = f.rowid
            WHERE hub_content_fts MATCH :q {source_clause}
            ORDER BY rank
            LIMIT :limit OFFSET :offset
            """,
            params,
        ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
        }
    except Exception:
        # FTS5 query syntax error (e.g. special chars) — fall back
        return None


def _like_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict:
    """Fallback LIKE search on hub_content."""
    pattern = f"%{query}%"
    params: dict = {"pattern": pattern, "limit": limit, "offset": offset}

    source_clause = ""
    if source_filter:
        source_clause = "AND source = :source"
        params["source"] = source_filter

    where = f"(title LIKE :pattern OR raw_text LIKE :pattern OR processed_text LIKE :pattern) {source_clause}"

    total = conn.execute(
        f"SELECT COUNT(*) FROM hub_content WHERE {where}",
        params,
    ).fetchone()[0]

    rows = conn.execute(
        f"SELECT * FROM hub_content WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
        params,
    ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
    }

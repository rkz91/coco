"""Full-text search abstraction over hub_content mirror table.

SQLite: uses FTS5 on hub_content_fts virtual table (falls back to LIKE).
PostgreSQL: tsvector (future — falls back to LIKE for now).
"""

from sqlalchemy import func, select, text

from app.db.compat import _IS_SQLITE
from app.db.engine import engine
from app.db.tables import hub_content


def search_content(
    query: str,
    limit: int = 50,
    offset: int = 0,
    source_filter: str | None = None,
) -> dict:
    """Search hub_content using FTS5 (preferred) or LIKE (fallback).

    Returns {"items": [dict, ...], "total": int}.
    """
    with engine.connect() as conn:
        if _IS_SQLITE:
            result = _fts5_search(conn, query, limit, offset, source_filter)
            if result is not None:
                return result
        else:
            result = _tsvector_search(conn, query, limit, offset, source_filter)
            if result is not None:
                return result
        return _like_search(conn, query, limit, offset, source_filter)


def _fts5_search(
    conn,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict | None:
    """Try FTS5 search (SQLite only). Returns None if the virtual table doesn't exist."""
    try:
        # Verify FTS5 table exists
        conn.execute(text("SELECT 1 FROM hub_content_fts LIMIT 1"))
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
            text(
                f"SELECT COUNT(*) FROM hub_content c "
                f"JOIN hub_content_fts f ON c.rowid = f.rowid "
                f"WHERE hub_content_fts MATCH :q {source_clause}"
            ),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"SELECT c.*, rank FROM hub_content c "
                f"JOIN hub_content_fts f ON c.rowid = f.rowid "
                f"WHERE hub_content_fts MATCH :q {source_clause} "
                f"ORDER BY rank "
                f"LIMIT :limit OFFSET :offset"
            ),
            params,
        ).mappings().all()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
        }
    except Exception:
        # FTS5 query syntax error (e.g. special chars) — fall back
        return None


def _tsvector_search(
    conn,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict | None:
    """PostgreSQL tsvector search stub.

    TODO: Implement proper tsvector search with ts_query, ts_rank, and a
    GIN index on hub_content.  For now, returns None to fall through to
    the LIKE fallback.
    """
    return None


def _like_search(
    conn,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict:
    """Fallback LIKE search on hub_content using SA Core."""
    c = hub_content.c
    pattern = f"%{query}%"

    # Use actual DB column names via the table object.
    # hub_content.c.body maps to raw_text, hub_content.c.summary maps to processed_text
    where = (c.title.like(pattern)) | (c.body.like(pattern)) | (c.summary.like(pattern))

    if source_filter:
        where = where & (c.source == source_filter)

    total = conn.execute(
        select(func.count()).select_from(hub_content).where(where)
    ).scalar_one()

    rows = conn.execute(
        select(hub_content)
        .where(where)
        .order_by(hub_content.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
    }

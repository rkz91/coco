"""Full-text search abstraction over hub_content mirror table.

SQLite: uses FTS5 on hub_content_fts virtual table (falls back to LIKE).
PostgreSQL: tsvector (future — falls back to LIKE for now).
"""

import time

import structlog
from sqlalchemy import func, select, text

from app.db.compat import _IS_SQLITE
from app.db.engine import engine
from app.db.tables import hub_content

log = structlog.get_logger()


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

        # Reached LIKE fallback path — log for observability (slow path / missing FTS index)
        like_start = time.perf_counter()
        result = _like_search(conn, query, limit, offset, source_filter)
        like_ms = round((time.perf_counter() - like_start) * 1000, 2)
        log.warning(
            "fts5_fallback",
            query=query,
            reason="fts5_unavailable_or_failed",
            duration_ms=like_ms,
            backend="sqlite" if _IS_SQLITE else "postgres",
            source_filter=source_filter,
        )
        return result


def _fts5_search(
    conn,
    query: str,
    limit: int,
    offset: int,
    source_filter: str | None,
) -> dict | None:
    """Try FTS5 search (SQLite only). Returns None if the virtual table doesn't exist."""
    start = time.perf_counter()
    try:
        # Verify FTS5 table exists
        conn.execute(text("SELECT 1 FROM hub_content_fts LIMIT 1"))
    except Exception as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        log.warning(
            "fts5_fallback",
            query=query,
            reason=f"missing_table:{e.__class__.__name__}",
            duration_ms=ms,
            stage="probe",
        )
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
    except Exception as e:
        # FTS5 query syntax error (e.g. special chars) — fall back
        ms = round((time.perf_counter() - start) * 1000, 2)
        log.warning(
            "fts5_fallback",
            query=query,
            reason=e.__class__.__name__,
            duration_ms=ms,
            stage="query",
        )
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

"""Knowledge Engine search — queries ~/.coco/knowledge/knowledge.db."""
import sqlite3
import logging
from pathlib import Path
from fastapi import APIRouter, Query

from app.config import KNOWLEDGE_DB_PATH

log = logging.getLogger(__name__)
router = APIRouter(tags=["Knowledge"])

def _get_knowledge_db():
    """Open knowledge.db read-only. Returns None if not available."""
    if not KNOWLEDGE_DB_PATH.exists():
        return None
    conn = sqlite3.connect(f"file:{KNOWLEDGE_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/api/knowledge/search")
def knowledge_search(q: str = Query(..., min_length=1), limit: int = Query(10, le=50)):
    """Search knowledge graph for entities and articles."""
    conn = _get_knowledge_db()
    if conn is None:
        return {"entities": [], "articles": [], "message": "Knowledge DB not available"}

    try:
        pattern = f"%{q}%"

        # Search entities
        entities = []
        rows = conn.execute(
            "SELECT gid, canonical_name, type, importance_score FROM global_entities WHERE canonical_name LIKE ? ORDER BY importance_score DESC LIMIT ?",
            (pattern, limit)
        ).fetchall()
        for r in rows:
            entities.append(dict(r))

        # Search articles via FTS5
        articles = []
        try:
            rows = conn.execute(
                "SELECT gid, title, snippet(articles_fts, 0, '<b>', '</b>', '...', 40) as snippet FROM articles_fts WHERE articles_fts MATCH ? LIMIT ?",
                (q, limit)
            ).fetchall()
            for r in rows:
                articles.append(dict(r))
        except Exception:
            # FTS might not match — fall back to LIKE on articles
            rows = conn.execute(
                "SELECT gid, title FROM articles WHERE title LIKE ? LIMIT ?",
                (pattern, limit)
            ).fetchall()
            for r in rows:
                articles.append(dict(r))

        conn.close()
        return {"entities": entities, "articles": articles}
    except Exception as e:
        log.error("knowledge_search_error: %s", e)
        if conn:
            conn.close()
        return {"entities": [], "articles": [], "error": str(e)}

@router.get("/api/knowledge/article/{gid}")
def get_knowledge_article(gid: str):
    """Get a specific knowledge article by GID."""
    conn = _get_knowledge_db()
    if conn is None:
        return {"error": "Knowledge DB not available"}

    try:
        row = conn.execute("SELECT * FROM articles WHERE gid = ?", (gid,)).fetchone()
        conn.close()
        if row is None:
            return {"error": "Article not found"}
        return dict(row)
    except Exception as e:
        if conn:
            conn.close()
        return {"error": str(e)}

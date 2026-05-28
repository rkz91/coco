"""Utilities for node-tree (materialized path) queries.

Works with sqlalchemy.engine.Connection.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.db.tables import nodes


def get_subtree_node_ids(db: Connection, node_id: str) -> list[str]:
    """Get all node IDs in the subtree rooted at *node_id* (inclusive).

    Uses the materialized ``path`` column on the ``nodes`` table.
    If the node is not found, falls back to returning ``[node_id]`` so callers
    can still filter safely.
    """
    row = db.execute(
        select(nodes.c.path).where(nodes.c.id == node_id)
    ).fetchone()
    if not row:
        return [node_id]
    path = row[0]
    rows = db.execute(
        select(nodes.c.id).where(nodes.c.path.like(path + "%"))
    ).fetchall()
    return [r[0] for r in rows]


def build_node_id_filter(
    db: Connection,
    node_id: str | None,
    subtree: bool,
    column: str = "node_id",
) -> tuple[str, list[str]]:
    """Return a SQL fragment and params list for node-based filtering.

    Returns (sql_fragment, params) where *sql_fragment* is either empty or a
    clause like ``"node_id IN (?, ?, ?)"`` (without WHERE/AND prefix) so
    callers can integrate it into their own condition lists.
    """
    if not node_id:
        return ("", [])

    if subtree:
        ids = get_subtree_node_ids(db, node_id)
        placeholders = ", ".join("?" for _ in ids)
        return (f"{column} IN ({placeholders})", ids)

    return (f"{column} = ?", [node_id])

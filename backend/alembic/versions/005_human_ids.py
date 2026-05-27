"""Add human_id column to todo_overrides, agents; backfill from entity_identifiers.

Revision ID: 005
Revises: 004
Create Date: 2026-05-26

Adds Linear-style human-readable IDs (e.g., CXR-47) as a UNIQUE column directly
on todos and agents (decisions are JSON-backed in queue.json — handled in app
code, not in this migration).

Backfill order:
  1. For each row with an existing mapping in entity_identifiers, copy that
     display_id into human_id.
  2. For remaining rows (in monotonic order by created_at), generate fresh
     IDs by atomically incrementing id_sequences. Rows without a node_id
     are placed under a synthetic "CXR" team prefix bucket.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GLOBAL_BUCKET_NODE_ID = "__global__"
GLOBAL_PREFIX = "CXR"


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _ensure_global_bucket(conn) -> None:
    """Seed a sentinel id_sequences row for entities without a real node."""
    conn.exec_driver_sql(
        "INSERT OR IGNORE INTO id_sequences (node_id, next_seq) VALUES (?, 1)",
        (GLOBAL_BUCKET_NODE_ID,),
    )


def _auto_prefix(label: str | None) -> str:
    if not label:
        return GLOBAL_PREFIX
    alpha = "".join(c for c in label if c.isalpha())
    if len(alpha) >= 3:
        return alpha[:3].upper()
    return (alpha + "XXX")[:3].upper()


def _existing_prefixes(conn, exclude_node_id: str | None = None) -> set[str]:
    """Return the set of prefixes already assigned to nodes (excluding one)."""
    if exclude_node_id is None:
        rows = conn.exec_driver_sql(
            "SELECT prefix FROM nodes WHERE prefix IS NOT NULL AND prefix != ''"
        ).fetchall()
    else:
        rows = conn.exec_driver_sql(
            "SELECT prefix FROM nodes "
            "WHERE prefix IS NOT NULL AND prefix != '' AND id != ?",
            (exclude_node_id,),
        ).fetchall()
    return {r[0] for r in rows}


def _disambiguate_prefix(base: str, taken: set[str]) -> str:
    """Return a prefix derived from ``base`` that is not in ``taken``.

    First tries the bare prefix, then appends digits 2-99. The combined
    string is truncated to 5 chars so display_ids stay compact.
    """
    if base not in taken:
        return base
    # Try AUD2, AUD3, ... AUD99 — disambiguated but still readable.
    for n in range(2, 100):
        candidate = f"{base}{n}"[:5]
        if candidate not in taken:
            return candidate
    # Pathological fallback — extremely unlikely but keep migration deterministic.
    return base


def _prefix_for_node(conn, node_id: str | None) -> str:
    """Return the prefix for a node, generating one if absent.

    Auto-generated prefixes are disambiguated against the rest of the
    ``nodes`` table to guarantee global uniqueness — otherwise two nodes
    whose labels share the same first three alpha characters (e.g.
    "AuditBoard" and "AuditBoard Tax") would both produce ``AUD`` and the
    later ``UNIQUE INDEX uq_agents_human_id`` would collide on ``AUD-1``.
    """
    if not node_id or node_id == GLOBAL_BUCKET_NODE_ID:
        return GLOBAL_PREFIX
    row = conn.exec_driver_sql(
        "SELECT prefix, label FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if not row:
        return GLOBAL_PREFIX
    rm = row._mapping
    prefix = rm["prefix"]
    if prefix:
        return prefix
    base = _auto_prefix(rm["label"])
    taken = _existing_prefixes(conn, exclude_node_id=node_id)
    # The GLOBAL_PREFIX is reserved for the synthetic bucket — never reuse it
    # for a real node (otherwise a fresh-DB-with-global-bucket-but-no-other-nodes
    # scenario would still collide).
    taken.add(GLOBAL_PREFIX)
    prefix = _disambiguate_prefix(base, taken)
    conn.exec_driver_sql(
        "UPDATE nodes SET prefix = ?, updated_at = datetime('now') WHERE id = ?",
        (prefix, node_id),
    )
    return prefix


def _next_seq(conn, node_id: str) -> int:
    """Atomically reserve and return the next sequence number for a node."""
    conn.exec_driver_sql(
        "INSERT INTO id_sequences (node_id, next_seq) VALUES (?, 1) "
        "ON CONFLICT(node_id) DO UPDATE SET next_seq = next_seq + 1",
        (node_id,),
    )
    row = conn.exec_driver_sql(
        "SELECT next_seq FROM id_sequences WHERE node_id = ?", (node_id,)
    ).fetchone()
    return int(row[0])


def _generate_human_id(conn, node_id: str | None) -> str:
    bucket = node_id if node_id else GLOBAL_BUCKET_NODE_ID
    prefix = _prefix_for_node(conn, bucket if bucket != GLOBAL_BUCKET_NODE_ID else None)
    seq = _next_seq(conn, bucket)
    return f"{prefix}-{seq}"


def _backfill(conn, table: str, id_col: str, node_col: str | None, entity_type: str) -> None:
    """Backfill human_id for all rows in `table` lacking one."""
    # Step 1: pull display_id from entity_identifiers where present.
    conn.exec_driver_sql(
        f"""
        UPDATE {table}
           SET human_id = (
               SELECT ei.display_id FROM entity_identifiers ei
                WHERE ei.entity_id = {table}.{id_col}
                  AND ei.entity_type = '{entity_type}'
           )
         WHERE human_id IS NULL
           AND EXISTS (
               SELECT 1 FROM entity_identifiers ei
                WHERE ei.entity_id = {table}.{id_col}
                  AND ei.entity_type = '{entity_type}'
           )
        """
    )

    # Step 2: generate fresh IDs for remaining rows in monotonic created_at order.
    rows = conn.exec_driver_sql(
        f"SELECT {id_col}, "
        + (f"{node_col}" if node_col else "NULL")
        + f", created_at FROM {table} WHERE human_id IS NULL "
        f"ORDER BY COALESCE(created_at, '1970-01-01') ASC, {id_col} ASC"
    ).fetchall()

    for row in rows:
        entity_id = row[0]
        node_id = row[1] if node_col else None
        human_id = _generate_human_id(conn, node_id)

        conn.exec_driver_sql(
            f"UPDATE {table} SET human_id = ? WHERE {id_col} = ?",
            (human_id, entity_id),
        )

        # Mirror into entity_identifiers (keep both data sources consistent).
        conn.exec_driver_sql(
            "INSERT OR IGNORE INTO entity_identifiers "
            "(entity_id, entity_type, node_id, sequence_num, display_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                entity_id,
                entity_type,
                node_id or GLOBAL_BUCKET_NODE_ID,
                int(human_id.rsplit("-", 1)[1]),
                human_id,
            ),
        )


def upgrade() -> None:
    bind = op.get_bind()

    # 0. Ensure the id_sequences / entity_identifiers tables exist.
    #    In normal deploys init_db.py creates these via SA Core metadata
    #    before alembic runs, but for fresh alembic-only deploys we create
    #    them here so this migration is self-sufficient.
    op.execute(
        "CREATE TABLE IF NOT EXISTS id_sequences ("
        "node_id TEXT PRIMARY KEY, next_seq INTEGER NOT NULL DEFAULT 1)"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS entity_identifiers ("
        "entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, "
        "node_id TEXT NOT NULL, sequence_num INTEGER NOT NULL, "
        "display_id TEXT NOT NULL, UNIQUE(node_id, sequence_num))"
    )

    # 0b. Ensure the nodes table has the prefix column. The baseline (001)
    #     created ``nodes`` without one, but ``_prefix_for_node`` SELECTs and
    #     UPDATEs that column. Adding it here keeps fresh alembic-only
    #     databases consistent with init_db.py's SA Core metadata.
    if not _column_exists(bind, "nodes", "prefix"):
        op.execute("ALTER TABLE nodes ADD COLUMN prefix TEXT")

    # 1. Ensure global bucket exists for entities without a node.
    _ensure_global_bucket(bind)

    # 2. Add human_id columns (idempotent — checked before ALTER).
    if not _column_exists(bind, "todo_overrides", "human_id"):
        op.execute("ALTER TABLE todo_overrides ADD COLUMN human_id TEXT")

    if not _column_exists(bind, "agents", "human_id"):
        op.execute("ALTER TABLE agents ADD COLUMN human_id TEXT")

    # 3. Backfill.
    _backfill(bind, "todo_overrides", "hub_todo_id", "node_id", "todo")
    _backfill(bind, "agents", "id", "node_id", "agent")

    # 4. Enforce uniqueness AFTER backfill (otherwise duplicates would block).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_todo_overrides_human_id "
        "ON todo_overrides(human_id) WHERE human_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_human_id "
        "ON agents(human_id) WHERE human_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_todo_overrides_human_id")
    op.execute("DROP INDEX IF EXISTS uq_agents_human_id")
    # NOTE: SQLite ALTER TABLE DROP COLUMN requires 3.35+. Use batch mode.
    with op.batch_alter_table("todo_overrides") as batch:
        try:
            batch.drop_column("human_id")
        except Exception:
            pass
    with op.batch_alter_table("agents") as batch:
        try:
            batch.drop_column("human_id")
        except Exception:
            pass

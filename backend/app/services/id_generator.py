"""Human-readable ID generator for entities (e.g. CXR-47).

Supports todos, tasks, and any future entity types.
Uses atomic sequence increments per node to produce unique display IDs.
Auto-generates a prefix from the node label if none is configured.
"""

import re
import structlog
from app.db.session import get_db

log = structlog.get_logger()


def _auto_prefix(label: str) -> str:
    """Generate a 3-char uppercase prefix from a node label."""
    alpha = re.sub(r"[^A-Za-z]", "", label)
    if len(alpha) >= 3:
        return alpha[:3].upper()
    return (alpha + "XXX")[:3].upper()


def _get_or_create_prefix(conn, node_id: str) -> str | None:
    """Get the node's prefix, auto-generating one if absent."""
    row = conn.exec_driver_sql(
        "SELECT prefix, label FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if not row:
        return None

    rm = row._mapping
    prefix = rm["prefix"]
    if prefix:
        return prefix

    label = rm["label"] or ""
    if not label:
        return None

    prefix = _auto_prefix(label)

    conn.exec_driver_sql(
        "UPDATE nodes SET prefix = ?, updated_at = datetime('now') WHERE id = ?",
        (prefix, node_id),
    )
    return prefix


def generate_display_id(node_id: str, entity_type: str = "todo", entity_id: str | None = None) -> str | None:
    """Atomically increment the sequence for a node and return PREFIX-N."""
    with get_db() as conn:
        prefix = _get_or_create_prefix(conn, node_id)
        if not prefix:
            return None

        conn.exec_driver_sql(
            "INSERT INTO id_sequences (node_id, next_seq) VALUES (?, 1) "
            "ON CONFLICT(node_id) DO UPDATE SET next_seq = next_seq + 1",
            (node_id,),
        )
        seq_row = conn.exec_driver_sql(
            "SELECT next_seq FROM id_sequences WHERE node_id = ?", (node_id,)
        ).fetchone()
        seq = seq_row[0]

        conn.exec_driver_sql(
            "UPDATE id_sequences SET next_seq = ? WHERE node_id = ?",
            (seq + 1, node_id),
        )

        display_id = f"{prefix}-{seq}"

        if entity_id:
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO entity_identifiers "
                "(entity_id, entity_type, node_id, sequence_num, display_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (entity_id, entity_type, node_id, seq, display_id),
            )

        return display_id


def assign_display_id(entity_id: str, node_id: str, entity_type: str = "todo") -> str | None:
    """Assign a human-readable display ID to an entity and persist the mapping."""
    display_id = generate_display_id(node_id, entity_type=entity_type, entity_id=entity_id)
    if display_id:
        log.info("display_id_assigned", entity_id=entity_id, entity_type=entity_type, display_id=display_id)
    return display_id


def resolve_display_id(display_id: str) -> dict | None:
    """Resolve a human-readable ID (e.g. 'CXR-47') to entity details."""
    with get_db() as conn:
        row = conn.exec_driver_sql(
            "SELECT entity_id, entity_type, node_id, display_id FROM entity_identifiers WHERE display_id = ?",
            (display_id.upper(),),
        ).fetchone()
        if row:
            return dict(row._mapping)

        row = conn.exec_driver_sql(
            "SELECT entity_id, entity_type, node_id, display_id FROM entity_identifiers WHERE UPPER(display_id) = UPPER(?)",
            (display_id,),
        ).fetchone()
        return dict(row._mapping) if row else None

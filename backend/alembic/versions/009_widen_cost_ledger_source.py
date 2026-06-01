"""Widen cost_ledger.source CHECK to include all real cost writers.

Revision ID: 009_widen_cost_ledger_source
Revises: 008_audit_log
Create Date: 2026-06-01

The legacy cost_ledger CHECK only allowed ('station','chat','think',
'kh_pipeline'), but the application writes source='agent' (process_manager,
agent SDK), 'classifier' (auto_classifier), and 'brain' (brain_query). Every
such insert raised IntegrityError, which record_sdk_cost swallowed -> the
ledger stayed empty (0 rows) while hub_api_costs grew to ~900.

SQLite cannot ALTER a CHECK in place, so we use the recreate-table pattern:
create the new table with the widened CHECK, copy all rows, drop the old,
rename, and recreate the indexes. The widened set mirrors
``COST_LEDGER_SOURCES`` in db/tables.py (the create_all source of truth).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009_widen_cost_ledger_source"
down_revision: Union[str, None] = "008_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLS = (
    "id, agent_id, project_id, model, input_tokens, output_tokens, "
    "cost_usd, source, created_at, node_id"
)

_WIDE_SOURCES = (
    "'station','chat','think','kh_pipeline','agent','classifier','brain','api_token'"
)
_NARROW_SOURCES = "'station','chat','think','kh_pipeline'"

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_cost_project ON cost_ledger(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_cost_time ON cost_ledger(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_cost_ledger_agent ON cost_ledger(agent_id)",
    "CREATE INDEX IF NOT EXISTS idx_cost_ledger_node ON cost_ledger(node_id)",
)


def _ddl(sources: str) -> str:
    return f"""
        CREATE TABLE cost_ledger_new (
            id TEXT PRIMARY KEY,
            agent_id TEXT REFERENCES "agents"(id),
            project_id TEXT,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            source TEXT NOT NULL DEFAULT 'agent' CHECK(source IN ({sources})),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            node_id TEXT
        );
    """


def _rebuild(sources: str) -> None:
    """Recreate cost_ledger with the given CHECK source set.

    Drives DDL+DML through Alembic's bound connection and commits explicitly,
    matching migration 002 (SQLite non-transactional DDL would otherwise roll
    back the INSERT/DROP/RENAME). Idempotent against a stray scratch table.
    """
    bind = op.get_bind()
    bind.exec_driver_sql("DROP TABLE IF EXISTS cost_ledger_new")
    bind.exec_driver_sql(_ddl(sources))
    bind.exec_driver_sql(
        f"INSERT INTO cost_ledger_new ({_COLS}) SELECT {_COLS} FROM cost_ledger"
    )
    bind.exec_driver_sql("DROP TABLE cost_ledger")
    bind.exec_driver_sql("ALTER TABLE cost_ledger_new RENAME TO cost_ledger")
    for stmt in _INDEXES:
        bind.exec_driver_sql(stmt)
    bind.commit()


def upgrade() -> None:
    _rebuild(_WIDE_SOURCES)


def downgrade() -> None:
    # Best-effort: rows with the newly-allowed sources would violate the
    # narrow CHECK, so drop them before reinstating the old constraint.
    bind = op.get_bind()
    bind.exec_driver_sql(
        "DELETE FROM cost_ledger WHERE source NOT IN (" + _NARROW_SOURCES + ")"
    )
    bind.commit()
    _rebuild(_NARROW_SOURCES)

#!/usr/bin/env python3
"""One-time cleanup: delete orphaned analysis_jobs rows.

`analysis_jobs.node_id` declares `REFERENCES nodes(id)` but SQLite does not
enforce foreign keys unless `PRAGMA foreign_keys = ON` is set on every
connection, so historical drift left rows whose parent node was deleted.

`PRAGMA foreign_key_check` against ~/.coco/platform.db currently reports
4 such rows. This script deletes them inside a single `BEGIN IMMEDIATE`
transaction and re-runs `PRAGMA foreign_key_check` to confirm the table
is clean.

Usage:
    python scripts/cleanup_orphaned_analysis_jobs.py --dry-run
    python scripts/cleanup_orphaned_analysis_jobs.py --execute

Idempotent: re-running after --execute is a no-op (0 rows deleted).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


DEFAULT_DB = Path.home() / ".coco" / "platform.db"


def find_orphans(conn: sqlite3.Connection) -> list[tuple]:
    """Return rows in analysis_jobs whose node_id has no matching nodes.id."""
    cursor = conn.execute(
        """
        SELECT aj.id, aj.node_id, aj.status, aj.created_at
        FROM analysis_jobs aj
        LEFT JOIN nodes n ON aj.node_id = n.id
        WHERE n.id IS NULL
        ORDER BY aj.created_at
        """
    )
    return cursor.fetchall()


def cleanup(db_path: Path, execute: bool) -> int:
    """Delete orphaned rows. Returns the count of rows deleted (or to-be-deleted)."""
    if not db_path.exists():
        print(f"ERROR: database not found at {db_path}", file=sys.stderr)
        return -1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        # Pre-flight: report what foreign_key_check sees right now.
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        print(f"foreign_key_check found {len(fk_violations)} violation(s) before cleanup")
        for v in fk_violations:
            print(f"  - table={v[0]} rowid={v[1]} parent={v[2]} fkid={v[3]}")

        orphans = find_orphans(conn)
        count = len(orphans)
        print(f"\nFound {count} orphaned analysis_jobs row(s):")
        for row in orphans:
            print(
                f"  id={row['id']}  node_id={row['node_id']}  "
                f"status={row['status']}  created_at={row['created_at']}"
            )

        if count == 0:
            print("\nNothing to do.")
            return 0

        if not execute:
            print("\n[--dry-run] No changes made. Re-run with --execute to delete.")
            return count

        # Lock the row range up-front so a concurrent writer cannot insert
        # an analysis_job referencing a doomed orphan node_id between the
        # SELECT and the DELETE.
        conn.execute("BEGIN IMMEDIATE")
        try:
            ids_to_delete = [row["id"] for row in orphans]
            placeholders = ",".join("?" for _ in ids_to_delete)
            cur = conn.execute(
                f"DELETE FROM analysis_jobs WHERE id IN ({placeholders})",
                ids_to_delete,
            )
            deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        print(f"\nDeleted {deleted} row(s).")

        # Post-check: foreign_key_check should now report 0 violations on
        # analysis_jobs (other tables may still drift independently).
        remaining = conn.execute(
            "PRAGMA foreign_key_check(analysis_jobs)"
        ).fetchall()
        print(f"Post-cleanup foreign_key_check(analysis_jobs): {len(remaining)} violation(s)")
        return deleted
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="List orphan rows but make no changes.",
    )
    group.add_argument(
        "--execute",
        dest="execute",
        action="store_true",
        help="Delete orphan rows inside a BEGIN IMMEDIATE transaction.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to platform.db (default: {DEFAULT_DB})",
    )
    args = parser.parse_args()

    rc = cleanup(args.db, execute=args.execute)
    return 0 if rc >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())

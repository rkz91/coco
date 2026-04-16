#!/usr/bin/env python3
"""
fix_knowledge_schema.py — Knowledge DB schema migration for product article ingestion.

Fixes 5 CRITICAL and 2 MAJOR review findings:

  C1  Drop reject_low_confidence_insert / reject_low_confidence_update triggers.
      These BEFORE INSERT/UPDATE triggers silently RAISE(IGNORE) when
      confidence < 0.95, which blocks *all* new article ingestion below
      that threshold — including perfectly valid product articles.

  C2  Widen the global_entities.type CHECK constraint to include 'product'.
      SQLite cannot ALTER a CHECK; we recreate the table with the new
      constraint, preserving all data and indexes.

  C3  Verify sources_json column exists on articles table (confirmation only).

  M4  Ensure articles_fts is populated on new article inserts.  Creates an
      AFTER INSERT trigger that mirrors title + body into articles_fts.
      Also backfills any articles currently missing from articles_fts.

  M5  Documents the upsert pattern: INSERT OR REPLACE keyed on
      UNIQUE(gid, version).

Usage:
    python3 scripts/fix_knowledge_schema.py [--db PATH] [--dry-run] [--no-backup]

Idempotent — safe to run multiple times.
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fix_knowledge_schema")

# Default knowledge DB path
DEFAULT_DB = Path.home() / ".coco" / "knowledge" / "knowledge.db"

# ---------------------------------------------------------------------------
# The new CHECK constraint values for global_entities.type
# ---------------------------------------------------------------------------
ALLOWED_ENTITY_TYPES = (
    "person", "team", "role", "system",
    "module", "org_unit", "document", "product",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_db(db_path: Path) -> Path:
    """Create a timestamped backup of the DB file."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_suffix(f".bak-migration-{ts}")
    shutil.copy2(db_path, backup)
    log.info("Backup created: %s (%.1f MB)", backup.name, backup.stat().st_size / 1e6)
    return backup


def _body_json_to_fts_text(body_json: str | None) -> str:
    """Extract plain text from article body_json for FTS5 indexing."""
    if not body_json:
        return ""
    try:
        data = json.loads(body_json)
        parts: list[str] = []
        for section in data.get("sections", []):
            heading = section.get("heading", "")
            content = section.get("content", "")
            if heading:
                parts.append(heading)
            if content:
                parts.append(content)
        return "\n".join(parts)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# C1 — Drop reject_low_confidence triggers
# ---------------------------------------------------------------------------

def fix_c1_drop_reject_triggers(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Drop reject_low_confidence_insert and reject_low_confidence_update triggers."""
    triggers = [
        "reject_low_confidence_insert",
        "reject_low_confidence_update",
    ]
    changed = False
    for name in triggers:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
        ).fetchone()
        if row:
            log.info("C1: Found trigger %s — dropping", name)
            if not dry_run:
                conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            changed = True
        else:
            log.info("C1: Trigger %s already absent — OK", name)
    return changed


# ---------------------------------------------------------------------------
# C2 — Widen global_entities.type CHECK to include 'product'
# ---------------------------------------------------------------------------

def fix_c2_widen_entity_type_check(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Recreate global_entities with CHECK(..., 'product')."""
    # Check if 'product' is already allowed
    current_ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='global_entities'"
    ).fetchone()
    if current_ddl and "'product'" in current_ddl[0]:
        log.info("C2: global_entities CHECK already includes 'product' — skipping")
        return False

    log.info("C2: Recreating global_entities with 'product' in CHECK constraint")
    if dry_run:
        return True

    check_values = ",".join(f"'{t}'" for t in ALLOWED_ENTITY_TYPES)

    # Step 1: Create new table with updated CHECK
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS global_entities_new (
            gid              TEXT PRIMARY KEY,
            canonical_name   TEXT NOT NULL,
            type             TEXT NOT NULL CHECK(type IN ({check_values})),
            aliases_json     TEXT NOT NULL DEFAULT '[]',
            merged_from_json TEXT NOT NULL DEFAULT '[]',
            importance_score REAL NOT NULL DEFAULT 0.0,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            parent_project_slug TEXT
        )
    """)

    # Step 2: Copy all existing data
    conn.execute("""
        INSERT INTO global_entities_new
            (gid, canonical_name, type, aliases_json, merged_from_json,
             importance_score, created_at, updated_at, parent_project_slug)
        SELECT gid, canonical_name, type, aliases_json, merged_from_json,
               importance_score, created_at, updated_at, parent_project_slug
        FROM global_entities
    """)

    # Step 3: Drop old table and rename
    conn.execute("DROP TABLE global_entities")
    conn.execute("ALTER TABLE global_entities_new RENAME TO global_entities")

    # Step 4: Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ge_type ON global_entities(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ge_name ON global_entities(canonical_name)")

    count = conn.execute("SELECT COUNT(*) FROM global_entities").fetchone()[0]
    log.info("C2: Recreated global_entities with %d rows, 'product' type now allowed", count)
    return True


# ---------------------------------------------------------------------------
# C3 — Verify sources_json column exists
# ---------------------------------------------------------------------------

def verify_c3_sources_json(conn: sqlite3.Connection) -> bool:
    """Confirm sources_json column exists on articles table."""
    cols = [
        row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
    ]
    if "sources_json" in cols:
        log.info("C3: sources_json column exists on articles — OK")
        return True
    else:
        log.warning("C3: sources_json column MISSING from articles table!")
        return False


# ---------------------------------------------------------------------------
# M4 — Ensure articles_fts is populated
# ---------------------------------------------------------------------------

def fix_m4_fts_population(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Create AFTER INSERT trigger for articles_fts and backfill missing rows."""
    changed = False

    # Check if trigger already exists
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name='articles_fts_insert'"
    ).fetchone()

    if not existing:
        log.info("M4: Creating AFTER INSERT trigger for articles_fts")
        if not dry_run:
            # We use body_json_to_fts_text logic in the application layer.
            # For the trigger, we insert the raw body_json — the search.py
            # already handles FTS via the body column. But for better results,
            # we extract just the text sections.
            # SQLite triggers can't call Python functions, so we store body_json
            # as-is and rely on the application to populate correctly.
            # Instead, we create a simple trigger that inserts what we can.
            # Use REPLACE to strip JSON syntax and extract readable text for FTS.
            # json_each + json_extract pulls section content; REPLACE strips residual braces.
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_fts_insert
                AFTER INSERT ON articles
                BEGIN
                    INSERT INTO articles_fts(gid, title, body)
                    VALUES (
                        NEW.gid,
                        NEW.title,
                        COALESCE(
                            (SELECT GROUP_CONCAT(
                                json_extract(value, '$.heading') || ' ' || json_extract(value, '$.content'), ' ')
                             FROM json_each(json_extract(NEW.body_json, '$.sections'))),
                            REPLACE(REPLACE(REPLACE(COALESCE(NEW.body_json, ''), '"', ''), '{', ''), '}', '')
                        )
                    );
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_fts_update
                AFTER UPDATE OF title, body_json ON articles
                BEGIN
                    DELETE FROM articles_fts WHERE gid = OLD.gid AND title = OLD.title;
                    INSERT INTO articles_fts(gid, title, body)
                    VALUES (
                        NEW.gid,
                        NEW.title,
                        COALESCE(
                            (SELECT GROUP_CONCAT(
                                json_extract(value, '$.heading') || ' ' || json_extract(value, '$.content'), ' ')
                             FROM json_each(json_extract(NEW.body_json, '$.sections'))),
                            REPLACE(REPLACE(REPLACE(COALESCE(NEW.body_json, ''), '"', ''), '{', ''), '}', '')
                        )
                    );
                END
            """)
            # And AFTER DELETE
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_fts_delete
                AFTER DELETE ON articles
                BEGIN
                    DELETE FROM articles_fts WHERE gid = OLD.gid AND title = OLD.title;
                END
            """)
        changed = True
    else:
        log.info("M4: articles_fts_insert trigger already exists — OK")

    # Backfill: find articles not in articles_fts and insert them
    if not dry_run:
        missing = conn.execute("""
            SELECT a.gid, a.title, a.body_json
            FROM articles a
            WHERE NOT EXISTS (
                SELECT 1 FROM articles_fts f WHERE f.gid = a.gid
            )
        """).fetchall()

        if missing:
            log.info("M4: Backfilling %d articles into articles_fts", len(missing))
            for row in missing:
                gid, title, body_json = row[0], row[1], row[2]
                body_text = _body_json_to_fts_text(body_json)
                conn.execute(
                    "INSERT INTO articles_fts(gid, title, body) VALUES (?, ?, ?)",
                    (gid, title, body_text),
                )
            changed = True
        else:
            log.info("M4: All articles already in articles_fts — OK")

    return changed


# ---------------------------------------------------------------------------
# M5 — Document and verify upsert pattern
# ---------------------------------------------------------------------------

def verify_m5_upsert_pattern(conn: sqlite3.Connection):
    """Verify UNIQUE(gid, version) constraint exists for INSERT OR REPLACE."""
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    if ddl and "UNIQUE(gid, version)" in ddl[0]:
        log.info("M5: UNIQUE(gid, version) constraint on articles — OK")
        log.info("M5: Upsert pattern: INSERT OR REPLACE INTO articles "
                 "(gid, version, title, ...) VALUES (?, ?, ?, ...)")
        log.info("M5: This replaces the existing row when gid+version match, "
                 "or inserts a new row otherwise.")
    else:
        log.warning("M5: UNIQUE(gid, version) constraint NOT FOUND — "
                     "INSERT OR REPLACE may not work as expected!")


# ---------------------------------------------------------------------------
# Bonus: Register 'product' in article_types reference table
# ---------------------------------------------------------------------------

def register_product_article_type(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Add 'product' to the article_types reference table if not present."""
    existing = conn.execute(
        "SELECT 1 FROM article_types WHERE type_id = 'product'"
    ).fetchone()
    if existing:
        log.info("Bonus: 'product' already in article_types — OK")
        return False

    log.info("Bonus: Inserting 'product' into article_types")
    if not dry_run:
        conn.execute(
            "INSERT OR IGNORE INTO article_types(type_id, category, label, schedule, enabled) "
            "VALUES ('product', 'entity', 'Product', 'daily', 1)"
        )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fix knowledge.db schema for product article ingestion"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to knowledge.db (default: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would change without modifying the DB"
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip creating a backup before modifying"
    )
    args = parser.parse_args()

    db_path: Path = args.db
    if not db_path.exists():
        log.error("Database not found: %s", db_path)
        sys.exit(1)

    log.info("=" * 60)
    log.info("Knowledge DB Schema Migration")
    log.info("Database: %s", db_path)
    log.info("Mode: %s", "DRY RUN" if args.dry_run else "LIVE")
    log.info("=" * 60)

    # Backup
    if not args.dry_run and not args.no_backup:
        _backup_db(db_path)

    conn = sqlite3.connect(str(db_path), timeout=120.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # OFF during migration (table rebuild)
    conn.execute("PRAGMA busy_timeout=120000")

    any_changes = False

    try:
        # C1: Drop reject_low_confidence triggers
        log.info("")
        log.info("--- C1: Drop reject_low_confidence triggers ---")
        if fix_c1_drop_reject_triggers(conn, args.dry_run):
            any_changes = True

        # C2: Widen global_entities.type CHECK
        log.info("")
        log.info("--- C2: Widen global_entities.type CHECK to include 'product' ---")
        if fix_c2_widen_entity_type_check(conn, args.dry_run):
            any_changes = True

        # C3: Verify sources_json
        log.info("")
        log.info("--- C3: Verify sources_json column ---")
        verify_c3_sources_json(conn)

        # M4: FTS population
        log.info("")
        log.info("--- M4: Ensure articles_fts is populated ---")
        if fix_m4_fts_population(conn, args.dry_run):
            any_changes = True

        # M5: Document upsert pattern
        log.info("")
        log.info("--- M5: Verify upsert pattern ---")
        verify_m5_upsert_pattern(conn)

        # Bonus: Register product article type
        log.info("")
        log.info("--- Bonus: Register 'product' article type ---")
        if register_product_article_type(conn, args.dry_run):
            any_changes = True

        if not args.dry_run:
            conn.commit()
            log.info("")
            log.info("All changes committed.")
        else:
            log.info("")
            log.info("DRY RUN complete — no changes made.")

        # Post-migration summary
        log.info("")
        log.info("=" * 60)
        log.info("POST-MIGRATION SUMMARY")
        log.info("=" * 60)

        # Trigger count
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        log.info("Active triggers: %s",
                 ", ".join(r[0] for r in triggers) if triggers else "(none)")

        # Entity types in CHECK
        ge_ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='global_entities'"
        ).fetchone()
        log.info("global_entities DDL includes 'product': %s",
                 "'product'" in ge_ddl[0] if ge_ddl else "TABLE NOT FOUND")

        # Article counts
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        total_fts = conn.execute("SELECT COUNT(*) FROM articles_fts").fetchone()[0]
        log.info("Articles: %d rows, FTS: %d rows (delta: %d)",
                 total_articles, total_fts, total_articles - total_fts)

        # Entity type distribution
        types = conn.execute(
            "SELECT type, COUNT(*) FROM global_entities GROUP BY type ORDER BY type"
        ).fetchall()
        log.info("Entity types: %s", ", ".join(f"{r[0]}={r[1]}" for r in types))

        # Article types
        atypes = conn.execute(
            "SELECT type_id FROM article_types ORDER BY type_id"
        ).fetchall()
        log.info("Registered article types: %s", ", ".join(r[0] for r in atypes))

    except Exception as e:
        log.error("Migration failed: %s", e, exc_info=True)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

    log.info("")
    if any_changes and not args.dry_run:
        log.info("Migration complete. Changes applied successfully.")
    elif args.dry_run:
        log.info("Dry run complete. Re-run without --dry-run to apply.")
    else:
        log.info("No changes needed — schema already up to date.")


if __name__ == "__main__":
    main()

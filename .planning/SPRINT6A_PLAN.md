# Sprint 6A Plan: "Cut the Last Wires"

**Date:** 2026-03-28
**Duration:** 4 days
**Prerequisites:** Sprint 5 complete (Sprint 5.5 foundation already exists in codebase)

---

## The Problem

The SA Core migration is **80% done** — but the last 20% is the part that blocks PostgreSQL. Here's the actual state:

| Layer | Status | Detail |
|-------|--------|--------|
| **Engine** (`engine.py`) | DONE | SA Core engine with WAL pragmas |
| **Session** (`session.py`) | DONE | `get_db()` context manager with auto-commit/rollback |
| **Tables** (`tables.py`) | DONE | 707 lines, all 37+ tables defined as SA Core metadata |
| **Hub sync** (`hub_sync.py`) | DONE | Mirrors hub.db → hub_* tables every 60s |
| **Hub mirrors** | DONE | hub_content, hub_todos, hub_projects, etc. all populated |
| **Router connections** | DONE | All 21 routers use `get_db()`, import from `tables.py` |
| **SA Core queries** | PARTIAL | Many queries use SA Core expressions, but **117 `text()` raw SQL calls remain** |
| **Infrastructure** | BROKEN | search.py, event_bus.py bypass SA Core entirely; init_db.py is 1,035 lines raw DDL |
| **Dead code** | PRESENT | `connections.py` has zero importers — fully dead |

### The 117 `text()` calls — why they matter

Every `text("datetime('now', '-7 days')")` or `text("INSERT OR REPLACE INTO ...")` is a **SQLite-only** string that will crash on PostgreSQL. These are the last wires to cut.

### Breakdown by file

**Routers (81 `text()` calls across 13 files):**

| File | Count | Primary pattern |
|------|-------|----------------|
| `jarvis.py` | 12 | Full `text("SELECT ...")` raw queries for hub data |
| `costs.py` | 9 | `datetime('now', '-N days')` date functions |
| `dashboard.py` | 9 | `datetime('now')` + aggregation aliases |
| `todos.py` | 9 | `date('now')` comparisons, `INSERT OR REPLACE` upserts |
| `home.py` | 9 | `datetime('now')` + hub data aggregation |
| `content.py` | 9 | `datetime('now')` + FTS5 search calls |
| `chat.py` | 6 | `text("SELECT ...")` for hub reads in chat context |
| `search.py` | 4 | FTS5 search delegation |
| `tree.py` | 4 | Column aliases in GROUP BY |
| `collaboration.py` | 4 | `datetime('now')` |
| `drafts.py` | 2 | `text("INSERT OR REPLACE ...")` upserts |
| `teams.py` | 2 | `datetime('now')` |
| `analysis.py` | 2 | `datetime('now')` |

**Services (27 `text()` calls across 6 files):**

| File | Count | Primary pattern |
|------|-------|----------------|
| `collaboration_context.py` | 16 | Full `text("SELECT ...")` raw queries |
| `folder_scanner.py` | 3 | `datetime('now')` |
| `process_manager.py` | 2 | Status updates |
| `chat_context.py` | 2 | `datetime('now')` |
| `event_bus.py` | 2 | Direct `sqlite3.connect()` bypass |
| `auto_classifier.py` | 2 | `datetime('now')` |

**MCP tools (9 `text()` calls across 3 files):**

| File | Count | Primary pattern |
|------|-------|----------------|
| `mcp/tools/session.py` | 4 | `datetime('now')` |
| `mcp/tools/todos.py` | 3 | `date('now')` comparisons |
| `mcp/tools/system.py` | 2 | `datetime('now')` |

**Infrastructure (direct sqlite3 — no SA Core at all):**

| File | Issue |
|------|-------|
| `db/search.py` | Uses `sqlite3.connect()` directly — bypasses SA engine entirely |
| `services/event_bus.py` | Uses `sqlite3.connect()` directly — fire-and-forget writes |
| `db/init_db.py` | 1,035 lines raw DDL, `import sqlite3`, f-string SQL |
| `db/connections.py` | **Dead code** — zero importers anywhere in codebase |
| `db/tree_utils.py` | Imports sqlite3 |

---

## The Fix: Four categories

### Category 1: Date functions (70% of `text()` calls)

SQLite uses `datetime('now', '-7 days')`. PostgreSQL uses `NOW() - INTERVAL '7 days'`.

**Solution:** Create a dialect-aware date helper in `db/compat.py`:

```python
# backend/app/db/compat.py
from sqlalchemy import func, text
from app.db.engine import engine

_IS_SQLITE = "sqlite" in str(engine.url)

def now():
    """Current timestamp — dialect-aware."""
    if _IS_SQLITE:
        return func.datetime("now")
    return func.now()

def days_ago(n: int):
    """Timestamp N days in the past — dialect-aware."""
    if _IS_SQLITE:
        return func.datetime("now", f"-{n} days")
    return func.now() - text(f"INTERVAL '{n} days'")

def today():
    """Current date (no time) — dialect-aware."""
    if _IS_SQLITE:
        return func.date("now")
    return func.current_date()

def date_trunc_day(col):
    """Truncate timestamp to date — for GROUP BY day."""
    if _IS_SQLITE:
        return func.date(col)
    return func.date_trunc("day", col)
```

Then replace across all files:
```python
# BEFORE
.where(hub_todos.c.due_date < text("date('now')"))

# AFTER
from app.db.compat import today
.where(hub_todos.c.due_date < today())
```

### Category 2: Upserts (`INSERT OR REPLACE` → SA Core)

SQLite uses `INSERT OR REPLACE`. PostgreSQL uses `INSERT ... ON CONFLICT DO UPDATE`.

**Solution:** SA Core's dialect-aware insert:

```python
# BEFORE
conn.execute(text(
    "INSERT OR REPLACE INTO draft_decisions (id, hub_draft_id, status) "
    "VALUES (:id, :hid, :s)"
), params)

# AFTER
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
stmt = sqlite_insert(draft_decisions).values(id=id, hub_draft_id=hid, status=s)
stmt = stmt.on_conflict_do_update(
    index_elements=[draft_decisions.c.hub_draft_id],
    set_={"status": s}
)
conn.execute(stmt)
```

For PostgreSQL compatibility, add a helper:

```python
# backend/app/db/compat.py (addition)
from sqlalchemy.dialects import sqlite as sqlite_dialect, postgresql as pg_dialect

def upsert(table, values, conflict_columns, update_columns):
    """Dialect-aware upsert."""
    if _IS_SQLITE:
        stmt = sqlite_dialect.insert(table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={col: values[col] for col in update_columns}
        )
    else:
        stmt = pg_dialect.insert(table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={col: stmt.excluded[col] for col in update_columns}
        )
    return stmt
```

### Category 3: Full raw SQL queries (collaboration_context, jarvis)

These files have complete `text("SELECT ... FROM ... JOIN ...")` queries. Need full conversion to SA Core expressions.

### Category 4: Infrastructure bypass (search.py, event_bus.py)

These files use `sqlite3.connect()` directly, completely bypassing the SA Core engine. Need to be rewritten to use `get_db()`.

---

## Day 1: Helpers + Simple Files (50 `text()` calls)

### Morning: Create `db/compat.py` + delete dead code

1. **Create `backend/app/db/compat.py`** — dialect-aware date functions (`now()`, `days_ago(n)`, `today()`, `date_trunc_day(col)`) + upsert helper
2. **Delete `backend/app/db/connections.py`** — zero importers, confirmed dead code
3. **Migrate `db/tree_utils.py`** — replace `import sqlite3` with SA Core

### Afternoon: Migrate simple `text()` patterns (15 files, ~50 calls)

These files only use `text()` for date functions — mechanical find-and-replace:

| File | Calls | Change |
|------|-------|--------|
| `routers/costs.py` | 9 | `datetime('now', '-N days')` → `days_ago(N)` + `date_trunc_day()` |
| `routers/dashboard.py` | 9 | `datetime('now')` → `now()`, `text("d")` → column ref |
| `routers/home.py` | 9 | `datetime('now')` → `now()`, `text("d")` → column ref |
| `routers/content.py` | 9 | `datetime('now')` → `now()` |
| `routers/todos.py` | 9 | `date('now')` → `today()`, upserts → `compat.upsert()` |
| `routers/collaboration.py` | 4 | `datetime('now')` → `now()` |
| `routers/search.py` | 4 | `datetime('now')` → `now()` |
| `routers/tree.py` | 4 | `text("alias")` → SA column label references |
| `routers/drafts.py` | 2 | `INSERT OR REPLACE` → `compat.upsert()` |
| `routers/teams.py` | 2 | `datetime('now')` → `now()` |
| `routers/analysis.py` | 2 | `datetime('now')` → `now()` |
| `mcp/tools/session.py` | 4 | `datetime('now')` → `now()` |
| `mcp/tools/todos.py` | 3 | `date('now')` → `today()` |
| `mcp/tools/system.py` | 2 | `datetime('now')` → `now()` |
| `services/auto_classifier.py` | 2 | `datetime('now')` → `now()` |

**Test after each batch of 3-4 files.** Run existing test suite.

### End of Day 1:
- [ ] `compat.py` created and tested
- [ ] `connections.py` deleted
- [ ] 50 `text()` calls eliminated
- [ ] All existing tests pass

---

## Day 2: Complex Files (58 `text()` calls)

### Morning: Rewrite `collaboration_context.py` (16 calls)

This is the most `text()`-heavy service. Currently has 16 raw SQL queries that need full SA Core conversion.

Pattern: read its existing raw queries, rewrite as SA Core expressions using table imports from `tables.py`.

### Mid-day: Rewrite `jarvis.py` hub queries (12 calls)

`jarvis.py` has 12 `text()` calls — mostly full `SELECT` queries against hub mirror tables for building Jarvis context (todos, drafts, overdue items).

Convert each to SA Core:
```python
# BEFORE
rows = conn.execute(text(
    "SELECT t.id, t.title, t.status FROM hub_todos t WHERE t.status = 'open'"
)).fetchall()

# AFTER
rows = conn.execute(
    select(hub_todos.c.id, hub_todos.c.title, hub_todos.c.status)
    .where(hub_todos.c.status == "open")
).fetchall()
```

### Afternoon: Remaining services (12 calls)

| File | Calls | Change |
|------|-------|--------|
| `services/chat_context.py` | 2 | `datetime('now')` → `days_ago()` |
| `services/collaboration_context.py` | *(done in morning)* | |
| `services/folder_scanner.py` | 3 | `datetime('now')` → `now()` |
| `services/process_manager.py` | 2 | Status update text → SA Core update |
| `routers/chat.py` | 6 | Hub reads → SA Core expressions |

### End of Day 2:
- [ ] All 117 `text()` calls eliminated from routers, services, MCP tools
- [ ] `grep -r "text(" backend/app/routers/ backend/app/services/ backend/app/mcp/` returns zero hits for raw SQL
- [ ] All existing tests pass

---

## Day 3: Infrastructure Rewire

### Morning: Rewrite `search.py` (FTS5 abstraction)

Currently `search.py` uses `sqlite3.connect()` directly — completely bypasses SA Core.

**Rewrite to:**
```python
from app.db.session import get_db
from app.db.tables import hub_content
from app.db.engine import engine

_IS_SQLITE = "sqlite" in str(engine.url)

def search_content(query, limit=50, offset=0, source_filter=None):
    with get_db() as conn:
        if _IS_SQLITE:
            return _fts5_search(conn, query, limit, offset, source_filter)
        else:
            return _tsvector_search(conn, query, limit, offset, source_filter)

def _fts5_search(conn, query, limit, offset, source_filter):
    # Same FTS5 logic but through SA connection
    # Use text() here — FTS5 MATCH syntax has no SA Core equivalent
    # This is OK because it's behind a dialect check
    ...

def _tsvector_search(conn, query, limit, offset, source_filter):
    # PostgreSQL full-text search
    # hub_content needs a tsvector column (added in Alembic migration)
    ...
```

**Note:** FTS5 `MATCH` syntax has no SA Core equivalent. Using `text()` inside a `_IS_SQLITE` guard is acceptable — it's dialect-isolated.

### Mid-day: Rewrite `event_bus.py`

Currently uses `sqlite3.connect()` directly for fire-and-forget event persistence.

**Rewrite to use SA engine directly** (not `get_db()` — event writes should not participate in request transactions):

```python
from app.db.engine import engine
from app.db.tables import events

def _persist(event_data):
    """Fire-and-forget persist — separate connection, no request transaction."""
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(events.insert().values(**event_data))
    except Exception as e:
        log.warning("event_persist_failed", error=str(e))
```

Remove `import sqlite3` from event_bus.py.

### Afternoon: Slim down `init_db.py`

Current state: 1,035 lines of raw DDL. Much of this is now redundant because `tables.py` (707 lines) defines the same schema as SA Core metadata.

**Strategy:**
1. Replace `CREATE TABLE IF NOT EXISTS` blocks with `metadata.create_all(engine)`
2. Keep backward-compat ALTER TABLE migrations (add columns to existing DBs)
3. Keep seed data logic (default agent roles, workflow templates, hub project seeding)
4. Delete redundant DDL that duplicates `tables.py`

**Target:** Reduce init_db.py from 1,035 → ~400 lines (seed data + ALTER migrations).

### End of Day 3:
- [ ] `search.py` uses SA engine, dialect-aware FTS5/tsvector
- [ ] `event_bus.py` uses SA engine, no `import sqlite3`
- [ ] `init_db.py` uses `metadata.create_all()`, slimmed from 1,035 → ~400 lines
- [ ] `grep -r "import sqlite3" backend/app/` returns only `hub_sync.py` (intentional)
- [ ] All tests pass

---

## Day 4: PostgreSQL Validation + Regression Tests

### Morning: DATABASE_URL env var

**Modify `engine.py`:**
```python
import os
from app.config import PLATFORM_DB_PATH

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{PLATFORM_DB_PATH}")

engine = create_engine(DATABASE_URL, ...)

# Only set SQLite pragmas if actually using SQLite
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):
        ...
```

**Add `docker-compose.test.yml`:**
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: coco_test
      POSTGRES_USER: coco
      POSTGRES_PASSWORD: coco
    ports:
      - "5433:5432"
```

### Mid-day: Run full test suite against PostgreSQL

```bash
DATABASE_URL=postgresql://coco:coco@localhost:5433/coco_test pytest
```

Fix any remaining dialect issues:
- `datetime('now')` that slipped through → caught by `compat.py`
- `INSERT OR REPLACE` that slipped through → caught by `compat.upsert()`
- `LIKE` case sensitivity differences (SQLite case-insensitive, PostgreSQL case-sensitive)
- `BOOLEAN` handling (SQLite uses 0/1, PostgreSQL has native bool)

### Afternoon: Regression testing + f-string SQL audit

**Security audit:** Verify zero f-string SQL in routers/services:
```bash
grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE\|f"""SELECT' backend/app/routers/ backend/app/services/
```

Only `hub_sync.py` (intentional, reads hub.db) and `search.py` (inside dialect guard) should remain.

**Regression test checklist:**
- [ ] Dashboard loads with correct data
- [ ] Todo list shows hub todos with overrides applied
- [ ] Content search returns FTS5 results (SQLite) or tsvector results (PostgreSQL)
- [ ] Cost breakdown by day/project renders correctly
- [ ] Event SSE stream works
- [ ] Chat sends messages and persists history
- [ ] Agent spawn/stop lifecycle works
- [ ] Tree operations (create/move/delete node) work
- [ ] Jarvis context builds correctly from hub mirrors

### End of Day 4:
- [ ] `DATABASE_URL` env var works
- [ ] Test suite passes on SQLite
- [ ] Test suite passes on PostgreSQL
- [ ] Zero `text()` with raw SQL in routers/services (except dialect-guarded FTS5)
- [ ] Zero `import sqlite3` outside of `hub_sync.py`
- [ ] Zero f-string SQL outside of `hub_sync.py` and `search.py` (dialect-guarded)
- [ ] `docker-compose.test.yml` ready for CI

---

## Files Changed Summary

### Created (2 files)
| File | Purpose |
|------|---------|
| `backend/app/db/compat.py` | Dialect-aware helpers: `now()`, `days_ago()`, `today()`, `upsert()` |
| `docker-compose.test.yml` | PostgreSQL for testing |

### Deleted (1 file)
| File | Reason |
|------|--------|
| `backend/app/db/connections.py` | Dead code — zero importers |

### Rewritten (3 files)
| File | Change |
|------|--------|
| `backend/app/db/search.py` | SA engine + dialect-aware FTS5/tsvector |
| `backend/app/services/event_bus.py` | SA engine, remove `import sqlite3` |
| `backend/app/db/init_db.py` | `metadata.create_all()` + trimmed to ~400 lines |

### Modified (1 file)
| File | Change |
|------|--------|
| `backend/app/db/engine.py` | `DATABASE_URL` env var, conditional SQLite pragmas |

### Migrated — `text()` → SA Core (22 files)

**Routers (13):** costs, dashboard, home, content, todos, collaboration, search, tree, drafts, teams, analysis, jarvis, chat

**Services (6):** collaboration_context, chat_context, folder_scanner, process_manager, auto_classifier, event_bus

**MCP tools (3):** session, todos, system

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SA Core date functions produce different results than raw SQLite | Medium | Medium | Test date-heavy queries with known data; compare results pre/post migration |
| FTS5 search breaks after search.py rewrite | Medium | High | Keep LIKE fallback; test with real search queries from production |
| PostgreSQL test reveals many more dialect issues | High | Medium | Day 4 is dedicated to this; list is bounded (dates, upserts, booleans, case sensitivity) |
| init_db.py trim breaks existing database upgrade path | Medium | High | Test against a copy of real `~/.coco/platform.db` before deploying |
| Event bus rewrite drops events during high-frequency SSE | Low | Medium | Keep fire-and-forget pattern; just swap sqlite3 for SA engine |

---

## Success Metrics

After Sprint 6A, running these commands should confirm the migration:

```bash
# Zero raw SQL connections in app code (except hub_sync.py)
grep -r "import sqlite3" backend/app/ | grep -v hub_sync | grep -v __pycache__
# Expected: 0 results

# Zero raw SQL text() in routers/services (except dialect-guarded)
grep -rn "text(" backend/app/routers/ backend/app/services/ backend/app/mcp/ | grep -v "compat\." | grep -v "_IS_SQLITE" | grep -v "extract_action_items_from_text\|from_text\|text_content\|text_field"
# Expected: 0 results (after filtering function names containing "text")

# Dead code gone
test -f backend/app/db/connections.py && echo "FAIL: dead code remains" || echo "PASS"

# PostgreSQL works
DATABASE_URL=postgresql://coco:coco@localhost:5433/coco_test pytest
# Expected: all tests pass
```

---

## Relationship to Sprint 5.5

Sprint 5.5 as originally planned included migration work in Days 3-4. That work is now Sprint 6A. **Sprint 5.5 should be updated to be foundation-only (Days 1-2):**

- Sprint 5.5 (2 days): engine.py, session.py, tables.py, hub sync, Alembic ← **ALREADY DONE**
- Sprint 6A (4 days): migrate all `text()` calls, fix infrastructure, PostgreSQL validation ← **THIS SPRINT**
- Sprint 6 (10 days): Deep Intelligence (new features, all using SA Core from day one)

Since Sprint 5.5's foundation work is already in the codebase, Sprint 6A can start immediately after Sprint 5 completes.

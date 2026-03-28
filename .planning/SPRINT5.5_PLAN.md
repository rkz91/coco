# Sprint 5.5 Plan: "One Engine to Rule Them All"

**Date:** 2026-03-28
**Duration:** 4 days
**Prerequisites:** Sprint 5 complete
**Constraint:** Local SQLite testing for 2+ weeks before any PostgreSQL/cloud deployment

---

## The Problem

CoCo Platform uses raw `sqlite3` across **37 files** (24 routers, 10 services, 3 MCP tools). Every query is SQLite-dialect SQL. This blocks:

1. **Cloud deployment** — containers have ephemeral filesystems; need PostgreSQL
2. **Open-sourcing** — contributors expect `docker compose up` with PostgreSQL
3. **Hub coupling** — 14 files import `get_hub_db()` and read `hub.db` directly, tying the platform to KH's local SQLite file

## The Solution

```
BEFORE:                              AFTER:

Router → get_hub_db() → hub.db       Router → get_db() → SA Core engine
Router → get_platform_db() → plat.db                      ↓
                                                    SQLite (local)
                                                    PostgreSQL (cloud)

                                     Hub sync service: hub.db → hub_* tables
                                     (KH unchanged — still writes to hub.db)
```

---

## Blast Radius

### Files that import database functions (37 total)

**Hub + Platform (14 files — highest priority, need hub mirror migration):**
- `routers/chat.py` — `get_hub_db` (local import line 468)
- `routers/content.py` — `get_hub_db, get_platform_db`
- `routers/costs.py` — `get_hub_db, get_platform_db`
- `routers/dashboard.py` — `get_hub_db, get_platform_db`
- `routers/drafts.py` — `get_hub_db, get_platform_db`
- `routers/home.py` — `get_hub_db, get_platform_db`
- `routers/jarvis.py` — `get_hub_db, get_platform_db`
- `routers/projects.py` — `get_hub_db, get_platform_db`
- `routers/search.py` — `get_hub_db, get_platform_db`
- `routers/teams.py` — `get_hub_db, get_platform_db`
- `routers/templates.py` — `get_hub_db, get_platform_db`
- `routers/todos.py` — `get_hub_db, get_platform_db`
- `routers/tree.py` — `get_hub_db, get_platform_db`
- `services/auto_classifier.py` — `get_hub_db, get_platform_db`
- `services/chat_context.py` — `get_hub_db, get_platform_db`
- `services/collaboration_context.py` — `get_hub_db, get_platform_db`
- `mcp/tools/session.py` — `get_hub_db, get_platform_db`
- `mcp/tools/system.py` — `get_hub_db, get_platform_db`
- `mcp/tools/todos.py` — `get_hub_db, get_platform_db`

**Platform only (18 files — simpler, just swap connection):**
- `routers/activity.py`, `agents.py`, `analysis.py`, `chat.py`, `collaboration.py`, `comments.py`, `events.py`, `goals.py`, `inbox.py`, `tasks.py`, `triggers.py`
- `services/agent_sdk_client.py`, `delegation.py`, `id_generator.py`, `process_manager.py`, `self_improve.py`, `trigger_engine.py`, `verification.py`

### Hub.db tables read by the platform (7 tables)

| Hub table | Used by | Mirror as |
|-----------|---------|-----------|
| `todos` | todos, home, dashboard, teams, mcp/todos | `hub_todos` |
| `content` | content, search, drafts, chat_context, auto_classifier | `hub_content` |
| `projects` | projects, dashboard, home, teams, tree | `hub_projects` |
| `sync_state` | home, dashboard, health | `hub_sync_state` |
| `project_content` | content (join table) | `hub_project_content` |
| `api_costs` | costs | `hub_api_costs` |
| `drafts` | drafts, mcp/system | `hub_drafts` |

---

## Day 1: Foundation — SA Core Engine + Table Metadata

### Morning: Engine factory + connection manager

**New file: `backend/app/db/engine.py`**
```python
from sqlalchemy import create_engine, event
from app.config import DATABASE_URL  # default: "sqlite:///~/.coco/platform.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    # SQLite-specific: enable WAL + foreign keys via event listeners
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

**New file: `backend/app/db/session.py`**
```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from app.db.engine import engine

@contextmanager
def get_db():
    """Replaces both get_platform_db() and get_hub_db()."""
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Modify: `backend/app/db/connections.py`**
- Keep `get_hub_db()` and `get_platform_db()` but add deprecation warnings
- `get_platform_db()` delegates to `get_db()` internally
- `get_hub_db()` still opens hub.db directly (until Day 3 migrates to mirror tables)

**Modify: `backend/app/config.py`**
- Add `DATABASE_URL` from env var, default `f"sqlite:///{PLATFORM_DB_PATH}"`

### Afternoon: Table metadata definitions

**New file: `backend/app/db/tables.py`**

Define SA Core `Table` objects for all 37 platform.db tables + 7 hub mirror tables + 1 sync state table. Example:

```python
from sqlalchemy import MetaData, Table, Column, String, Integer, Float, Text, DateTime

metadata = MetaData()

# --- Platform tables ---
nodes = Table("nodes", metadata,
    Column("id", String, primary_key=True),
    Column("parent_id", String),
    Column("name", String, nullable=False),
    Column("node_type", String, nullable=False),
    Column("path", String),
    # ... all columns from init_db.py
)

agents = Table("agents", metadata, ...)
tasks = Table("tasks", metadata, ...)
cost_ledger = Table("cost_ledger", metadata, ...)
# ... all 37 tables

# --- Hub mirror tables ---
hub_todos = Table("hub_todos", metadata,
    Column("id", String, primary_key=True),
    Column("title", Text),
    Column("project_id", String),
    Column("owner", String),
    Column("due_date", String),
    Column("priority", String),
    Column("status", String),
    Column("source_type", String),
    Column("jira_key", String),
    Column("created_at", String),
    Column("completed_at", String),
    Column("tags", String),
)

hub_content = Table("hub_content", metadata, ...)
hub_projects = Table("hub_projects", metadata, ...)
hub_sync_state = Table("hub_sync_state", metadata, ...)
hub_project_content = Table("hub_project_content", metadata, ...)
hub_api_costs = Table("hub_api_costs", metadata, ...)
hub_drafts = Table("hub_drafts", metadata, ...)

# --- Sync watermark ---
hub_sync_watermark = Table("hub_sync_watermark", metadata,
    Column("table_name", String, primary_key=True),
    Column("last_synced_at", String),
    Column("last_rowid", Integer),
    Column("row_count", Integer),
)
```

### End of Day 1 deliverables:
- [ ] `engine.py` — SA Core engine from `DATABASE_URL`
- [ ] `session.py` — `get_db()` context manager
- [ ] `tables.py` — all 37 + 7 mirror + 1 watermark table definitions
- [ ] `config.py` — `DATABASE_URL` env var
- [ ] `connections.py` — backward compat with deprecation warnings
- [ ] All existing tests still pass (no behavior change yet)

---

## Day 2: Hub Sync Service + Alembic Update

### Morning: Hub sync service

**New file: `backend/app/services/hub_sync.py`**

```python
class HubSyncService:
    """Reads hub.db (read-only), mirrors into platform DB hub_* tables."""

    SYNC_INTERVAL = 60  # seconds

    HUB_TO_MIRROR = {
        "todos": hub_todos,
        "content": hub_content,
        "projects": hub_projects,
        "sync_state": hub_sync_state,
        "project_content": hub_project_content,
        "api_costs": hub_api_costs,
        "drafts": hub_drafts,
    }

    async def start(self):
        """Background task — runs every 60s."""
        await self._initial_sync()
        while True:
            await asyncio.sleep(self.SYNC_INTERVAL)
            await self._delta_sync()

    async def _initial_sync(self):
        """Full copy on first run or empty mirror tables."""
        # Open hub.db read-only via sqlite3 (NOT SA — hub.db stays raw)
        # For each table: SELECT * → bulk INSERT into hub_* mirror
        # Write watermark with current rowid/timestamp

    async def _delta_sync(self):
        """Incremental sync since last watermark."""
        # For each table:
        #   Read watermark (last_rowid, last_synced_at)
        #   SELECT from hub.db WHERE rowid > last_rowid OR updated_at > last_synced_at
        #   UPSERT into hub_* mirror table
        #   Update watermark
```

**Modify: `backend/app/main.py`**
- Add `hub_sync_service` to lifespan startup
- Background task via `asyncio.create_task(hub_sync.start())`

### Afternoon: Alembic migration update

**Modify: `backend/alembic/env.py`**
- Import `metadata` from `app.db.tables`
- Set `target_metadata = metadata`
- Read `DATABASE_URL` from env/config

**New migration: `backend/alembic/versions/002_hub_mirror_tables.py`**
- Creates 7 `hub_*` mirror tables + `hub_sync_watermark`
- Idempotent (IF NOT EXISTS)
- Downgrade drops them

**Modify: `backend/app/db/init_db.py`**
- Add `metadata.create_all(engine)` call alongside existing raw DDL
- Existing raw DDL kept for backward compat during transition
- Add hub mirror table creation

### End of Day 2 deliverables:
- [ ] Hub sync service runs on startup, mirrors all 7 hub tables
- [ ] Delta sync runs every 60s, only syncs changed rows
- [ ] Alembic generates correct migrations for both SQLite and PostgreSQL
- [ ] Hub mirror tables populated and queryable
- [ ] `docker-compose.yml` with PostgreSQL (for CI testing)

---

## Day 3: Migrate Hub Readers (14 files)

The goal: eliminate all `get_hub_db()` calls. Every hub.db read becomes a read from `hub_*` mirror tables via `get_db()`.

### Migration pattern per file:

```python
# BEFORE
from app.db.connections import get_hub_db, get_platform_db

def get_todos():
    with get_hub_db() as hub:
        rows = hub.execute("SELECT id, title, status FROM todos WHERE status = ?", ("open",)).fetchall()
    with get_platform_db() as pdb:
        overrides = pdb.execute("SELECT hub_todo_id, status FROM todo_overrides").fetchall()
    # merge...

# AFTER
from app.db.session import get_db
from app.db.tables import hub_todos, todo_overrides

def get_todos():
    with get_db() as conn:
        rows = conn.execute(
            hub_todos.select().where(hub_todos.c.status == "open")
        ).fetchall()
        overrides = conn.execute(
            todo_overrides.select()
        ).fetchall()
    # merge... (same logic, single connection)
```

### File migration order (by dependency — leaf files first):

**Batch 1 (morning — 6 files, simpler reads):**
1. `routers/projects.py` — hub reads: `projects` table
2. `routers/costs.py` — hub reads: `api_costs` table
3. `routers/drafts.py` — hub reads: `drafts` table
4. `routers/todos.py` — hub reads: `todos` table
5. `mcp/tools/todos.py` — hub reads: `todos` table
6. `mcp/tools/system.py` — hub reads: `projects`, `sync_state`

**Batch 2 (afternoon — 8 files, complex joins/search):**
7. `routers/dashboard.py` — hub reads: multiple tables for dashboard aggregation
8. `routers/home.py` — hub reads: multiple tables for home page
9. `routers/content.py` — hub reads: `content`, `project_content` (FTS5 search)
10. `routers/search.py` — hub reads: `content` (FTS5)
11. `routers/teams.py` — hub reads: `projects`, `todos`
12. `routers/tree.py` — hub reads: `projects`
13. `routers/templates.py` — hub reads: `projects`
14. `routers/chat.py` — hub read in line 468 (local import)

**Batch 3 (services — can overlap):**
15. `services/auto_classifier.py`
16. `services/chat_context.py`
17. `services/collaboration_context.py`
18. `mcp/tools/session.py`
19. `routers/jarvis.py`

### FTS5 migration note

`content_fts` is an FTS5 virtual table in hub.db. FTS5 is SQLite-specific and won't work in PostgreSQL. Strategy:

- **SQLite mode:** Mirror the FTS5 table as-is into platform.db. FTS5 works in platform.db too.
- **PostgreSQL mode:** Create a `hub_content_search` table with a `tsvector` column. Populate via trigger on `hub_content` inserts. Use `to_tsvector()` / `to_tsquery()` for search.
- **Abstraction:** `backend/app/db/search.py` provides `search_content(query)` that dispatches to FTS5 or tsvector based on dialect.

### End of Day 3 deliverables:
- [ ] All 19 `get_hub_db()` callers migrated to `hub_*` mirror reads
- [ ] `get_hub_db()` function has zero callers (can mark as deprecated/unused)
- [ ] Single `get_db()` connection for all database reads
- [ ] FTS5 search still works via mirror table (SQLite) or tsvector (PostgreSQL)
- [ ] All tests pass

---

## Day 4: Migrate Platform Writers + Integration Tests

### Morning: Migrate platform-only files (18 files)

These files only use `get_platform_db()` — simpler migration (just swap connection + rewrite SQL to SA Core).

**Batch 4 (10 routers):**
1. `routers/activity.py`
2. `routers/agents.py`
3. `routers/analysis.py`
4. `routers/chat.py` (platform writes)
5. `routers/collaboration.py`
6. `routers/comments.py`
7. `routers/events.py`
8. `routers/goals.py`
9. `routers/inbox.py`
10. `routers/tasks.py`
11. `routers/triggers.py`

**Batch 5 (7 services):**
12. `services/agent_sdk_client.py`
13. `services/delegation.py`
14. `services/id_generator.py`
15. `services/process_manager.py` (also imports `_connect` directly — fix)
16. `services/self_improve.py`
17. `services/trigger_engine.py`
18. `services/verification.py`

### Afternoon: Integration tests + cleanup

**New file: `backend/tests/conftest.py` update**
- Add `--db` flag: `sqlite` (default) or `postgres`
- For postgres: spin up test database, run migrations, tear down
- For sqlite: use temp file (existing behavior)

**New file: `backend/tests/test_hub_sync.py`**
- Test initial sync populates all mirror tables
- Test delta sync picks up new rows
- Test watermark advances correctly
- Test sync handles hub.db being locked/missing gracefully

**New file: `backend/tests/test_db_abstraction.py`**
- Test that `get_db()` returns working connection for both dialects
- Test that SA Core queries produce correct results on both
- Test FTS5 (SQLite) and tsvector (PostgreSQL) search parity

**Cleanup:**
- Remove `get_hub_db()` from `connections.py` (or leave as no-op with error)
- Remove all `import sqlite3` from routers (should only remain in `hub_sync.py` for reading hub.db)
- Update `init_db.py` to use `metadata.create_all()` as primary, raw DDL as fallback
- Add startup check: if `hub_sync_watermark` is empty, run initial sync before serving requests

**CI configuration:**
- `docker-compose.test.yml` — PostgreSQL for CI
- GitHub Actions matrix: `pytest --db=sqlite` + `pytest --db=postgres`

### End of Day 4 deliverables:
- [ ] Zero `import sqlite3` in any router or service (except `hub_sync.py`)
- [ ] Zero `get_hub_db()` or `get_platform_db()` callers
- [ ] All queries use SA Core via `get_db()`
- [ ] Test suite passes against SQLite
- [ ] Test suite passes against PostgreSQL (CI)
- [ ] Hub sync service tested (initial, delta, error handling)
- [ ] `docker-compose.yml` ready for future cloud use

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SA Core SQL not 100% compatible with existing raw SQL logic | Medium | Medium | Migrate one file at a time; run tests after each batch |
| FTS5 → tsvector parity issues (different ranking algorithms) | Medium | Low | Accept minor search result ordering differences; test with real queries |
| Hub sync initial load slow with large hub.db | Low | Low | hub.db has ~1800 items — initial sync is <1s |
| Hub sync race condition (sync writes while router reads) | Low | Medium | SA Core handles connection-level isolation; WAL mode on SQLite |
| `process_manager.py` imports `_connect` directly | High | Medium | Fix on Day 4 — replace with SA engine |
| Alembic migration fails on existing platform.db | Medium | High | Test against a copy of real ~/.coco/platform.db before running |

---

## What does NOT change

- `~/.hub/hub.db` — KH still owns this, schema unchanged, writes unchanged
- `~/.coco/brain.json`, `queue.json`, `config.json` — JSON files stay as-is
- KH MCP tools — still read/write hub.db directly
- `think.py` — still reads hub.db directly
- Frontend — zero changes (API contracts unchanged)
- API contracts — all endpoints return same JSON shapes

---

## Success Criteria

1. `DATABASE_URL=sqlite:///~/.coco/platform.db` — works identically to pre-migration (no regressions)
2. `DATABASE_URL=postgresql://coco:coco@localhost/coco` — all endpoints work
3. Hub sync mirrors hub.db → hub_* tables within 60 seconds
4. `grep -r "import sqlite3" backend/app/routers/` returns zero results
5. `grep -r "get_hub_db" backend/app/` returns only `connections.py` (deprecated stub)
6. Existing `~/.coco/platform.db` data survives migration (no data loss)
7. 2 weeks of local SQLite testing before any PostgreSQL deployment

---

## Post-Sprint: What changes for Sprints 6-12

All new code from Sprint 6 onward uses SA Core:

```python
# Sprint 6+ pattern
from app.db.session import get_db
from app.db.tables import hub_todos, todo_overrides, queue_items

with get_db() as conn:
    result = conn.execute(
        hub_todos.select()
        .where(hub_todos.c.status == "open")
        .order_by(hub_todos.c.priority.desc())
    ).fetchall()
```

No more raw SQL strings. No more `sqlite3` imports. DB-agnostic from day one.

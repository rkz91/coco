# Sprint 6 Plan: "Deep Intelligence"

**Date:** 2026-03-28
**Duration:** 10 days
**Prerequisites:** Sprint 4 (Agent SDK Week 1) + Sprint 5 (MCP server + verification gates)

---

## Workstream 1: Agent SDK Completion (Days 1-3)

### Day 1: Session Persistence and Recovery

**New file:** `backend/app/services/agent_session_store.py` — SDK session persistence. Maps agent_id to SDK session state (conversation ID, message history, checkpoints).

**Schema addition:**
```sql
CREATE TABLE IF NOT EXISTS agent_sessions (
    agent_id TEXT PRIMARY KEY REFERENCES agents(id),
    sdk_session_id TEXT,
    conversation_id TEXT,
    checkpoint_data TEXT,
    message_count INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    last_checkpoint_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Endpoints:**
- `GET /api/agents/{id}/session` — session metadata
- `POST /api/agents/{id}/resume` — resume from checkpoint

### Day 2: Subagent Support

**New file:** `backend/app/services/subagent_manager.py` — parent-child agent relationships. When SDK agent uses `create_agent`, CoCo registers child in platform.db, assigns to same node, tracks cost under parent budget.

**Endpoints:**
- `GET /api/agents/{id}/subagents` — list children
- `POST /api/agents/{id}/subagents` — spawn child (body: `{task, model, role?}`)
- Hard cap: max 3 subagents per parent

### Day 3: Edge Cases + Feature Flag Removal

- Rate limit 429 with exponential backoff + budget check
- Context window overflow with graceful truncation
- Model fallback (opus → sonnet) on repeated failures
- Remove `COCO_USE_AGENT_SDK` feature flag (SDK becomes default)
- Wire real token counts into cost_ledger
- Remove old subprocess code path from chat.py

---

## Workstream 2: Cross-Source Insight Engine (Days 4-6)

### Day 4: Entity Extraction Service

**New file:** `backend/app/services/entity_extractor.py`
- Two modes: regex/heuristic (instant) + LLM/Haiku (deep)
- Extracts: person, project, date, decision, action_item, topic
- Returns typed entities with confidence scores

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT,
    confidence REAL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}',
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    insight_type TEXT NOT NULL,  -- cross_reference, pattern, contradiction, escalation
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    confidence REAL DEFAULT 0.0,
    entity_ids TEXT NOT NULL,
    content_ids TEXT NOT NULL,
    sources TEXT NOT NULL,
    status TEXT DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Endpoints:**
- `GET /api/entities?content_id=X&type=person`
- `POST /api/entities/extract` — single content item
- `POST /api/entities/extract-batch` — bulk

### Day 5: FTS Similarity + Insight Generation

**New file:** `backend/app/services/insight_engine.py`
- Entity co-occurrence across 2+ sources → `cross_reference` insight
- FTS similarity via `content_fts` BM25 scoring
- Temporal proximity (48h window + shared person/topic)

**New file:** `backend/app/routers/insights.py`

**Endpoints:**
- `GET /api/insights?type=X&status=new&limit=20`
- `GET /api/insights/{id}` — detail with linked entities
- `POST /api/insights/{id}/action` — seen/actioned/dismissed
- `POST /api/insights/generate` — trigger cycle
- `GET /api/insights/summary` — aggregate stats

### Day 6: Frontend

**New files:**
- `frontend/src/components/knowledge/InsightCard.tsx` — title, description, source badges, confidence, entity pills, actions
- `frontend/src/components/knowledge/InsightPanel.tsx` — filterable list
- `frontend/src/components/knowledge/EntityGraph.tsx` — relationship visualization

**Modified:**
- `KnowledgePage.tsx` — add "Insights" tab
- `HomePage.tsx` — add insights card

---

## Workstream 3: Content-to-Action Pipeline (Days 7-8)

### Day 7: LLM-Powered Extraction

**New file:** `backend/app/services/action_pipeline.py`
- Haiku structured JSON output: `{action_items, decisions, follow_ups}`
- Stages results in `staged_actions` table
- YOLO mode: auto-creates todos. Careful mode: stages for review.

**New file:** `backend/app/routers/actions.py`

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS staged_actions (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    assignee TEXT,
    due_date TEXT,
    priority TEXT DEFAULT 'medium',
    source_quote TEXT,
    confidence REAL DEFAULT 0.0,
    status TEXT DEFAULT 'staged',
    created_todo_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Endpoints:**
- `POST /api/actions/process` — process single content item
- `POST /api/actions/process-batch` — all unprocessed today
- `GET /api/actions/staged?status=staged` — review list
- `POST /api/actions/{id}/approve` — creates todo
- `POST /api/actions/{id}/reject`
- `POST /api/actions/approve-all` — YOLO shortcut

### Day 8: Frontend + Integration

**New files:**
- `frontend/src/components/knowledge/ActionReviewPanel.tsx` — source on left, actions on right
- `frontend/src/components/knowledge/ActionBadge.tsx` — pending count

**Modified:**
- `ContentDetail.tsx` — "Extract Actions" button
- `ContentList.tsx` — action badge overlay
- `InboxPage.tsx` — "Pending Actions" section

---

## Workstream 4: Self-Improvement with Gates (Days 9-10)

### Day 9: Verification Gate Service

**New file:** `backend/app/services/verification.py`
- `run_gate(gate_name, input_data, output_data, node_id) -> GateResult`
- Spawns 2-3 verifier agents in parallel
- G1 (Ideation), G2 (Plan), G3 (Implementation), G4 (Acceptance)
- Uses Sonnet for verifiers, cap 10K input + 2K output per gate

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS verification_results (
    id TEXT PRIMARY KEY,
    gate_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    score REAL DEFAULT 0.0,
    issues TEXT DEFAULT '[]',
    verifier_results TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Wire into self_improve.py:** G1 after PM, G2 after Architect, G3 after Dev+Test, G4 before human approval

### Day 10: Hardening + Testing

- Stale worktree cleanup (>24h from failed cycles)
- Disk space check before worktree creation
- Concurrent merge prevention (lock file)
- Budget tracking: abort if spent >= budget
- Frontend: gate badges on stage stepper, issues in ImprovementCard

---

## New Files Summary

| File | Description |
|------|-------------|
| `backend/app/services/agent_session_store.py` | SDK session persistence |
| `backend/app/services/subagent_manager.py` | Parent-child agent management |
| `backend/app/services/entity_extractor.py` | Named entity extraction |
| `backend/app/services/insight_engine.py` | Cross-source insight generation |
| `backend/app/services/action_pipeline.py` | LLM content-to-action extraction |
| `backend/app/services/verification.py` | Reusable verification gates (G1-G4) |
| `backend/app/routers/insights.py` | Insights CRUD |
| `backend/app/routers/actions.py` | Action pipeline endpoints |
| `frontend/src/components/knowledge/InsightCard.tsx` | Insight display |
| `frontend/src/components/knowledge/InsightPanel.tsx` | Insights list |
| `frontend/src/components/knowledge/EntityGraph.tsx` | Entity visualization |
| `frontend/src/components/knowledge/ActionReviewPanel.tsx` | Action review UI |
| `frontend/src/components/knowledge/ActionBadge.tsx` | Pending action badge |

## Schema Changes: 5 new tables
- `agent_sessions` — SDK session persistence
- `entities` — extracted named entities
- `insights` — cross-source insights
- `staged_actions` — LLM-extracted actions awaiting review
- `verification_results` — gate outcomes

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Sprint 4/5 SDK not complete | High | Critical | Day 1-3 handles remaining SDK work |
| LLM extraction quality | Medium | Medium | Few-shot examples + confidence threshold 0.7 |
| Entity extraction false positives | Medium | Low | Start regex-only, LLM opt-in |
| Verification gates consume tokens | Medium | High | Sonnet verifiers, 10K token budget per gate |
| Subagent explosion | Low | High | Hard cap 3 per parent, inherits budget |

---

## Sprint 5.5 Compatibility Addendum

> Sprint 5.5 introduces SQLAlchemy Core + hub mirror tables. All new code in Sprint 6+ MUST use SA Core, not raw sqlite3.

### Schema changes (5 tables → SA Core definitions in `tables.py`)

| Raw SQL in this plan | SA Core replacement |
|---|---|
| `CREATE TABLE agent_sessions` (line 17) | `agent_sessions = Table("agent_sessions", metadata, ...)` in `tables.py` |
| `CREATE TABLE entities` (line 65) | `entities = Table("entities", metadata, ...)` in `tables.py` |
| `CREATE TABLE insights` (line 77) | `insights = Table("insights", metadata, ...)` in `tables.py` |
| `CREATE TABLE staged_actions` (line 138) | `staged_actions = Table("staged_actions", metadata, ...)` in `tables.py` |
| `CREATE TABLE verification_results` (line 188) | `verification_results = Table("verification_results", metadata, ...)` in `tables.py` |

### Connection pattern changes

All new files use `get_db()` from `app.db.session`, NOT `get_platform_db()` or `get_hub_db()`:

```python
# CORRECT (Sprint 6+ pattern)
from app.db.session import get_db
from app.db.tables import entities, insights

with get_db() as conn:
    conn.execute(entities.insert().values(id=eid, content_id=cid, ...))

# WRONG (pre-5.5 pattern — do not use)
from app.db.connections import get_platform_db
with get_platform_db() as db:
    db.execute("INSERT INTO entities ...")
```

### FTS5 / search queries

Entity extraction (Day 4) and insight engine (Day 5) use `content_fts` for BM25 search. After Sprint 5.5:
- **SQLite mode:** Query `hub_content` mirror table's FTS5 index (rebuilt during hub sync)
- **PostgreSQL mode:** Use `to_tsvector()` / `to_tsquery()` via `search_content()` helper in `app.db.search`

### Hub reads

`entity_extractor.py` and `insight_engine.py` read from `content` table. After Sprint 5.5, read from `hub_content` mirror table instead of `get_hub_db()`.

# Sprint 7 Plan: "Self-Improvement + Replay"

**Date:** 2026-03-28
**Duration:** 10 days
**Prerequisites:** Sprint 6

---

## Workstream A: Self-Improve Frontend Polish (Days 1-3)

### Day 1: Enhanced DiffViewer
- Side-by-side diff mode (unified toggle retained)
- File tabs for multi-file diffs
- Syntax highlighting via Prism.js (already bundled)

### Day 2: AgentActivityPanel
- Live SSE updates for in-progress self-improvement cycles
- StageStepper animation (analyze → plan → apply → verify)
- Collapse/expand per-stage detail

### Day 3: CycleAnalytics
- CycleAnalytics component — bar chart of cycle history (files changed, cost, duration)
- Analytics API endpoint (`GET /api/self-improve/analytics`)
- Date range filter, per-cycle drill-down

### Files

| New | Modified |
|-----|----------|
| `frontend/src/components/self-improve/AgentActivityPanel.tsx` | `frontend/src/pages/SelfImprovePage.tsx` |
| `frontend/src/components/self-improve/AutoScheduleSettings.tsx` | `frontend/src/components/self-improve/DiffViewer.tsx` |
| `frontend/src/components/self-improve/CycleAnalytics.tsx` | `backend/app/routers/self_improve.py` (analytics endpoint) |

---

## Workstream B: Self-Triggered Cron + Decision Queue (Days 4-5)

### Day 4: Weekly Auto-Trigger
- Weekly auto-trigger via `trigger_engine` (cron `0 3 * * 1` — Monday 3 AM)
- `auto_start_cycle()` function — checks last cycle age, skips if recent
- Preferences API for enable/disable, cron expression, max cost per cycle

### Day 5: Inbox + Jarvis Integration
- Improvements pushed to Jarvis voice queue ("I improved 3 files overnight")
- Inbox integration — improvement summary card in decision queue
- Home briefing count badge ("2 self-improvements this week")

### Files

| New | Modified |
|-----|----------|
| `backend/app/services/self_improve_scheduler.py` | `backend/app/routers/self_improve.py` |
| | `backend/app/services/trigger_engine.py` |
| | `backend/app/routers/jarvis.py` |
| | `backend/app/routers/inbox.py` |
| | `backend/app/routers/home.py` |

---

## Workstream C: Agent Replay — THE VIRAL FEATURE (Days 6-8)

### Day 6: ReplayService + API
- `ReplayService` — parse `stream-json` output from `agent_output` into structured timeline events
- Replay API endpoints: `GET /api/replays`, `POST /api/replays`, `DELETE /api/replays/{id}`, `GET /api/replays/share/{token}`
- DB table: `agent_replays`

### Day 7: Self-Contained HTML Template
- Single HTML file, zero external dependencies, works offline
- Timeline scrubber (play/pause/seek)
- File diff viewer with inlined Prism.js for syntax highlighting
- Cost tracker (running total as replay progresses)
- "Built with CoCo" branding footer
- Cap at 1000 events to keep file size manageable

### Day 8: Frontend + Sharing
- `ReplayPage.tsx` — full-page replay viewer (embedded HTML or native)
- `ReplayList.tsx` — list of generated replays per agent
- "Generate Replay" button on completed agent detail pages
- Share tokens — unique URL per replay, publicly accessible without auth

### Schema

```sql
CREATE TABLE agent_replays (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    title       TEXT NOT NULL,
    duration    REAL,
    event_count INTEGER,
    cost        REAL,
    files_changed INTEGER,
    share_token TEXT UNIQUE,
    html_path   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

### Files

| New | Modified |
|-----|----------|
| `backend/app/services/replay.py` | Existing agent detail pages |
| `backend/app/routers/replay.py` | |
| `backend/app/models/replay.py` | |
| `backend/app/templates/replay.html` | |
| `frontend/src/pages/ReplayPage.tsx` | |
| `frontend/src/components/replay/ReplayList.tsx` | |
| `frontend/src/components/replay/ReplayPreview.tsx` | |

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/replays` | List all replays (filterable by agent_id) |
| `POST` | `/api/replays` | Generate replay for a completed agent |
| `DELETE` | `/api/replays/{id}` | Delete a replay and its HTML file |
| `GET` | `/api/replays/share/{token}` | Public share — serves the HTML file |

---

## Workstream D: Morning Podcast Briefing (Days 9-10)

### Day 9: PodcastService + Backend
- Overnight data aggregation (completed agents, inbox decisions, cost summary, calendar, todos due)
- Haiku script generation — conversational 2-3 minute briefing script
- TTS synthesis via Kokoro (local, preferred) or Edge TTS (fallback)
- Cron: `0 7 * * 1-5` (weekday mornings at 7 AM)

### Day 10: Frontend + Notifications
- `PodcastPlayer.tsx` on HomePage — compact audio player with waveform visualization
- Script viewer (read along while listening)
- SSE notification on `podcast.ready` event
- macOS desktop notification via `osascript`

### Schema

```sql
CREATE TABLE podcasts (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    script     TEXT,
    audio_path TEXT,
    duration   REAL,
    voice      TEXT DEFAULT 'kokoro',
    status     TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Files

| New | Modified |
|-----|----------|
| `backend/app/services/podcast.py` | `backend/app/routers/home.py` |
| `backend/app/routers/podcast.py` | |
| `backend/app/models/podcast.py` | |
| `frontend/src/components/home/PodcastPlayer.tsx` | |
| `frontend/src/components/home/PodcastCard.tsx` | |

---

## Summary

| Metric | Count |
|--------|-------|
| New files | 14 |
| Modified files | 12 |
| New DB tables | 2 (`agent_replays`, `podcasts`) |
| New API endpoints | ~8 |

## Risk Register

### Risk 1: `stream-json` format changes across Claude versions

**Mitigations:**
- Detect CLI version at agent spawn (`claude --version`), store in `agent_runs` table
- Versioned parser registry — each parser handles a known schema shape
- Unknown event types stored raw (`type: "unknown"`), never dropped
- `replay_schema_version` field on `agent_replays` for backward compat
- Integration test with fixture file per known CLI version

### Risk 2: TTS quality degrades on long scripts

**Mitigations:**
- Sentence-boundary chunking — split at `.` `!` `?`, max 200 chars per chunk
- Silence insertion — 300ms between chunks, 600ms between sections
- Hard cap at 3 minutes (~450 words), truncate gracefully
- Quality gate — if audio duration off by >20% from expected, fall back to Edge TTS

### Risk 3: Replay HTML file size too large

**Mitigations:**
- Event cap 1000 + diff content cap 500KB
- Virtual scroll — only render visible timeline window
- Diff compression — store unified format, expand client-side
- Prism.js subset — JS/TS/Python/CSS only (~40KB vs ~200KB)
- Auto-summarize if pre-gzip > 2MB (collapse consecutive low-signal events)
- Share endpoint serves with `Content-Encoding: gzip`

---

## Sprint 5.5 Compatibility Addendum

> Sprint 5.5 introduces SQLAlchemy Core + hub mirror tables. All new code in Sprint 7+ MUST use SA Core, not raw sqlite3.

### Schema changes (2 tables → SA Core definitions in `tables.py`)

| Raw SQL in this plan | SA Core replacement |
|---|---|
| `CREATE TABLE agent_replays` (line 83) | `agent_replays = Table("agent_replays", metadata, ...)` in `tables.py` |
| `CREATE TABLE podcasts` (line 137) | `podcasts = Table("podcasts", metadata, ...)` in `tables.py` |

### Connection pattern changes

`replay.py` and `podcast.py` services use `get_db()` from `app.db.session`:

```python
from app.db.session import get_db
from app.db.tables import agent_replays, podcasts

with get_db() as conn:
    conn.execute(agent_replays.insert().values(...))
```

### Hub reads

`podcast.py` aggregation (Day 9 — "overnight data: completed agents, inbox decisions, cost summary, todos due") reads from `hub_todos` and `hub_content` mirror tables, not `get_hub_db()` directly.

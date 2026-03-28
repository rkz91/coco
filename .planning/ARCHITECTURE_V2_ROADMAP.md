# CoCo Platform — Architecture V2 Roadmap

**Version:** 1.0
**Date:** 2026-03-28
**Author:** Rijul Kalra / Claude Opus 4.6 (Senior Architect Review)
**Status:** Draft — awaiting review

---

## Table of Contents

1. [Current Architecture Assessment](#1-current-architecture-assessment)
2. [Current System Data Flow](#2-current-system-data-flow)
3. [Recommended Architecture for V2](#3-recommended-architecture-for-v2)
4. [Event-Driven Architecture](#4-event-driven-architecture)
5. [State Management](#5-state-management)
6. [Offline Support](#6-offline-support)
7. [Extension System Design](#7-extension-system-design)
8. [Security Architecture](#8-security-architecture)
9. [Monitoring and Observability](#9-monitoring-and-observability)
10. [Migration Path](#10-migration-path)

---

## 1. Current Architecture Assessment

### What's Good

**1. Clean separation of data ownership.**
The dual-database pattern (hub.db read-only, platform.db read-write) is a sound boundary. It prevents the platform from corrupting Knowledge Hub data and allows both systems to evolve independently. The `?mode=ro` URI enforcement in `connections.py` is a hard guarantee, not just convention.

**2. Process isolation for agents.**
The `ProcessManager` spawns Claude Code as real OS processes with sanitized environments (`_ALLOWED_ENV_KEYS` whitelist), proper timeout enforcement, and orphan reconciliation on startup. This is production-grade subprocess management -- not a toy wrapper.

**3. SSE architecture is appropriate.**
The `EventBus` (asyncio.Queue per subscriber, slow-consumer eviction, dead-queue cleanup) is simple and correct for a single-user local app. The frontend `useEventSource` hook handles reconnection with exponential backoff and jitter. SSE over WebSocket is the right call for unidirectional push.

**4. Collaboration context system.**
`collaboration_context.py` builds structured prompts from project context, handoffs, and workflow state -- giving agents situational awareness. The auto-capture pipeline (output -> project_context -> workflow advancement -> todo extraction) is a genuine workflow engine, not just logging.

**5. Atomic JSON writes.**
The tmp-then-rename pattern for brain.json/queue.json/config.json handles concurrent access with think.py correctly. Advisory locking adds another safety layer.

**6. Scope-based tree hierarchy.**
`ScopeContext.tsx` with its tree walker, ancestor resolution, and `scopeProjectIds` gives the frontend a natural way to filter data by organizational hierarchy. LocalStorage persistence of selected node is a nice UX touch.

### What's Concerning

**1. In-process threading for agent I/O.**
`ProcessManager._read_output` runs in daemon threads, each opening its own SQLite connection. This works but is fragile:
- Thread-local connections bypass any connection pooling or lifecycle management.
- If the FastAPI process crashes, all in-flight agent output between the last commit and crash is lost.
- The 10-line / 2-second batch commit heuristic is ad hoc -- no backpressure if agents produce output faster than SQLite can commit.

**2. No service layer abstraction.**
Business logic lives directly in routers (26 router files) or in service files that directly import `get_platform_db()`. There's no dependency injection, no repository pattern, no unit-testable service boundaries. Testing requires a real SQLite database.

**3. Event bus is ephemeral.**
`EventBus` is purely in-memory. If no SSE client is connected, events are silently dropped. There's no event persistence, no replay capability, and no way to audit what events were emitted. The `events.jsonl` file exists but is a separate mechanism -- the event bus doesn't write to it.

**4. No structured error handling.**
The API layer (`api.ts`) throws `ApiError` with raw text bodies. There's no standardized error envelope (e.g., `{error: string, code: string, details: object}`). Backend exception handlers are missing -- unhandled exceptions produce generic 500 responses.

**5. hub.db write violation in collaboration_context.py.**
`_create_todos_from_agent_output` (line 169-221) opens a direct `sqlite3.connect(str(HUB_DB_PATH))` in read-write mode to INSERT into the `todos` table. This violates the "hub.db is read-only" principle stated in ARCHITECTURE.md and risks write contention with the Knowledge Hub MCP server.

**6. Configuration is minimal.**
`config.py` is 20 lines of hardcoded defaults with env var overrides. There's no validation, no schema, no hot-reload capability. Adding a new config value requires a code change.

**7. No health metrics beyond heartbeat.**
The only liveness signal is `last_heartbeat` on agents. There's no CPU/memory monitoring (psutil is imported but not used for metrics), no request latency histograms, no error rate tracking, no disk space checks for SQLite.

**8. Frontend state is split without clear boundaries.**
The app uses both TanStack Query (for server state) and React Context (ScopeContext for tree state), but there's no Zustand store despite the architecture doc specifying one per domain. This leaves no client-side cache for cross-component coordination beyond TanStack Query's cache.

---

## 2. Current System Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL INPUTS                               │
│  Email │ Voice │ Jira │ Confluence │ Calendar │ File drops              │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                  KNOWLEDGE HUB (MCP Server)                    │
│  Adapters → Pipeline (ingest→preprocess→triage→classify→synth)│
│  Writes → hub.db (content, projects, drafts, todos, costs)    │
└───────────────────────────┬───────────────────────────────────┘
                            │
              ┌─────────────┼──────────────┐
              │             │              │
              ▼             ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│  think.py    │  │   CoCo CLI   │  │   CoCo Platform (FastAPI)│
│  (launchd    │  │  (terminal)  │  │   (localhost:8000)       │
│   cron)      │  │              │  │                          │
│              │  │  ~/.claude/  │  │  ┌─────────┐            │
│  Reads:      │  │  skills/     │  │  │ Routers │ (26 files) │
│  - hub.db RO │  │              │  │  │ x26     │            │
│  - brain.json│  │  Reads:      │  │  └────┬────┘            │
│  - queue.json│  │  - hub.db RO │  │       │                 │
│  - config.json│ │  - brain.json│  │  ┌────▼────────────┐    │
│              │  │  - queue.json│  │  │ Services         │    │
│  Writes:     │  │              │  │  │ - ProcessManager │    │
│  - queue.json│  │  Writes:     │  │  │ - EventBus      │    │
│  - brain.json│  │  - events.jl │  │  │ - JsonStore     │    │
│              │  │  - sessions/ │  │  │ - CollabContext  │    │
└──────────────┘  └──────────────┘  │  │ - FolderScanner │    │
                                    │  └────┬────────────┘    │
                                    │       │                 │
                                    │  ┌────▼────────────┐    │
                                    │  │ Data Layer       │    │
                                    │  │ hub.db (RO)      │    │
                                    │  │ platform.db (RW) │    │
                                    │  │ JSON files (RW)  │    │
                                    │  └────┬────────────┘    │
                                    │       │                 │
                                    │  ┌────▼────────────┐    │
                                    │  │ Agents (claude -p)│   │
                                    │  │ max 3 concurrent │    │
                                    │  │ stream-json out  │    │
                                    │  └─────────────────┘    │
                                    └──────────┬──────────────┘
                                               │ SSE + REST
                                               ▼
                                    ┌──────────────────────┐
                                    │  Browser (React 19)  │
                                    │  TanStack Query      │
                                    │  ScopeContext (tree)  │
                                    │  useEventSource (SSE) │
                                    └──────────────────────┘
```

### Key Data Flow Paths

| Flow | Path | Latency |
|------|------|---------|
| Dashboard load | Browser → REST → hub.db + platform.db → JSON | <200ms |
| Agent spawn | Browser → REST → ProcessManager → Popen → platform.db | <500ms |
| Agent output | stdout → reader thread → platform.db → EventBus → SSE → Browser | 1-2s |
| think.py cycle | launchd → think.py → queue.json → (file watch) → EventBus → SSE | 15min + 1s |
| Chat message | Browser → REST → Popen(claude -p) → SSE stream → Browser | 2-10s |
| Draft approval | Browser → REST → queue.json write → governance_log → EventBus | <500ms |

### Concurrency Danger Zones

1. **queue.json** — written by both think.py (append items) and Platform (remove items). Advisory lock mitigates but doesn't eliminate race.
2. **hub.db** — read by Platform, written by KH MCP server. WAL mode handles this correctly.
3. **brain.json** — written by think.py (stats) and Platform (settings). Different keys, low risk.
4. **platform.db** — written by main FastAPI thread + N reader threads. WAL mode + busy_timeout handles this.

---

## 3. Recommended Architecture for V2

### Guiding Principles

1. **Keep what works.** The dual-database model, subprocess agent spawning, SSE push, and file-based IPC with think.py are sound. Don't replace them.
2. **Add structure, not frameworks.** The system needs better layering, not a rewrite. Introduce service boundaries and repository patterns incrementally.
3. **Make the event bus durable.** The single biggest architectural improvement is persisting events so they survive restarts and support replay.
4. **Stay local-first.** No cloud dependencies. No external databases. No message brokers. Everything runs on one Mac.

### Recommended Changes

#### 3.1 Introduce a Repository Pattern

**Problem:** Routers directly call `get_platform_db()` and write SQL inline. Untestable, tightly coupled.

**Solution:** Extract data access into repository classes with interface contracts.

```
backend/app/
├── repositories/
│   ├── agent_repo.py        # AgentRepository: CRUD for agents table
│   ├── tree_repo.py         # TreeRepository: CRUD for tree_nodes
│   ├── cost_repo.py         # CostRepository: queries on cost_ledger
│   ├── governance_repo.py   # GovernanceRepository: audit log
│   └── hub_repo.py          # HubRepository: read-only queries on hub.db
├── services/
│   ├── agent_service.py     # Business logic: spawn rules, budget checks
│   ├── collaboration.py     # Workflow engine
│   └── ...
└── routers/
    ├── agents.py            # Thin HTTP layer: validate, delegate to service
    └── ...
```

**Migration:** Extract one router at a time, starting with `agents.py` (most complex).

#### 3.2 Fix the hub.db Write Violation

**Problem:** `collaboration_context.py` writes to hub.db's `todos` table directly.

**Solution:** Route todo creation through the Knowledge Hub MCP tool (`mcp__knowledge-hub__todo_add`) or write to platform.db's own `pending_todos` table and let a sync job push them to hub.db via the MCP server.

#### 3.3 Durable Event Log

**Problem:** EventBus is in-memory only. Events lost on restart. No replay.

**Solution:** Write every event to an `events` table in platform.db before broadcasting to SSE subscribers. See Section 4.

#### 3.4 Structured Error Handling

**Problem:** No consistent error envelope.

**Solution:** FastAPI exception handlers that produce:

```json
{
  "error": "budget_exceeded",
  "message": "Daily budget of $5.00 exceeded for project audit-board",
  "details": { "project_id": "abc", "spent": 5.23, "cap": 5.00 }
}
```

#### 3.5 Configuration Schema

**Problem:** `config.py` is unvalidated flat values.

**Solution:** Pydantic Settings model with validation, env var override, and `.env` file support.

```python
class PlatformSettings(BaseSettings):
    coco_dir: Path = Path.home() / ".coco"
    hub_dir: Path = Path.home() / ".hub"
    max_concurrent_agents: int = Field(3, ge=1, le=10)
    agent_timeout_minutes: int = Field(30, ge=5, le=180)
    chat_timeout_minutes: int = Field(5, ge=1, le=30)

    model_config = SettingsConfigDict(env_prefix="COCO_")
```

---

## 4. Event-Driven Architecture

### Should CoCo Go Fully Event-Sourced?

**Recommendation: No. Hybrid approach -- event log for observability, CRUD for state.**

Full event sourcing would mean deriving all state (agent status, tree structure, settings) from an append-only event log. For CoCo, this is overkill because:

1. **Single user, single machine.** Event sourcing shines for distributed systems with multiple writers. CoCo has one user and one FastAPI process.
2. **State is already simple.** Agent status is a 6-state enum. Tree nodes are a materialized hierarchy. Settings are key-value pairs. Reconstructing these from events adds complexity for zero benefit.
3. **Migration cost is high.** Retrofitting event sourcing into an existing CRUD system requires rewriting every write path. The architecture doc explicitly chose "stateless backend, stateful files."

### What CoCo SHOULD Do: Durable Event Log

Add an append-only `events` table to platform.db:

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,       -- 'agent.spawned', 'agent.completed', 'todo.created', etc.
    payload TEXT NOT NULL,          -- JSON blob
    emitted_at REAL NOT NULL,       -- unix timestamp (time.time())
    source TEXT DEFAULT 'platform'  -- 'platform', 'think.py', 'cli'
);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_time ON events(emitted_at);
```

Modified EventBus:

```python
class EventBus:
    def emit(self, event_type: str, data: dict) -> None:
        # 1. Persist (fire-and-forget to avoid blocking callers)
        self._persist(event_type, data)
        # 2. Broadcast to SSE subscribers (existing logic)
        self._broadcast(event_type, data)

    def replay(self, since: float, event_types: list[str] | None = None) -> list[dict]:
        """Replay events since a timestamp. Used for SSE reconnection and debugging."""
        ...
```

**Benefits:**
- SSE clients that reconnect can replay missed events (using `Last-Event-ID` header)
- Full audit trail of everything that happened in the system
- Debugging: "what happened while I was away?" becomes a simple query
- Foundation for future analytics without the full event-sourcing commitment

**Cost:** Minimal. One INSERT per event. Prune events older than 30 days via a scheduled cleanup.

### Event Taxonomy

| Category | Events |
|----------|--------|
| Agent lifecycle | `agent.spawned`, `agent.paused`, `agent.resumed`, `agent.completed`, `agent.failed`, `agent.killed`, `agent.timeout` |
| Tree mutations | `tree.node_created`, `tree.node_moved`, `tree.node_deleted` |
| Workflow | `workflow.started`, `workflow.step_completed`, `workflow.completed`, `handoff.created`, `handoff.accepted` |
| Decisions | `draft.approved`, `draft.rejected`, `todo.created`, `todo.completed` |
| Cost | `cost.recorded`, `budget.warning`, `budget.exceeded` |
| System | `platform.started`, `platform.stopped`, `health.check`, `think.cycle_completed` |

---

## 5. State Management

### Current State

- **TanStack Query:** Used for server-state cache (tree, API calls). Good choice.
- **React Context (ScopeContext):** Used for tree scope and node selection. Correct -- this is cross-cutting UI state.
- **No Zustand stores:** Despite the architecture doc specifying "one store per domain."

### Recommendation: TanStack Query + Zustand, Drop Context for Domain State

**TanStack Query stays as the primary server-state manager.** It handles caching, background refetch, optimistic updates, and stale-while-revalidate. This is the right tool for data that comes from the API.

**Add Zustand for three specific use cases:**

1. **UI state that doesn't come from the server:**
   - Sidebar collapsed/expanded
   - Active panel in split views
   - Filter/sort preferences per page
   - Command palette open state

2. **SSE-derived real-time state:**
   - Agent status map (updated by SSE events, not by polling)
   - Notification queue (ephemeral, not persisted)
   - Live typing indicators in chat

3. **Cross-cutting derived state:**
   - "Active scope" (currently in ScopeContext -- can stay as Context or move to Zustand, either is fine since it's truly global)

**Do NOT add Zustand for:**
- Agent list, task list, todo list, tree data -- these are server state. Use TanStack Query.
- Anything that needs to survive page refresh -- use localStorage or the API.

**Pattern:**

```typescript
// SSE events update Zustand directly
const useAgentStatusStore = create<AgentStatusState>((set) => ({
  statuses: {},
  updateStatus: (agentId: string, status: string) =>
    set((state) => ({
      statuses: { ...state.statuses, [agentId]: status },
    })),
}));

// SSE handler wires to Zustand + TanStack Query invalidation
function handleSSEEvent(type: string, data: unknown) {
  if (type.startsWith('agent.')) {
    useAgentStatusStore.getState().updateStatus(data.agent_id, data.status);
    queryClient.invalidateQueries({ queryKey: ['agents'] });
  }
}
```

### Why Not Redux / Jotai / Recoil?

- **Redux:** Too much ceremony for a single-user app. Zustand does everything Redux does with 1/10 the boilerplate.
- **Jotai/Recoil:** Atom-based state works well for complex derived state graphs. CoCo's state is flat -- a few maps and lists. Zustand's simplicity wins.

---

## 6. Offline Support

### Current Offline Story

CoCo Platform currently has **no offline support**. If the FastAPI server is down, the browser shows nothing. This is acceptable for v1 (local-only, always-on Mac), but worth planning for.

### What "Offline" Means for CoCo

CoCo is already local-first in the truest sense -- all data is on the user's machine. "Offline" for CoCo means: **the FastAPI server crashed or isn't running, but the browser tab is still open.**

### Recommended Approach: Service Worker + Read Cache

**Tier 1 (Low effort, high value): Stale-while-revalidate caching**

TanStack Query already supports `staleTime` and `gcTime`. Set aggressive stale times so the UI shows cached data even if the server is temporarily unreachable.

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,       // Data is "fresh" for 60s
      gcTime: 10 * 60_000,     // Keep in cache for 10min
      retry: 3,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
    },
  },
});
```

**Tier 2 (Medium effort): Service Worker for static assets**

Register a service worker (via `vite-plugin-pwa`) that caches the built JS/CSS/HTML. This means:
- If the Vite dev server or production static server is down, the app shell still loads from cache.
- API calls still fail, but the user sees a "Backend unavailable" message in a functional UI rather than a blank page.

**Tier 3 (High effort, questionable value): IndexedDB offline write queue**

Queue mutations (approve draft, create todo, update settings) in IndexedDB when the server is unreachable, and flush when it comes back. This is the full "offline-first" pattern.

**Recommendation: Implement Tier 1 now, Tier 2 in Phase 12 (Polish), skip Tier 3.**

Tier 3 is not worth it because:
- CoCo's core actions (spawning agents, chatting with Claude) require the server anyway.
- The server and browser run on the same machine -- if one is down, the user is at the keyboard and can restart it.
- CRDT-based sync (cr-sqlite, Synql) would add significant complexity for a single-user app with no multi-device sync requirement.

### When CRDTs Would Make Sense

CRDTs would become relevant if CoCo ever supports:
- **Multi-device sync** (e.g., MacBook + iPad) -- cr-sqlite could replicate platform.db across devices.
- **Collaborative editing** (e.g., two PMs sharing a project tree) -- Yjs for concurrent tree mutations.
- **Offline agent queuing** (queue agent spawn from phone, execute when Mac wakes) -- event-sourced command queue with CRDT merge.

None of these are on the current roadmap. Revisit if multi-device becomes a requirement.

---

## 7. Extension System Design

### Why CoCo Needs an Extension System

CoCo already has an informal extension system: CoCo skills (`~/.claude/skills/*.md`), Knowledge Hub MCP tools, and think.py plugins. The question is whether to formalize this for third-party (or internal) extensions.

### Recommended: Manifest-Based Plugin System (Raycast Pattern)

Inspired by Raycast's constrained API approach and VS Code's Extension Host isolation, but dramatically simpler because CoCo is single-user and local-only.

#### Plugin Manifest

```toml
# ~/.coco/plugins/my-plugin/plugin.toml
[plugin]
name = "jira-sync"
version = "0.1.0"
description = "Sync Jira tickets into the CoCo tree"
author = "rijul"

[triggers]
# When these events fire, run the handler
events = ["tree.node_created", "agent.completed"]
# Cron-style schedule (optional)
schedule = "*/30 * * * *"

[commands]
# Commands exposed in the command palette
sync-now = { description = "Force sync Jira tickets", handler = "sync.py:run" }

[permissions]
# What the plugin can access
hub_db = "read"           # read-only access to hub.db
platform_db = "read"      # read-only access to platform.db
file_system = ["~/projects/"]  # allowed paths
network = ["mckinsey.atlassian.net"]  # allowed domains
```

#### Execution Model

```
Plugin trigger (event / cron / command)
         │
         ▼
Plugin Runner (subprocess)
  - Spawns: python sync.py (or node handler.js)
  - Env: restricted (no ANTHROPIC_API_KEY unless declared)
  - Stdin: JSON event payload
  - Stdout: JSON result
  - Timeout: 60s default
  - Sandbox: no access beyond declared permissions
         │
         ▼
Result Handler
  - Validates output against declared capabilities
  - Emits events to EventBus if plugin declares write permissions
  - Logs execution to governance_log
```

#### Why Subprocess Isolation (Not In-Process)

Following VS Code's Extension Host pattern: plugins run in separate processes. This means:
- A buggy plugin can't crash the FastAPI server
- Plugins can be killed if they hang (timeout enforcement)
- Resource limits (CPU, memory) can be applied via OS-level controls
- Different languages are supported (Python, Node, shell scripts)

#### Plugin API Surface

Plugins communicate via stdin/stdout JSON protocol. The API surface is deliberately small:

```json
// Input (stdin)
{
  "trigger": "event",
  "event_type": "agent.completed",
  "event_data": { "agent_id": "abc", "status": "completed" },
  "context": {
    "selected_node_id": "xyz",
    "scope_project_ids": ["proj-1", "proj-2"]
  }
}

// Output (stdout)
{
  "actions": [
    { "type": "emit_event", "event_type": "jira.synced", "data": { "tickets": 3 } },
    { "type": "notify", "title": "Jira Sync", "message": "3 tickets synced" },
    { "type": "create_todo", "title": "Review synced tickets", "project_id": "proj-1" }
  ]
}
```

#### Migration Path

1. **Phase 1:** Formalize the plugin manifest format. Move existing integrations (think.py, Jira bridge) to use it.
2. **Phase 2:** Build the Plugin Runner subprocess manager (reuse ProcessManager patterns).
3. **Phase 3:** Add command palette integration and plugin settings UI.
4. **Phase 4:** (Future) Plugin registry / sharing if CoCo ever goes multi-user.

---

## 8. Security Architecture

### Threat Model

CoCo runs on localhost, single-user, no internet exposure. The threat model is:
1. **Malicious subprocess output** -- an agent could emit output that, if rendered unsanitized, causes XSS in the dashboard.
2. **File system traversal** -- API endpoints that accept paths (folder scanner, agent cwd) could be tricked into reading sensitive files.
3. **Secret leakage** -- API keys in env vars, brain.json contents (people data), or agent output could be exposed.
4. **Plugin escape** -- a future plugin could access more than its declared permissions.

### Current Security Measures (Good)

- CORS restricted to `localhost:5173`
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`
- Agent env whitelist (`_ALLOWED_ENV_KEYS`)
- Read-only hub.db access enforced at connection level

### Recommended Additions

#### 8.1 Content Security Policy

```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "  # Tailwind needs inline styles
    "connect-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self';"
)
```

#### 8.2 Path Validation Middleware

Every endpoint that accepts a file path should validate it against an allowlist:

```python
ALLOWED_ROOTS = [
    Path.home() / "projects",
    Path.home() / ".coco",
    Path.home() / ".hub",
]

def validate_path(path: str) -> Path:
    resolved = Path(path).resolve()
    if not any(resolved.is_relative_to(root) for root in ALLOWED_ROOTS):
        raise HTTPException(403, f"Path {path} is outside allowed directories")
    return resolved
```

#### 8.3 Agent Output Sanitization

Before rendering agent output in the browser:
- Strip ANSI escape codes (already common in terminal output)
- HTML-encode all output before rendering (React does this by default, but `dangerouslySetInnerHTML` must never be used for agent output)
- Rate-limit output storage to prevent disk exhaustion (current 1000-line cap per agent is good)

#### 8.4 Secret Detection

Add a pre-commit hook and a runtime scanner that flags patterns like API keys in:
- Agent output stored in `agent_output` table
- brain.json before it's served via the API
- Plugin stdout before processing

```python
SECRET_PATTERNS = [
    r'sk-ant-[a-zA-Z0-9]{20,}',     # Anthropic API key
    r'AKIA[0-9A-Z]{16}',            # AWS access key
    r'ghp_[a-zA-Z0-9]{36}',         # GitHub PAT
]
```

#### 8.5 Optional PIN Enhancement

The current "optional PIN" model is fine for localhost. If CoCo ever needs to be accessible from the local network (e.g., iPad on same WiFi):
- Add session-based PIN authentication (not per-request)
- Use `httpOnly` cookies with `SameSite=Strict`
- Rate-limit PIN attempts (5 per minute)

---

## 9. Monitoring and Observability

### Current State

- `structlog` JSON logging (good foundation)
- `X-Response-Time` header on every response
- Slow request warning at >200ms
- Agent `last_heartbeat` tracking
- No metrics, no dashboards, no alerting

### Recommended: Three-Layer Observability

#### Layer 1: Structured Logging (Already Done, Enhance)

**Current:** structlog JSON to stdout.
**Add:** Log to `~/.coco/logs/platform.log` with rotation (logrotate or Python's `RotatingFileHandler`, 10MB x 5 files).

Key log events to standardize:
```python
log.info("request_completed", path="/api/agents", method="GET", status=200, duration_ms=45)
log.info("agent_spawned", agent_id="abc", node_id="xyz", model="sonnet")
log.warning("slow_query", table="content", duration_ms=350, query_hash="...")
log.error("agent_crash", agent_id="abc", exit_code=1, stderr_tail="...")
```

#### Layer 2: Metrics Table (New)

Add a `metrics` table to platform.db for time-series data:

```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric TEXT NOT NULL,         -- 'request_count', 'request_latency_p99', 'agent_spawn_count'
    value REAL NOT NULL,
    labels TEXT,                  -- JSON: {"path": "/api/agents", "method": "GET"}
    recorded_at REAL NOT NULL     -- unix timestamp
);
CREATE INDEX idx_metrics_name_time ON metrics(metric, recorded_at);
```

Metrics to track:
| Metric | Type | Labels |
|--------|------|--------|
| `request_count` | counter | path, method, status |
| `request_latency_ms` | gauge | path, method |
| `agent_spawn_total` | counter | model, node_id |
| `agent_duration_seconds` | gauge | agent_id |
| `db_query_duration_ms` | gauge | table, operation |
| `sse_subscribers` | gauge | -- |
| `disk_usage_bytes` | gauge | db_name |
| `event_bus_queue_depth` | gauge | -- |

**Collection:** Middleware samples request metrics. A background task (every 60s) collects system metrics (disk, memory, queue depth).

**Pruning:** Delete metrics older than 7 days. This is not Prometheus -- it's a lightweight self-diagnosis tool.

#### Layer 3: Health Dashboard Endpoint

Enhance `GET /api/health` to return a comprehensive system status:

```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "version": "0.1.0",
  "databases": {
    "hub_db": { "status": "ok", "size_mb": 45.2, "last_write": "2026-03-28T10:00:00Z" },
    "platform_db": { "status": "ok", "size_mb": 12.1, "wal_size_mb": 0.3 }
  },
  "agents": { "running": 1, "total_spawned_today": 5, "failed_today": 0 },
  "sse_subscribers": 2,
  "think_py": { "last_run": "2026-03-28T09:45:00Z", "next_expected": "2026-03-28T10:00:00Z" },
  "disk": { "coco_dir_mb": 120, "hub_dir_mb": 450 },
  "recent_errors": 0,
  "slowest_endpoint_ms": { "path": "/api/tree", "p99": 180 }
}
```

#### Self-Diagnosis Alert System

Rather than external monitoring, CoCo can monitor itself:

```python
# Run every 5 minutes as a background task
async def self_diagnosis():
    issues = []

    # Check think.py staleness
    if think_py_last_run > timedelta(hours=1):
        issues.append("think.py hasn't run in over 1 hour")

    # Check disk space
    if platform_db_size > 500_000_000:  # 500MB
        issues.append("platform.db exceeds 500MB -- consider pruning")

    # Check agent zombies
    for agent in running_agents:
        if agent.last_heartbeat < now - timedelta(minutes=10):
            issues.append(f"Agent {agent.id} hasn't sent heartbeat in 10min")

    if issues:
        event_bus.emit("health.warning", {"issues": issues})
```

---

## 10. Migration Path

### Phasing: From Current to V2 Architecture

The key constraint is: **every change ships independently and the system stays functional throughout.** No big-bang rewrites.

### Phase A: Foundation Hardening (1-2 weeks)

**Goal:** Fix the critical issues without changing the architecture.

| Task | Effort | Impact |
|------|--------|--------|
| Fix hub.db write violation in `collaboration_context.py` | 0.5d | Critical: data integrity |
| Add Pydantic Settings to replace `config.py` | 0.5d | Medium: validation + .env support |
| Add structured error envelope + exception handlers | 1d | Medium: API consistency |
| Add `events` table + make EventBus durable | 1d | High: observability foundation |
| Add CSP header + path validation middleware | 0.5d | Medium: security baseline |
| Enhance health endpoint with system status | 0.5d | Medium: self-diagnosis |

### Phase B: Service Layer Extraction (2-3 weeks)

**Goal:** Introduce repository pattern, one router at a time.

Order of extraction (by complexity and test value):
1. `agents.py` -- most complex, highest value from testability
2. `tree.py` -- core data model, used by many other features
3. `costs.py` -- financial data, correctness matters
4. `tasks.py` -- state machine logic benefits from unit tests
5. Remaining routers (lower priority, extract as touched)

Each extraction follows the same pattern:
1. Create `repositories/x_repo.py` with typed methods
2. Create `services/x_service.py` with business logic
3. Slim down router to validation + delegation
4. Add unit tests for service layer (mock repository)

### Phase C: Frontend State Maturation (1 week)

**Goal:** Add Zustand for SSE-derived state, improve error handling.

| Task | Effort |
|------|--------|
| Add `useAgentStatusStore` (Zustand) wired to SSE events | 0.5d |
| Add `useNotificationStore` (Zustand) for toast/notification state | 0.5d |
| Add global error boundary with structured error display | 0.5d |
| Add TanStack Query defaults (staleTime, retry, error handling) | 0.5d |
| Add service worker for static asset caching | 0.5d |

### Phase D: Extension System (2-3 weeks, future)

**Goal:** Formalize plugin manifest and runner.

Only pursue this after Phases A-C are complete and the system is stable. The plugin system is a "nice to have" that enables future flexibility but isn't needed for the core PM workflow.

### Phase E: Observability (1 week, ongoing)

**Goal:** Metrics table, self-diagnosis, log rotation.

Can run in parallel with Phase B since it touches different files.

### Summary Timeline

```
Week 1-2:  Phase A (Foundation Hardening)
Week 2-4:  Phase B (Service Layer) + Phase E (Observability) in parallel
Week 4-5:  Phase C (Frontend State)
Week 6-8:  Phase D (Extension System) -- only if needed
```

Total: **5 weeks for A-C-E (core), 8 weeks if D is included.**

---

## Appendix: Research Sources

- [A Beginner's Guide to Local-First Software Development](https://blog.openreplay.com/beginners-guide-local-first-software-development/)
- [VS Code Extension Host Architecture](https://code.visualstudio.com/api/advanced-topics/extension-host)
- [Cursor: How Forking VS Code Built a $29B Company](https://www.mmntm.net/articles/cursor-deep-dive)
- [LangGraph vs CrewAI vs AutoGen: Multi-Agent AI Orchestration Guide 2026](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63)
- [LangGraph Agents in Production](https://www.alphabold.com/langgraph-agents-in-production/)
- [cr-sqlite: Convergent, Replicated SQLite](https://github.com/vlcn-io/cr-sqlite)
- [SQLite Sync: CRDT-based Offline-First Sync](https://github.com/sqliteai/sqlite-sync)
- [How Raycast API and Extensions Work](https://www.raycast.com/blog/how-raycast-api-extensions-work)
- [Event Sourcing with SQLite](https://www.sqliteforum.com/p/event-sourcing-with-sqlite)
- [Building Event Sourcing Systems with SQLite: CQRS Guide](https://www.sqliteforum.com/p/building-event-sourcing-systems-with)

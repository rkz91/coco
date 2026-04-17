# CoCo Platform — Deep Architecture Analysis

> Generated 2026-04-08 | 3 parallel analyst agents | Backend + Frontend + Data Layer

---

## 0. User Journeys

### Primary Daily Flow

```mermaid
journey
    title Rijul's Daily CoCo Workflow
    section Morning Kickoff
      Open CoCo Platform: 5: Rijul
      View HomePage briefing: 5: Rijul
      Listen to podcast briefing: 4: Rijul
      Scan health grid (all green?): 5: Rijul
      Check focus list (high-priority todos): 5: Rijul
    section Triage
      Open Inbox (8 tabs): 4: Rijul
      Review urgent items: 4: Rijul
      Approve/reject drafts: 5: Rijul
      Classify unsorted content: 3: Rijul
      Process decision queue: 4: Rijul
    section Deep Work
      Navigate to project via tree: 5: Rijul
      Spawn agent for task: 5: Rijul
      Monitor agent progress (SSE): 4: Rijul
      Chat with Claude for context: 5: Rijul
      Review agent output: 4: Rijul
    section End of Day
      Check cost summary: 4: Rijul
      Review activity log: 3: Rijul
      Mark todos done: 5: Rijul
```

### Journey: Inbox Triage to Action

```mermaid
flowchart TB
    START([Open CoCo]) --> HOME[HomePage]
    HOME -->|"Needs attention badge"| INBOX[InboxPage]

    INBOX --> TAB_URGENT["Urgent Tab<br/>(high-priority items)"]
    INBOX --> TAB_DRAFTS["Drafts Tab<br/>(KH-generated docs)"]
    INBOX --> TAB_CLASSIFY["Classify Tab<br/>(unsorted content)"]
    INBOX --> TAB_ACTIONS["Actions Tab<br/>(extracted action items)"]
    INBOX --> TAB_HEALTH["Health Tab<br/>(system alerts)"]

    TAB_URGENT -->|"Click item"| DETAIL["Item Detail"]
    DETAIL -->|"Assign to project"| TREE_NAV["Navigate Tree"]
    DETAIL -->|"Create todo"| TODO_CREATE["TodosPage + New Todo"]
    DETAIL -->|"Spawn agent"| AGENT_SPAWN["AgentsPage + Spawn"]

    TAB_DRAFTS -->|"Review"| DRAFT_REVIEW["Draft Preview"]
    DRAFT_REVIEW -->|"Approve"| APPROVED["Approved → Knowledge Hub"]
    DRAFT_REVIEW -->|"Reject"| REJECTED["Rejected + Feedback"]

    TAB_CLASSIFY -->|"Assign project"| CLASSIFIED["Content → Project"]
    TAB_CLASSIFY -->|"Mark noise"| DISMISSED["Dismissed"]

    TAB_ACTIONS -->|"Convert to todo"| TODO_CREATE
    TAB_ACTIONS -->|"Delegate to agent"| AGENT_SPAWN

    style INBOX fill:#4a9eff,color:#fff
    style APPROVED fill:#10b981,color:#fff
    style AGENT_SPAWN fill:#8b5cf6,color:#fff
```

### Journey: Spawning & Monitoring an Agent

```mermaid
flowchart TB
    START([Need something done]) --> CHOOSE{How to start?}

    CHOOSE -->|"From project"| PROJ["ProjectDetailPage<br/>→ Agents tab"]
    CHOOSE -->|"From agents"| AGENTS["AgentsPage<br/>→ Create Agent"]
    CHOOSE -->|"Voice command"| ORB["CoCo Orb<br/>'spawn a developer'"]
    CHOOSE -->|"From todo"| TODO["TodosPage<br/>→ Delegate"]

    PROJ --> CREATE["Create/Select Agent<br/>Pick role, model, task"]
    AGENTS --> CREATE
    ORB -->|"Jarvis interprets"| CREATE
    TODO -->|"Auto-assign"| CREATE

    CREATE --> SPAWN["POST /agents/:id/spawn"]
    SPAWN --> CONTEXT["Context Injection<br/>Brain + YOLO + Knowledge"]
    CONTEXT --> RUNNING["Agent Running<br/>(SSE: agent.spawned)"]

    RUNNING --> MONITOR{Monitor}
    MONITOR -->|"Real-time output"| LOG_VIEW["Agent Log Viewer<br/>(streaming)"]
    MONITOR -->|"Status badge"| CARD["Agent Card<br/>(idle/running/failed)"]
    MONITOR -->|"Desktop notification"| NOTIF["Desktop Notification<br/>'Agent completed'"]

    RUNNING -->|"Needs input"| PAUSE["Agent Paused<br/>→ Queue item created"]
    PAUSE -->|"Decision"| RESUME["Resume with answer"]

    RUNNING --> DONE{Outcome}
    DONE -->|"Success"| COMPLETED["Agent Completed<br/>Review output"]
    DONE -->|"Failed"| FAILED["Agent Failed<br/>Check logs, retry?"]
    DONE -->|"Timeout (30min)"| TIMEOUT["Auto-killed<br/>Partial output saved"]

    COMPLETED --> NEXT{Next?}
    NEXT -->|"More work"| SPAWN
    NEXT -->|"Handoff"| HANDOFF["Handoff to another agent"]
    NEXT -->|"Done"| CLOSE["Mark task done"]

    style RUNNING fill:#10b981,color:#fff
    style FAILED fill:#ef4444,color:#fff
    style COMPLETED fill:#4a9eff,color:#fff
    style ORB fill:#8b5cf6,color:#fff
```

### Journey: Knowledge Discovery

```mermaid
flowchart TB
    START([Looking for information]) --> ENTRY{Entry Point}

    ENTRY -->|"Cmd+K"| PALETTE["Command Palette<br/>Search across everything"]
    ENTRY -->|"Knowledge page"| KNOW["KnowledgePage"]
    ENTRY -->|"Project detail"| PROJ["ProjectDetailPage<br/>→ Knowledge tab"]
    ENTRY -->|"CoCo Orb"| ORB["'search for X'"]

    PALETTE -->|"Display ID (CXR-47)"| RESOLVE["Resolve → Jump to entity"]
    PALETTE -->|"Text search"| SEARCH["Search Results"]

    KNOW --> CONTENT_TAB["Content Tab<br/>Filter by source/project"]
    KNOW --> INSIGHTS_TAB["Insights Tab<br/>Cross-source entities"]
    KNOW --> GRAPH_TAB["Entity Graph Tab<br/>Visual connections"]

    CONTENT_TAB -->|"Click item"| DETAIL["Content Detail<br/>Full text + metadata"]
    DETAIL -->|"Assign to project"| CLASSIFY["Classify"]
    DETAIL -->|"Extract todos"| EXTRACT["Action Items → Todos"]
    DETAIL -->|"Chat about it"| CHAT["ChatPage<br/>Attach content to chat"]

    INSIGHTS_TAB -->|"Entity card"| ENTITY["Entity Detail<br/>Mentions across sources"]

    PROJ -->|"Scoped content"| SCOPED["Content filtered<br/>to this project"]

    CHAT --> ASK["Ask Claude<br/>with KH context injected"]
    ASK --> RESPONSE["Response<br/>(model: sonnet/opus/haiku)"]

    style PALETTE fill:#f59e0b,color:#fff
    style CHAT fill:#4a9eff,color:#fff
    style KNOW fill:#10b981,color:#fff
```

### Journey: Self-Improve Cycle (Studio)

```mermaid
flowchart TB
    START([Start Self-Improve]) --> INIT["/self-improve page"]
    INIT --> CONFIG["Configure<br/>Focus areas, max improvements"]
    CONFIG --> LAUNCH["Start Cycle"]

    LAUNCH --> PM["PM Agent (Opus)<br/>Analyzes codebase,<br/>proposes improvements"]
    PM --> ARCH["Architect Agent (Opus)<br/>Validates feasibility,<br/>orders by build sequence"]
    ARCH --> DEV["Developer Agent (Opus)<br/>Implements in git worktree"]
    DEV --> TEST["Tester Agent (Sonnet)<br/>Runs pytest"]
    TEST --> SEC["Security Agent (Sonnet)<br/>Vulnerability scan"]
    SEC --> REVIEW["Reviewer Agent (Opus)<br/>Code review"]
    REVIEW --> DOC["Doc Writer (Sonnet)<br/>PR description + changelog"]

    DOC --> AWAIT["Awaiting Human Approval"]

    AWAIT --> HUMAN{Rijul Reviews}
    HUMAN -->|"View diff"| DIFF["Full Code Diff"]
    DIFF --> DECIDE{Approve?}
    DECIDE -->|"Yes"| MERGE["Merge worktree → main"]
    DECIDE -->|"No"| REJECT["Reject + cleanup worktree"]

    MERGE --> QA["QA Lead (Opus)<br/>Integration test"]
    QA --> DONE["Cycle Complete<br/>Analytics updated"]

    REJECT --> NEXT{More improvements?}
    NEXT -->|"Yes"| AWAIT
    NEXT -->|"No"| CANCELLED["Cycle Ended"]

    style AWAIT fill:#f59e0b,color:#fff
    style MERGE fill:#10b981,color:#fff
    style REJECT fill:#ef4444,color:#fff
    style PM fill:#8b5cf6,color:#fff
    style ARCH fill:#8b5cf6,color:#fff
    style DEV fill:#8b5cf6,color:#fff
```

### Journey: Portfolio Management (Tree)

```mermaid
flowchart LR
    subgraph Tree["Portfolio Tree"]
        ROOT["My Portfolio"]
        ROOT --> T1["Team: Anti-Corruption"]
        ROOT --> T2["Team: AuditBoard"]
        ROOT --> T3["Team: 3PI V2"]
        ROOT --> MORE["+ 10 more teams"]

        T1 --> P1["Project: ACC Phase 1"]
        T1 --> P2["Project: ACC Phase 2"]
        T2 --> P3["Project: AB Config"]
        T2 --> P4["Project: AB Tax"]

        P1 --> A1["Agent: Developer"]
        P1 --> A2["Agent: Researcher"]
    end

    subgraph Actions["Tree Actions"]
        DRAG["Drag & Drop<br/>Reorder/reparent"]
        ANALYZE["Analyze Folder<br/>→ AI scans folder contents"]
        SCOPE["Click node<br/>→ Scopes entire app"]
        ADD["Add node<br/>→ group/team/project"]
    end

    subgraph Scoped["Scoped Views (after click)"]
        S_AGENTS["AgentsPage<br/>filtered to project"]
        S_TODOS["TodosPage<br/>filtered to project"]
        S_COSTS["CostsPage<br/>filtered to project"]
        S_KNOWLEDGE["KnowledgePage<br/>filtered to project"]
    end

    Tree --> Actions
    SCOPE --> Scoped

    style ROOT fill:#4a9eff,color:#fff
    style SCOPE fill:#10b981,color:#fff
```

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph External["External Data Sources"]
        HUB_DB["hub.db<br/>(Knowledge Hub)<br/>READ-ONLY"]
        BRAIN["brain.json<br/>(People Graph)"]
        QUEUE["queue.json<br/>(Decision Queue)"]
        EVENTS_FILE["events.jsonl<br/>(Event Stream)"]
        SESSIONS["~/.coco/sessions/<br/>(CLI History)"]
    end

    subgraph Backend["FastAPI Backend :8000"]
        direction TB
        MAIN["main.py<br/>Lifespan Manager"]
        
        subgraph CoreRouters["Core Routers (27)"]
            R_AGENTS["agents"]
            R_CHAT["chat"]
            R_TASKS["tasks"]
            R_TODOS["todos"]
            R_COSTS["costs"]
            R_TREE["tree"]
            R_HOME["home"]
            R_EVENTS["events/stream"]
            R_INBOX["inbox"]
            R_KNOWLEDGE["content/search"]
            R_MORE["+ 17 more"]
        end

        subgraph StudioRouters["Studio Routers (4)"]
            R_JARVIS["jarvis"]
            R_TTS["tts"]
            R_STT["stt"]
            R_SELF["self-improve"]
        end

        subgraph Services["Services Layer"]
            SVC_PM["ProcessManager<br/>(Agent Lifecycle)"]
            SVC_HUB["HubSync<br/>(60s delta sync)"]
            SVC_EB["EventBus<br/>(SSE + persistence)"]
            SVC_TRIGGER["TriggerEngine<br/>(cron/webhook/file)"]
            SVC_JSON["JsonStore<br/>(atomic R/W)"]
            SVC_SDK["AgentSDK<br/>(Claude API)"]
            SVC_SI["SelfImprove<br/>(10-agent squad)"]
        end

        PLATFORM_DB[("platform.db<br/>(27+ tables)")]
    end

    subgraph Frontend["React Frontend :5173"]
        direction TB
        APP["App.tsx<br/>React Router v7"]
        
        subgraph Pages["17 Pages"]
            P_HOME["HomePage"]
            P_DASH["DashboardPage"]
            P_AGENTS["AgentsPage"]
            P_CHAT["ChatPage"]
            P_TODOS["TodosPage"]
            P_KNOWLEDGE["KnowledgePage"]
            P_INBOX["InboxPage"]
            P_TREE["TreePage"]
            P_COSTS["CostsPage"]
            P_MORE["+ 8 more"]
        end

        subgraph State["State Management"]
            TQ["TanStack Query<br/>(282 queries)"]
            SCOPE["ScopeContext<br/>(Tree Navigation)"]
            SSE_HOOK["useEventSource<br/>(Real-time SSE)"]
        end

        subgraph Studio_UI["Studio UI"]
            ORB["CoCo Orb<br/>(Voice + Text)"]
            JARVIS_UI["Jarvis Overlay"]
        end
    end

    subgraph MCP["MCP Server (HTTP)"]
        MCP_SRV["FastMCP<br/>22 tools"]
    end

    subgraph Claude["Claude CLI"]
        CLAUDE_P["claude -p<br/>(subprocess)"]
    end

    %% Data Flow
    HUB_DB -->|"read-only sync"| SVC_HUB
    SVC_HUB -->|"mirror tables"| PLATFORM_DB
    BRAIN <-->|"atomic JSON"| SVC_JSON
    QUEUE <-->|"atomic JSON"| SVC_JSON
    SVC_EB -->|"append"| EVENTS_FILE

    MAIN --> CoreRouters
    MAIN -->|"if COCO_EDITION=studio"| StudioRouters
    CoreRouters --> Services
    StudioRouters --> Services
    Services --> PLATFORM_DB

    SVC_PM -->|"spawn subprocess"| CLAUDE_P
    SVC_SDK -->|"Anthropic API"| CLAUDE_P

    Frontend -->|"HTTP + SSE"| Backend
    SSE_HOOK -->|"EventSource"| R_EVENTS
    MCP_SRV -->|"HTTP localhost"| Backend
    MCP_SRV -->|"direct file"| BRAIN
    MCP_SRV -->|"direct file"| QUEUE

    style HUB_DB fill:#4a9eff,color:#fff
    style PLATFORM_DB fill:#10b981,color:#fff
    style BRAIN fill:#f59e0b,color:#fff
    style QUEUE fill:#f59e0b,color:#fff
    style StudioRouters fill:#8b5cf6,color:#fff
    style Studio_UI fill:#8b5cf6,color:#fff
```

---

## 2. Agent Lifecycle Flow

```mermaid
stateDiagram-v2
    [*] --> idle: Agent Created
    idle --> spawning: POST /spawn
    spawning --> running: Process Started
    running --> paused: POST /pause (SIGSTOP)
    paused --> running: POST /resume (SIGCONT)
    running --> completed: Exit Code 0
    running --> failed: Exit Code != 0
    running --> failed: Heartbeat Lost (30s)
    running --> killed: POST /kill (SIGTERM)
    killed --> [*]
    completed --> [*]
    failed --> idle: Retry

    note right of spawning
        1. Build context (brain + YOLO + knowledge)
        2. Check budget cap
        3. Acquire concurrency semaphore (max 3)
        4. SDK path OR subprocess path
        5. Start output reader thread
    end note

    note right of running
        Heartbeat every 30s
        Output batched (10 lines / 2s)
        Max 1000 output rows kept
        Timeout: 30 min default
    end note
```

```mermaid
flowchart LR
    subgraph Context_Injection["Context Injection (Pre-Spawn)"]
        direction TB
        A1["build_coco_context()<br/>People + Rules from brain.json"]
        A2["build_yolo_constraints()<br/>Autonomy guardrails"]
        A3["build_knowledge_context()<br/>Relevant KH content (2000 tokens)"]
        A4["build_collaboration_prompt()<br/>Project context + handoffs"]
    end

    subgraph Dual_Path["Execution Path"]
        direction TB
        SDK["SDK Path<br/>(USE_AGENT_SDK=true)<br/>Anthropic API direct<br/>Real token counts"]
        CLI["CLI Path (default)<br/>claude -p --stream-json<br/>Subprocess PID tracking<br/>Approximate token counts"]
    end

    subgraph Output["Output Pipeline"]
        direction TB
        STREAM["Stream Reader Thread"]
        DB_OUT["agent_output table<br/>(last 1000 rows)"]
        COST["cost_ledger<br/>(per-call costs)"]
        EVENT["EventBus<br/>(agent.* events)"]
        SSE_OUT["SSE to Frontend"]
    end

    Context_Injection --> Dual_Path
    SDK --> Output
    CLI --> Output
    STREAM --> DB_OUT
    STREAM --> COST
    STREAM --> EVENT
    EVENT --> SSE_OUT
```

---

## 3. Data Flow: Knowledge Hub to Frontend

```mermaid
flowchart TB
    subgraph KH["Knowledge Hub (Separate System)"]
        KH_INGEST["Ingest Pipeline<br/>(email triage, classify)"]
        KH_DB[("hub.db<br/>todos, content, projects,<br/>drafts, costs, sync_state")]
    end

    subgraph Sync["Hub Sync Service (60s loop)"]
        FULL["Full Sync<br/>(startup)"]
        DELTA["Delta Sync<br/>(rowid > watermark)"]
        FTS["FTS5 Index<br/>(title, raw_text,<br/>processed_text, source)"]
    end

    subgraph Mirror["Mirror Tables in platform.db"]
        M_TODOS["hub_todos"]
        M_CONTENT["hub_content"]
        M_PROJECTS["hub_projects"]
        M_DRAFTS["hub_drafts"]
        M_COSTS["hub_api_costs"]
        M_PC["hub_project_content"]
        M_SS["hub_sync_state"]
    end

    subgraph Overlay["Platform Overlay (Read-Write)"]
        O_TODO["todo_overrides<br/>(status, priority, owner,<br/>due_date, project_id)"]
        O_DRAFT["draft_decisions<br/>(approved/rejected)"]
        O_PROJ["project_overrides"]
        O_DEPS["todo_dependencies<br/>(blocked_by)"]
        O_IDS["entity_identifiers<br/>(display IDs: CXR-47)"]
    end

    subgraph API["API Response (Merged)"]
        MERGE["Hub Data + Overlay = Final View"]
    end

    KH_INGEST --> KH_DB
    KH_DB -->|"read-only<br/>?mode=ro"| Sync
    FULL --> Mirror
    DELTA --> Mirror
    Mirror --> FTS

    Mirror --> MERGE
    Overlay --> MERGE
    MERGE -->|"JSON"| FE["Frontend"]

    style KH_DB fill:#4a9eff,color:#fff
    style Mirror fill:#60a5fa,color:#fff
    style Overlay fill:#10b981,color:#fff
```

---

## 4. Real-Time Event System

```mermaid
flowchart LR
    subgraph Emitters["Event Sources"]
        E1["Agent spawn/kill/fail"]
        E2["Task transitions"]
        E3["Draft approve/reject"]
        E4["Todo overdue"]
        E5["Budget warnings"]
        E6["Trigger fires"]
        E7["Self-improve cycles"]
    end

    subgraph Bus["EventBus (Singleton)"]
        direction TB
        MEM["In-Memory Queues<br/>(asyncio.Queue per subscriber<br/>256 item buffer)"]
        DB_EVT[("events table<br/>(24h retention)")]
        JSONL["events.jsonl<br/>(trimmed at 10k lines)"]
    end

    subgraph Consumers["Consumers"]
        SSE_EP["/api/events/stream<br/>(SSE endpoint)"]
        AGENT_EP["/api/events/agents<br/>(Agent-specific SSE)"]
        NOTIF["NotificationProvider<br/>(Frontend)"]
        TOAST["Toast System"]
        DESKTOP["Desktop Notifications"]
    end

    Emitters -->|"event_bus.emit()"| Bus
    MEM --> SSE_EP
    DB_EVT -->|"replay since=ts"| SSE_EP
    JSONL -->|"file tail"| SSE_EP
    MEM --> AGENT_EP

    SSE_EP -->|"EventSource<br/>exponential backoff"| NOTIF
    NOTIF --> TOAST
    NOTIF --> DESKTOP
```

---

## 5. Self-Improve Cycle (Studio)

```mermaid
stateDiagram-v2
    [*] --> planning: Start Cycle
    planning --> architecting: PM Agent proposes improvements
    architecting --> developing: Architect validates + orders
    developing --> testing: Developer implements in worktree
    testing --> reviewing: Tester runs pytest
    reviewing --> documenting: Reviewer code-reviews
    documenting --> awaiting_approval: Doc Writer creates PR desc
    awaiting_approval --> merging: Human approves
    awaiting_approval --> rejected: Human rejects
    merging --> integrating: Worktree merged to main
    integrating --> completed: QA Lead verifies
    rejected --> [*]
    completed --> [*]

    note right of developing
        Isolated git worktree per improvement
        Branch: self-improve/<uuid>
        Denylist: *.db, *.env, credentials
    end note

    note left of awaiting_approval
        Human reviews diff at:
        GET /self-improve/improvements/{id}/diff
        Then: POST /approve or /reject
    end note
```

---

## 6. Frontend Page Architecture

```mermaid
flowchart TB
    subgraph App["App.tsx (React Router v7)"]
        direction TB
        SHELL["AppShell<br/>(Sidebar + Content)"]

        subgraph Eager["Eager Loaded"]
            HOME["/ → HomePage<br/>Briefing, Focus, Health, Podcast"]
            DASH["/analytics → DashboardPage<br/>Metrics, Projects, Activity"]
        end

        subgraph Lazy["Lazy Loaded (15 pages)"]
            AGENTS["/agents → AgentsPage<br/>Cards + Org Chart"]
            CHAT["/chat → ChatPage<br/>SSE Streaming, 3 models"]
            TODOS["/todos → TodosPage<br/>List + Board views"]
            KNOW["/knowledge → KnowledgePage<br/>Content, Insights, Graph"]
            INBOX["/inbox → InboxPage<br/>8 tabs, batch actions"]
            TREE["/tree → TreePage<br/>Drag-drop hierarchy"]
            COSTS["/costs → CostsPage<br/>Charts, Budgets"]
            PROJ["/projects/:id → ProjectDetailPage<br/>10 tabs (needs refactor)"]
            GOALS["/goals → GoalsPage<br/>OKR tree"]
            SETTINGS["/settings → SettingsPage<br/>6 config tabs"]
            ACTIVITY["/activity → ActivityPage<br/>Audit log"]
        end

        subgraph StudioPages["Studio-Only Routes"]
            SI["/self-improve<br/>Cycle Manager"]
            REPLAY["/replays/:id<br/>Agent Replay Viewer"]
            JARVIS_P["/jarvis → redirect to /?jarvis=true"]
        end
    end

    subgraph SharedUI["Shared Components (116 total)"]
        ORB2["CoCo Orb<br/>(floating voice/text)"]
        CMD["CommandPalette<br/>(Cmd+K, 19 commands)"]
        NOTIF2["NotificationDropdown"]
        BREAD["Breadcrumbs"]
        ERR["ErrorBoundary<br/>(every route)"]
    end

    SHELL --> Eager
    SHELL --> Lazy
    SHELL --> StudioPages
    SHELL --> SharedUI

    style StudioPages fill:#8b5cf6,color:#fff
    style Eager fill:#10b981,color:#fff
```

---

## 7. Database Schema Map

```mermaid
erDiagram
    nodes ||--o{ nodes : "parent_id"
    nodes ||--o{ agents : "node_id"
    nodes ||--o{ tasks : "node_id"
    nodes ||--o{ cost_ledger : "node_id"
    nodes ||--o{ goals : "node_id"
    nodes ||--o{ entity_identifiers : "node_id"
    nodes ||--o{ project_context : "node_id"
    nodes ||--o{ triggers : "node_id"
    nodes ||--o{ budgets : "node_id"

    agents ||--o{ agent_output : "agent_id"
    agents ||--o{ agent_sessions : "agent_id"
    agents ||--o{ cost_ledger : "agent_id"

    tasks ||--o{ tasks : "parent_task_id"
    tasks ||--o{ task_documents : "task_id"

    hub_todos ||--o| todo_overrides : "hub_todo_id"
    hub_todos ||--o{ todo_dependencies : "todo_id"
    hub_drafts ||--o| draft_decisions : "hub_draft_id"

    chat_sessions ||--o{ chat_messages : "session_id"

    self_improve_cycles ||--o{ self_improve_improvements : "cycle_id"
    self_improve_improvements ||--o{ self_improve_agents : "improvement_id"

    triggers ||--o{ trigger_log : "trigger_id"

    nodes {
        uuid id PK
        uuid parent_id FK
        string label
        string node_type
        string hub_project_id
        string path
        int depth
        int sort_order
    }

    agents {
        uuid id PK
        uuid node_id FK
        string name
        string role
        string status
        int pid
        string model
    }

    cost_ledger {
        uuid id PK
        uuid agent_id FK
        uuid node_id FK
        string model
        int input_tokens
        int output_tokens
        float cost_usd
    }

    hub_todos {
        int rowid PK
        string title
        string status
        string priority
    }

    todo_overrides {
        uuid id PK
        int hub_todo_id FK
        string status
        string priority
        string owner
    }
```

---

## 8. Trigger Execution Flow

```mermaid
flowchart TB
    subgraph Types["Trigger Types"]
        CRON["cron<br/>'*/30 * * * *'<br/>Checked every 30s"]
        WEBHOOK["webhook<br/>POST /api/webhooks/:id<br/>Instant"]
        FILEWATCH["file_watch<br/>mtime polling<br/>Every 30s"]
    end

    subgraph Engine["TriggerEngine (Singleton)"]
        CRON_LOOP["Cron Loop<br/>(dedup by minute)"]
        FW_LOOP["File Watch Loop<br/>(mtime cache)"]
    end

    subgraph Actions["Action Types"]
        A_SPAWN["spawn_agent<br/>Claude subprocess"]
        A_CMD["run_command<br/>Shell exec"]
        A_TODO["create_todo<br/>Platform todo"]
        A_NOTIFY["notify<br/>EventBus emit"]
        A_POD["podcast_generate<br/>(Studio only)"]
    end

    LOG[("trigger_log<br/>(status, error, duration)")]

    CRON --> CRON_LOOP
    FILEWATCH --> FW_LOOP
    WEBHOOK -->|"HTTP POST"| Engine

    Engine --> Actions
    Actions --> LOG
```

---

## 9. Health Scorecard

### What Works Well

| Area | Score | Details |
|------|-------|---------|
| **Hub Sync** | 9/10 | Read-only mirror with delta sync, FTS5 index, overlay pattern. Rock solid. |
| **Agent Spawning** | 8/10 | Context injection, budget checks, heartbeat monitoring, concurrency control. |
| **Event System** | 8/10 | Dual persistence (memory + DB), SSE with replay, exponential backoff reconnect. |
| **Tree Hierarchy** | 8/10 | Proper FK constraints, path indexing, depth tracking. Flexible. |
| **Trigger Engine** | 8/10 | Cron + webhook + file-watch, comprehensive logging. |
| **MCP Server** | 9/10 | HTTP-based (no imports), graceful degradation, local file fallback. |
| **Frontend Routing** | 8/10 | Clean lazy loading, ErrorBoundary on every route, edition gating. |
| **SSE Reconnection** | 9/10 | Exponential backoff + jitter + event replay. Production-ready. |
| **Command Palette** | 8/10 | 19 commands, keyboard nav, dynamic search, display ID resolve. |
| **Cost Tracking** | 7/10 | Dual ledger, budget enforcement, per-model breakdown. |
| **Bootstrap/Setup** | 8/10 | Idempotent init, clean scripts, proper env handling. |
| **Todo System** | 7/10 | Hub mirror + overlay + dependencies + display IDs. |

### What Needs Work

| Area | Score | Issue | Recommendation |
|------|-------|-------|----------------|
| **brain.json** | 4/10 | Single JSON file, no transactions, concurrent write risk | Migrate to `people` + `attention_rules` tables in platform.db |
| **queue.json** | 3/10 | Index-based access, brittle, no UUID keys | Migrate to `queue_items` table with UUID PKs |
| **Token Counting** | 5/10 | SDK = real tokens, CLI = word-count estimate. Costs diverge. | Standardize on SDK path or parse CLI output for actual tokens |
| **Alembic Migrations** | 3/10 | Only baseline exists. Schema changes are manual. | Create migration per schema change going forward |
| **ProjectDetailPage** | 4/10 | 1000+ LOC, 10 tabs, all rendered in DOM | Split into sub-components, lazy-load tabs |
| **Chat Recovery** | 4/10 | SSE close mid-stream = lost content, no retry | Save partial response, add retry button |
| **List Virtualization** | 4/10 | ContentList, TodoList, ActivityFeed render all items | Add @tanstack/react-virtual |
| **Memoization** | 5/10 | Only 51/116 components memoized. Jarvis overlay not memoized. | Memoize expensive components, especially Jarvis + Chat |
| **Error Handling** | 5/10 | ScopeContext silent on /tree failure, Inbox classify fails silently | Add error states + fallback UI everywhere |
| **useAgentSSE** | 4/10 | Redundant with useEventSource, manual EventSource parsing | Consolidate into single SSE hook |
| **Offline/Failure UX** | 4/10 | No warning when SSE disconnects (except small banner) | Add prominent offline indicator + graceful degradation |
| **Form Validation** | 4/10 | CreateAgentDialog, AddTodoDialog lack input validation | Add validation (zod + react-hook-form or similar) |

### Dead/Unused Code

| Item | Location | Status |
|------|----------|--------|
| `/people` route in CommandPalette | No PeoplePage exists | Dead reference |
| `/tasks` route in CommandPalette | No TasksPage exists | Dead reference |
| `ReplayList` component | ReplayPage uses iframe only | Unused |
| `useCardActions` hook | Trivially simple | Inline candidate |
| Zustand in package.json | Not imported anywhere | Unused dependency |

---

## 10. Full System Sequence: User Creates Agent

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant PM as ProcessManager
    participant Claude as Claude CLI
    participant DB as platform.db
    participant EB as EventBus
    participant SSE as SSE Stream

    User->>FE: Click "Spawn Agent"
    FE->>API: POST /api/agents/{id}/spawn
    API->>PM: spawn(agent_id, task)
    
    PM->>DB: Check budget cap
    DB-->>PM: OK (under limit)
    PM->>PM: Acquire semaphore (max 3)
    
    PM->>PM: build_coco_context()
    PM->>PM: build_yolo_constraints()
    PM->>PM: build_knowledge_context()
    
    alt SDK Path
        PM->>Claude: Anthropic API call
    else CLI Path (default)
        PM->>Claude: subprocess: claude -p --stream-json
    end
    
    PM->>DB: UPDATE agents SET status='running', pid=N
    PM->>EB: emit("agent.spawned")
    EB->>SSE: Push event
    SSE->>FE: SSE: agent.spawned
    FE->>FE: Update AgentsPage (3s polling)
    
    API-->>FE: 200 OK {status: "running"}

    loop Output Streaming (background thread)
        Claude->>PM: stdout chunks
        PM->>DB: INSERT agent_output (batch 10/2s)
        PM->>DB: UPDATE cost_ledger
    end

    Claude->>PM: Process exits (code 0)
    PM->>DB: UPDATE agents SET status='completed'
    PM->>PM: Release semaphore
    PM->>EB: emit("agent.completed")
    EB->>SSE: Push event
    SSE->>FE: SSE: agent.completed
    FE->>FE: Show completion notification
```

---

## 11. Recommended Priority Fixes

### P0 (Data Integrity)
1. **Migrate brain.json to platform.db** — concurrent writes can corrupt
2. **Migrate queue.json to platform.db** — index-based access is a bug waiting to happen
3. **Add Alembic migration workflow** — schema changes need version control

### P1 (UX Quality)
4. **Virtualize long lists** — ContentList, TodoList, ActivityFeed
5. **Split ProjectDetailPage** — 10 tabs in 1000+ LOC is unmaintainable
6. **Add chat stream recovery** — partial content loss on disconnect
7. **Consolidate SSE hooks** — useAgentSSE is redundant

### P2 (Reliability)
8. **Standardize token counting** — SDK vs CLI divergence under-reports costs
9. **Add form validation** — agent creation, todo creation have no input checks
10. **Improve offline UX** — prominent disconnection indicator
11. **Memoize Jarvis + Chat** — expensive re-renders on every state change

### P3 (Cleanup)
12. **Remove dead CommandPalette routes** — /people, /tasks pages don't exist
13. **Remove unused Zustand dependency**
14. **Inline useCardActions hook**

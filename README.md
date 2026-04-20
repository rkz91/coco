<div align="center">

# CoCo Platform

**Your AI agents, managed like a product team.**

CoCo is a local-first control plane for AI coding agents. It turns Claude Code sessions into a managed product team — with knowledge from your emails, voice memos, Jira, and Confluence feeding directly into agent context.

[Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [Knowledge Engine](#knowledge-engine) · [Contributing](CONTRIBUTING.md) · [License](#license)

[![Status](https://img.shields.io/badge/status-active-brightgreen)]() [![Articles](https://img.shields.io/badge/wiki--articles-13%2C371-blue)]() [![Model](https://img.shields.io/badge/LLM-gpt--5.4--nano-orange)]() [![Platform](https://img.shields.io/badge/macOS-launchd-lightgrey)]()

</div>

---

## Why CoCo?

AI coding agents are powerful but chaotic. You spawn them, lose track of what they're doing, and have no idea what they cost. CoCo fixes that:

- **One dashboard** for all your agents, tasks, and costs
- **Knowledge Hub** — emails, voice memos, Jira, Confluence all searchable in one place
- **Wiki engine** — auto-generated entity articles from every brain DB (13K+ articles today)
- **Smart inbox** — auto-classified items, draft approvals, decision queue
- **Real cost tracking** — per-agent, per-task token usage and spend
- **Trigger engine** — cron jobs, file watchers, webhooks that spawn agents

## Quick Start

**Development (full stack, two ports):**
```bash
git clone https://github.com/rijulkalra2000/Project-Coco.git
cd Project-Coco
./scripts/setup.sh
./scripts/dev.sh
```
Frontend at [http://localhost:5173](http://localhost:5173), backend API at [http://localhost:8000/api/](http://localhost:8000/api/).

**Production (launchd on macOS, single port):**
```bash
./scripts/start.sh     # bundled frontend served via FastAPI on port 3001
```

**Companion wiki (read-only entity articles):**
```bash
python3 ~/.coco/knowledge/wiki_server.py     # MediaWiki-style wiki on port 8888
```

## Features

### Core Edition (MIT — free forever)

| Feature | Description |
|---------|-------------|
| **Home Dashboard** | Project health, recent activity, quick actions |
| **Agent Management** | Spawn, monitor, and coordinate Claude Code agents |
| **Knowledge Hub** | Unified search across email, voice, Jira, Confluence |
| **Smart Inbox** | Auto-classified items, draft approvals, batch actions |
| **Todos & Goals** | Full lifecycle: backlog → in progress → done |
| **Chat** | Claude conversations with injected project context |
| **Cost Tracking** | Per-agent token usage, budgets, cost ledger |
| **Triggers** | Cron, file watch, webhook automation |
| **Portfolio Tree** | Hierarchical team → project → agent organization |
| **Templates** | Export/import project configurations |
| **Comments** | Threaded discussions on any entity |
| **Search** | Unified search across todos, agents, tasks, content |

### Studio Edition (BSL 1.1)

| Feature | Description |
|---------|-------------|
| **Jarvis Voice** | Cinematic voice assistant overlay with briefings |
| **TTS/STT** | Text-to-speech (Kokoro) and speech-to-text (Deepgram) |
| **Agent Replay** | Shareable HTML time-lapse of agent sessions |
| **Morning Podcast** | Auto-generated audio briefing of overnight activity |
| **Self-Improvement** | Agents that analyze and improve the platform itself |
| **Folder Analysis** | Deep document analysis pipeline |

> Studio features convert to MIT license on March 28, 2029.

## Architecture

```
┌─────────────────────────────────────┐
│           React 19 + Vite           │  ← Frontend (:5173 dev, :3001 prod)
│  Radix UI · Tailwind CSS 4 · Zustand│
└──────────────┬──────────────────────┘
               │ REST + SSE (/api/*)
┌──────────────┴──────────────────────┐
│         FastAPI + uvicorn           │  ← Backend (:8000 dev, :3001 prod)
│  SQLAlchemy Core · structlog        │
└──────┬───────────────┬──────────────┘
       │               │
┌──────┴──────┐ ┌──────┴──────┐ ┌──────────────┐
│  hub.db     │ │ platform.db │ │ knowledge.db │
│  (read-only)│ │ (read-write)│ │ (wiki RO)    │
│  KH owned   │ │ CoCo owned  │ │ KE owned     │
└─────────────┘ └─────────────┘ └──────┬───────┘
                                        │
                           ┌────────────┴─────────────┐
                           │  Knowledge Engine        │  ← ~/.coco/knowledge
                           │  cron.py · master_cron   │    (code in coco-dotfiles)
                           │  gpt-5.4-nano (QB GW)    │
                           │  pykeen KG trainer       │
                           │  wiki_server :8888       │
                           └──────────────────────────┘
```

- **hub.db** — Knowledge Hub's database. Opened read-only. Never written to by CoCo.
- **platform.db** — CoCo's own database. Agents, costs, todos overlay, governance log.
- **knowledge.db** — Wiki corpus (13K+ entity articles, FTS5-indexed, graph-linked).
- **SSE** — Server-Sent Events for real-time updates (not WebSocket).
- **SQLite WAL mode** — concurrent reads, single writer.
- **Single LLM rail** — gpt-5.4-nano via QB OpenAI Gateway. No Anthropic/CLI fallback.

## Knowledge Engine

The wiki engine lives at `~/.coco/knowledge/` (runtime data) with source code tracked separately in [`coco-dotfiles`](https://github.com/rijulkalra2000/coco-dotfiles). Runs as a set of launchd agents that harvest brain DBs, generate entity articles via `gpt-5.4-nano-2026-03-17` through the QB OpenAI Gateway, index them in FTS5, and train a pykeen knowledge graph over cross-project connections.

| Component | What it does | Schedule |
|---|---|---|
| `master_cron.py` | Orchestrates Phases 1-15 across 36+ projects | 01:00 + 14:00 daily |
| `cron.py` | Per-project harvest → article gen → FTS5 → backlinks | wrapped by master-cron |
| `article_writer.py` | Unified write path — dedup, versioning, FTS5 sync | library |
| `pykeen_bridge.py` | KG training daemon (TransE/RotatE, Adam-checkpointed) | KeepAlive |
| `wiki_server.py` | MediaWiki-style reader on port 8888 | manual or launchd |
| `knowledge-dashboard.py` | Queue + job control surface on port 9876 | KeepAlive |

**Article generation:** `~13K articles`, ≈$0.003 per article on gpt-5.4-nano, 20 parallel workers, deterministic confidence scoring gated by `COCO_CONFIDENCE_FLOOR` (default 0.90).

**Brain-DB schema:** versioned via `~/.claude/skills/brain/scripts/brain/schema.py`. Current `SCHEMA_VERSION = 6`. Idempotent migrations auto-apply on `migrate()` for legacy brains.

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
COCO_EDITION=core                    # or "studio"
PLATFORM_PORT=3001                   # prod single-port; dev uses 8000 backend + 5173 frontend
MAX_CONCURRENT_AGENTS=3

# Knowledge engine (overrides — defaults sensible):
COCO_GPT5_NANO_MODEL=gpt-5.4-nano-2026-03-17
COCO_CONFIDENCE_FLOOR=0.90           # min deterministic score to land an article
COCO_SCORE_DETERMINISTIC=1           # 0 reverts to LLM-self-confidence scoring
COCO_DISABLE_GPT5_NANO=0             # 1 forces legacy local path (MLX retired — reserved)
COCO_LOCAL_ONLY=1                    # raise on cloud failure instead of fallback
```

QB Gateway key lives at `~/.coco/.qb-gateway-key` (chmod 600, never checked in). See [docs/SETUP.md](docs/SETUP.md) for full configuration reference.

## Development

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && pnpm dev

# Tests
cd backend && uv run pytest
cd frontend && pnpm test
```

## License

CoCo Platform uses a dual license model:

- **Core** — [MIT License](LICENSE)
- **Studio** — [Business Source License 1.1](LICENSE-STUDIO), converting to MIT on March 28, 2029

You can use Core features freely in any project. Studio features require the BSL license until the change date.

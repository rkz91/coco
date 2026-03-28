# CoCo Platform — Claude Code Ecosystem Report

**Date:** 2026-03-28
**Author:** Rijul Kalra / Claude Opus 4.6
**Status:** Research Complete

---

## Table of Contents

1. [Top 20 Repos/Tools in the Claude Code Ecosystem](#1-top-20-repostools)
2. [Integration Opportunities](#2-integration-opportunities)
3. [Feature Inspiration](#3-feature-inspiration)
4. [Community Patterns](#4-community-patterns)
5. [MCP Server Opportunities](#5-mcp-server-opportunities)
6. [Claude Code API Changes](#6-claude-code-api-changes)
7. [Competing Agent Frameworks](#7-competing-agent-frameworks)
8. [Technical Debt Patterns](#8-technical-debt-patterns)
9. [Recommended Architecture Changes](#9-recommended-architecture-changes)

---

## 1. Top 20 Repos/Tools

Ranked by relevance to CoCo Platform, with ecosystem significance noted.

| # | Repo / Tool | Stars | What It Does | CoCo Relevance |
|---|-------------|-------|--------------|----------------|
| 1 | **[Superpowers](https://github.com/obra/superpowers)** | 94k+ | 7-phase TDD methodology as skills framework. Official Anthropic marketplace entry. | CoCo already uses GSD which is similar. Superpowers' skill format is the de facto standard. CoCo should ensure compatibility. |
| 2 | **[Claude Squad](https://github.com/smtg-ai/claude-squad)** | 5.6k | Terminal UI managing multiple Claude Code / Codex / Aider sessions via tmux + git worktrees. | Direct competitor to CoCo's agent panel. CoCo's web UI is richer but Claude Squad's worktree isolation is worth adopting. |
| 3 | **[awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)** | — | 135 agents, 35 skills, 42 commands, 150+ plugins, 19 hooks, 15 rules, 8 MCP configs. | Meta-resource. CoCo should be listed here. Skills and hooks from this collection should be testable in CoCo. |
| 4 | **[awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills)** | — | Curated skill directory with frontmatter conventions. | Reference for skill format standardization. CoCo's `SkillRegistry` should parse this format. |
| 5 | **[Repomix](https://github.com/yamadashy/repomix)** | 22.6k | Packs entire repo into single AI-friendly file with token counts. | CoCo agents could use Repomix to feed codebase context before spawning. Integrate as pre-spawn step. |
| 6 | **[Context7 MCP](https://github.com/upstash/context7)** | — | MCP server serving up-to-date library docs into prompts. | High-value MCP for CoCo agents to avoid hallucinating outdated API usage. |
| 7 | **[OpenCode](https://github.com/sst/opencode)** | — | Open-source Claude Code alternative supporting 75+ providers. | Watch for feature parity ideas. CoCo could support OpenCode as an alternative agent backend. |
| 8 | **[Claude Wrapper](https://github.com/ChrisColeTech/claude-wrapper)** | — | OpenAI-compatible HTTP API wrapper for Claude Code CLI. | CoCo's `process_manager.py` does similar work but CoCo could expose an OpenAI-compatible API for external tools. |
| 9 | **[OpenHands](https://github.com/All-Hands-AI/OpenHands)** | — | Open-source autonomous coding agent platform for teams. | Architectural inspiration for team-scale agent management. |
| 10 | **[OpenClaw](https://github.com/steipete/openclaw)** | 135k | Open-source tool by Peter Steinberger, built with Agent SDK. | Study its Agent SDK integration patterns for CoCo's own SDK usage. |
| 11 | **[claude-code-ultimate-guide](https://github.com/FlorianBruniaux/claude-code-ultimate-guide)** | — | Production-ready templates for all Claude Code features. | Reference for best practices. CoCo's documentation should align with community standards. |
| 12 | **[awesome-agent-skills (VoltAgent)](https://github.com/VoltAgent/awesome-agent-skills)** | — | 1000+ agent skills compatible with Claude Code, Codex, Gemini CLI, Cursor. | Cross-platform skill compatibility. CoCo should ensure its skill format works here. |
| 13 | **[claude-code-skills (levnikolaevich)](https://github.com/levnikolaevich/claude-code-skills)** | — | Full delivery lifecycle: Agile pipeline, multi-model review, hex-line editing, hex-graph code knowledge graph. | hex-graph (code knowledge graph) MCP is directly useful for CoCo's Knowledge Hub integration. |
| 14 | **[OpenWork](https://github.com/different-ai/openwork)** | — | Open-source alternative to Claude Cowork, built for teams on top of OpenCode. | Closest open-source analog to CoCo's team collaboration features. Study their approach. |
| 15 | **[Slack MCP Server](https://github.com/korotovsky/slack-mcp-server)** | 9k+ users | Full Slack integration — DMs, channels, history, no special permissions needed. | CoCo agents should be able to read/post to Slack for team notifications. |
| 16 | **[GitHub MCP Server](https://github.com/modelcontextprotocol/servers)** | 100/100 | Official GitHub integration — repos, PRs, issues, code search. | Must-have for CoCo agents doing code work. Already likely available but should be default-configured. |
| 17 | **[Memory MCP](https://github.com/modelcontextprotocol/servers)** | — | Knowledge graph-based persistent memory for Claude. | CoCo already has brain.json; Memory MCP could supplement or replace it. |
| 18 | **[Desktop Commander MCP](https://desktopcommander.app/)** | 94/100 | Enhanced filesystem operations beyond basic FS MCP. | Useful for CoCo agents that need to interact with files on the user's machine. |
| 19 | **[Aider](https://github.com/paul-gauthier/aider)** | — | Terminal AI coding with 100+ language support, Git-native, multi-provider. | CoCo could support Aider as an alternative agent backend alongside `claude -p`. |
| 20 | **[Shipyard](https://shipyard.build/)** | — | Multi-agent orchestration layer specifically for Claude Code. | Study their orchestration patterns; CoCo's ProcessManager serves a similar role. |

---

## 2. Integration Opportunities

### Tier 1 — Immediate Value (next 2 phases)

| Integration | Effort | Value | How |
|---|---|---|---|
| **Claude Code Agent Teams (TeammateTool)** | Medium | Critical | CoCo's ProcessManager spawns individual `claude -p` processes. Anthropic's built-in TeammateTool (released Feb 2026 with Opus 4.6) provides native multi-agent orchestration with 13 operations. CoCo should offer a toggle: use native swarm mode OR CoCo's own orchestration. Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=true`. |
| **Context7 MCP** | Low | High | Pre-configure Context7 as a default MCP server for all CoCo agents. Eliminates outdated-docs hallucination. |
| **Repomix pre-flight** | Low | High | Before spawning an agent on a codebase, run `repomix` to generate a context file. Inject path into agent prompt. |
| **Superpowers skill compatibility** | Low | High | Ensure CoCo's SkillRegistry can parse Superpowers' `.skill` frontmatter format (description, keywords, auto-invoke triggers). |

### Tier 2 — Medium-term (phases 5-8)

| Integration | Effort | Value | How |
|---|---|---|---|
| **Slack MCP for notifications** | Medium | High | When an agent completes/fails, post to a Slack channel. Use korotovsky/slack-mcp-server. |
| **GitHub MCP as default** | Low | Medium | Auto-configure GitHub MCP for agents working on repos. |
| **OpenAI-compatible API** | Medium | Medium | Expose CoCo's agent management via OpenAI-compatible HTTP API so external tools (Cursor, Continue) can use CoCo as a backend. |
| **Claude Agent SDK migration** | High | High | Replace raw `subprocess.Popen` of `claude -p` with the official Claude Agent SDK (Python). Gains: structured tool calling, safety hooks, usage tracking, streaming events. |

### Tier 3 — Future (phases 9-12)

| Integration | Effort | Value | How |
|---|---|---|---|
| **Multi-provider support (OpenCode/Aider)** | High | Medium | Allow agents to use non-Claude backends for cost-sensitive tasks. |
| **LangGraph for complex workflows** | High | Medium | For multi-step, stateful agent pipelines (e.g., research -> plan -> implement -> review), LangGraph's graph-based orchestration is more robust than CoCo's current linear spawn model. |
| **Prompt caching / Message Batches API** | Medium | High | Use Anthropic's batch API (50% cost reduction) for non-urgent agent tasks. |

---

## 3. Feature Inspiration

### From Claude Code Native Features

| Feature | Source | CoCo Adoption |
|---|---|---|
| **Voice mode** (`/voice`) | Claude Code March 2026 | CoCo already has voice infrastructure in `cli/src/voice/`. Ensure it works with the platform's chat interface. |
| **Loop/scheduled tasks** (`/loop`) | Claude Code March 2026 | CoCo should support cron-like agent scheduling (e.g., "run cost audit every 6 hours"). Backend already has the scheduling primitives. |
| **1M context window** | Opus 4.6 beta | CoCo agents should default to extended context for large codebase tasks. Surface context usage in the UI. |
| **Hooks (PreToolUse, PostToolUse)** | Claude Code v1.0 | CoCo should allow users to define hooks per-agent (e.g., "before any file write, lint the file"). Store hook configs in platform.db. |
| **X-Claude-Code-Session-Id header** | March 2026 API change | CoCo should capture this header to correlate API usage with specific agents for cost tracking. |

### From Competing Platforms

| Feature | Source | CoCo Adoption |
|---|---|---|
| **Git worktree isolation** | Claude Squad | Each CoCo agent should work in its own git worktree, preventing branch conflicts. Claude Squad's tmux+worktree pattern is proven. |
| **Org chart / reports-to hierarchy** | OpenAI Codex app | CoCo already has this (`/api/agents/org-chart`). Enhance with drag-and-drop reorganization in the UI. |
| **Agent-to-agent direct communication** | Claude Code Swarm | CoCo agents currently only communicate through the lead agent. Add peer-to-peer messaging via shared context files or a lightweight message bus. |
| **Cost prediction before spawn** | Codex / Windsurf | Before spawning an agent, estimate token cost based on task complexity + model. Show in the UI with a "proceed?" confirmation. |
| **Competing hypotheses pattern** | Claude Code Agent Teams docs | Spawn multiple agents with different approaches to the same problem, compare results, pick the best. CoCo's analysis_jobs table partially supports this. |
| **Air-gapped mode** | OpenCode | For McKinsey's security-sensitive projects, allow running agents against local models via Ollama. |

### From Agent Frameworks

| Feature | Source | CoCo Adoption |
|---|---|---|
| **Role-based agent templates** | CrewAI | CoCo's `agent_roles` table is the right foundation. Expand with rich role templates (PM, architect, security reviewer, test engineer) with pre-built system prompts. |
| **Graph-based workflow definition** | LangGraph | For complex multi-agent pipelines, allow users to define agent workflows as directed graphs in the UI. |
| **Human-in-the-loop checkpoints** | LangGraph, Devin | CoCo's decision queue already supports this. Enhance by allowing agents to pause and request human input mid-task. |
| **Agent evaluation / grading** | Promptfoo, LangSmith | After agent completion, auto-evaluate output quality. Track agent success rates over time per role. |

---

## 4. Community Patterns

### How People Use Claude Code

1. **Solo dev with 1-3 agents**: The most common pattern. One "main" Claude Code session + 1-2 background agents for tests/reviews. CoCo's sweet spot.

2. **Team lead with agent swarm**: A lead session decomposes work, spawns 3-5 subagents, synthesizes results. CoCo's `reports_to` and org-chart model fits this exactly.

3. **Skill-driven development**: Developers install 5-10 skills (Superpowers, GSD, custom) and invoke them via slash commands. Over 60% of advanced users create custom commands in their first week.

4. **MCP-augmented agents**: Power users configure 3-5 MCP servers (GitHub, filesystem, Slack, database, docs) to give agents access to external systems.

5. **Continuous background agents**: Using `/loop` and scheduled tasks for ongoing monitoring (PR reviews, deployment health, cost tracking). This is emerging and CoCo should lead here.

### Skill Ecosystem Conventions

- Skills use Markdown files with optional YAML frontmatter
- Standard frontmatter: `description`, `keywords`, `auto-invoke` (trigger patterns)
- Skills are stored in `~/.claude/commands/` (global) or `.claude/commands/` (project)
- The VoltAgent awesome-agent-skills repo shows cross-platform skill compatibility is becoming standard (Claude Code, Codex, Gemini CLI, Cursor)

### Pain Points CoCo Can Solve

| Pain Point | Frequency | CoCo's Answer |
|---|---|---|
| **Rate limit exhaustion** | #1 complaint | CoCo's cost tracking + budget alerts. Pause agents before limits hit. |
| **Session loss on token exhaustion** | Very common | CoCo preserves agent output in platform.db. Context survives session death. |
| **No visibility into agent work** | Common | CoCo's real-time log viewer + SSE events. |
| **Multi-session conflicts** | Common | CoCo's per-agent working directories + git worktree isolation. |
| **Quality regression detection** | Emerging | CoCo could track agent success rates over time, flag model regressions. |
| **Context pollution** | Very common | CoCo spawns fresh agents per task (no context pollution by design). |

---

## 5. MCP Server Opportunities

### Must-Have (configure by default for CoCo agents)

| MCP Server | Why |
|---|---|
| **Filesystem MCP** | Already built-in. Ensure it's properly sandboxed per-agent working directory. |
| **GitHub MCP** | Essential for any code-related agent work. Auto-detect if cwd is a git repo and configure. |
| **Context7** | Eliminates outdated-docs hallucination. Zero-config value. |
| **Knowledge Hub MCP** | CoCo already has this (`mcp__knowledge-hub__*`). Ensure all agents can access it. |

### High-Value Optional

| MCP Server | Why |
|---|---|
| **Slack MCP** | Team notifications, reading channel context for agent tasks. |
| **PostgreSQL / SQLite MCP** | For agents working on data-heavy tasks. |
| **Playwright MCP** | For agents doing E2E testing or web scraping. |
| **Chrome DevTools MCP** | For frontend debugging agents. |

### CoCo-Specific MCP Servers to Build

| MCP Server | Purpose |
|---|---|
| **CoCo Platform MCP** | Expose CoCo's own API (agents, projects, tree, costs) as an MCP server so Claude Code sessions can query/control CoCo directly. |
| **Brain MCP** | Expose brain.json (people graph, rules) as an MCP tool. Agents could query "who owns this project?" or "what are the attention rules for Pankaj?" |
| **Session History MCP** | Expose `~/.coco/sessions/` as searchable context. Agents could reference past conversations. |

---

## 6. Claude Code API Changes

### Recent Changes to Adapt To

| Change | Date | CoCo Impact |
|---|---|---|
| **`output_format` moved to `output_config.format`** | March 2026 | CoCo's ProcessManager uses `--output-format stream-json`. Verify CLI flag still works; plan migration to new SDK format. |
| **`X-Claude-Code-Session-Id` header** | March 2026 | Capture in proxy/middleware for per-agent cost attribution. |
| **1M context window (Opus 4.6 beta)** | Feb 2026 | Allow agents to opt into extended context. Surface token usage in UI. |
| **Message Batches API (50% cost)** | 2026 | Non-urgent agent tasks (analysis, documentation) should use batch API. |
| **Haiku 3 deprecation (April 19, 2026)** | March 2026 | Update any Haiku references in agent role defaults. |
| **Sonnet 4.6 launch** | March 2026 | Add as model option in agent creation UI. Good balance of speed/quality for everyday tasks. |

### Upcoming Features to Prepare For

| Feature | Status | CoCo Preparation |
|---|---|---|
| **Agent Teams GA** | Experimental (flag-gated) | CoCo should have a toggle to use native Teams vs. CoCo's own orchestration. Both should work. |
| **Computer Use** | Research preview | CoCo agents could use Computer Use for GUI automation tasks. Prepare UI to show screenshots from Computer Use sessions. |
| **Voice mode** | Rolling out | CoCo's voice infrastructure should interop with Claude Code's native voice. |
| **Remote Control** | Research preview | Could allow CoCo to be controlled remotely — useful for mobile access to the dashboard. |

---

## 7. Competing Agent Frameworks

### Direct Competitors to CoCo

| Platform | Strengths | Weaknesses vs CoCo |
|---|---|---|
| **OpenAI Codex App** | 2M+ weekly users, multi-agent UI, GPT-5.3-Codex model, Windows+Mac | Locked to OpenAI ecosystem. No local-first. No existing CoCo/KH data integration. |
| **Claude Squad** | Simple, proven tmux+worktree model, supports multiple agent backends | Terminal-only. No web UI, no project hierarchy, no cost tracking, no decision queue. |
| **Devin** | Fully autonomous, handles complex multi-service architectures | $500/month. Overkill for PM workflows. No CLI integration. |
| **Windsurf** | IDE-native, $15/month flat, good for professional dev | IDE-bound. Not a control plane. No multi-agent. |
| **OpenWork** | Open-source team collaboration on top of OpenCode | Early stage. No equivalent to CoCo's brain.json, decision queue, or Knowledge Hub. |

### Agent Frameworks (not direct competitors, but architectural references)

| Framework | Status (March 2026) | CoCo Takeaway |
|---|---|---|
| **CrewAI** | Active, fastest time-to-production for role-based teams | CoCo's agent_roles + org-chart is already CrewAI-like. Validate that CoCo's role templates are as rich as CrewAI's. |
| **LangGraph** | Production leader for stateful workflows, LangSmith observability | CoCo should add graph-based workflow visualization. LangSmith-style observability (traces, latency, cost per step) is a gap. |
| **AutoGen** | Maintenance mode (Microsoft shifting to broader Agent Framework) | Avoid building on AutoGen patterns. Microsoft's direction is unclear. |
| **Google ADK** | GA, 7M+ downloads, supports Gemini 3 | If CoCo adds multi-provider support, ADK's agent patterns are worth studying. |

### Strategic Positioning

CoCo occupies a unique niche: **local-first PM control plane for Claude Code**. No competitor combines:
- Project hierarchy (teams > projects > agents)
- Knowledge Hub integration (content pipeline)
- Decision queue (human-in-the-loop governance)
- Brain.json (people graph + attention rules)
- Cost tracking with budget alerts
- Chat that preserves MCP tools

The closest competitor is OpenAI's Codex App (multi-agent UI), but it lacks the PM/governance layer that makes CoCo unique.

---

## 8. Technical Debt Patterns

### Common Mistakes in Claude Code Wrappers

| Anti-Pattern | Description | CoCo Status |
|---|---|---|
| **Raw subprocess without structured output** | Spawning `claude -p` and parsing stdout as text instead of using stream-json | CoCo uses `--output-format stream-json` — GOOD. But should migrate to Agent SDK for structured events. |
| **No timeout / runaway agents** | Agents running indefinitely, consuming tokens | CoCo has `AGENT_TIMEOUT_MINUTES` — GOOD. |
| **No cost attribution** | Can't tell which agent/task consumed how many tokens | CoCo has cost_ledger table but needs to capture `X-Claude-Code-Session-Id` for precise attribution. |
| **Monolithic CLAUDE.md** | Over-specified instructions where important rules get lost | CoCo should split agent instructions: base rules (CLAUDE.md) + role-specific rules (per agent_role). |
| **No worktree isolation** | Multiple agents writing to the same branch, causing conflicts | CoCo should adopt git worktree per agent (from Claude Squad). |
| **Kitchen-sink sessions** | Mixing unrelated tasks in one agent session, polluting context | CoCo's model (one agent = one task) prevents this by design — GOOD. |
| **No output persistence** | Session output lost when agent dies | CoCo persists to `agent_output` table — GOOD. |
| **Ignoring exit codes** | Not distinguishing clean completion from failure | CoCo tracks exit_code and sets status accordingly — GOOD. |
| **Runtime blindness** | Code passes static checks but fails in production (concurrency, connection limits) | CoCo should add runtime validation hooks (PostToolUse hooks that run tests). |
| **66% productivity tax** | AI-generated code that's "almost right" requiring manual fixes | CoCo's verify-work / UAT pattern (from GSD) mitigates this. Ensure all agents have verification steps. |

### CoCo-Specific Technical Debt to Address

1. **ProcessManager uses raw Popen**: Should migrate to Claude Agent SDK for structured tool calling, safety hooks, and streaming events.
2. **No git worktree isolation**: Agents share the same working directory. Risk of branch conflicts.
3. **Agent output stored as raw text**: Should parse stream-json events and store structured data (tool calls, results, cost events).
4. **No MCP server configuration per agent**: All agents get the same environment. Should allow per-role MCP configs.
5. **Hardcoded model list**: Model options should be dynamically fetched or at least easily configurable.
6. **No agent-to-agent communication**: Agents can only report back to the orchestrator, not to each other.

---

## 9. Recommended Architecture Changes

### Priority 1: Agent SDK Migration

**Current:** `subprocess.Popen(["claude", "-p", "--output-format", "stream-json", task])`
**Target:** Use the official Claude Agent SDK (Python) which provides:
- Structured tool calling with type-safe parameters
- Safety hooks (PreToolUse, PostToolUse)
- Streaming events with proper typing
- Built-in usage tracking (tokens, cost)
- Session management

**Impact:** Eliminates raw stdout parsing, enables cost attribution, unlocks hooks.

### Priority 2: Git Worktree Isolation

**Current:** Agents share `working_directory` (often the same repo).
**Target:** On agent spawn, create a git worktree for the agent's branch:
```
git worktree add /tmp/coco-agents/{agent_id} -b agent/{agent_id}
```
On completion, merge back and remove worktree.

**Impact:** Eliminates branch conflicts, enables true parallel agent work.

### Priority 3: Native Agent Teams Toggle

**Current:** CoCo manages agents individually via ProcessManager.
**Target:** Offer two modes:
1. **CoCo-managed**: Current model. CoCo spawns/monitors/kills agents.
2. **Native swarm**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=true`, let Claude Code's TeammateTool handle orchestration. CoCo provides the UI and monitoring.

**Impact:** Users get the best of both worlds. CoCo adds value even when using native teams.

### Priority 4: Per-Agent MCP Configuration

**Current:** All agents inherit the host environment's MCP config.
**Target:** Store MCP server configs per agent_role in platform.db. On spawn, generate a temporary `.claude/settings.json` in the agent's worktree with the role-specific MCP servers.

**Impact:** Security-review agents get different tools than test-writing agents.

### Priority 5: Structured Output Storage

**Current:** Agent output stored as raw text chunks in `agent_output`.
**Target:** Parse stream-json events and store structured records:
- `agent_events` table: `{agent_id, event_type, tool_name, input, output, tokens_in, tokens_out, cost, timestamp}`
- Enables: cost breakdown per tool call, tool usage analytics, replay of agent sessions.

**Impact:** Unlocks LangSmith-style observability for CoCo agents.

### Priority 6: CoCo Platform MCP Server

**Current:** CoCo is only accessible via its web UI and REST API.
**Target:** Build an MCP server that exposes CoCo's capabilities:
- `coco_list_agents` — list active agents
- `coco_spawn_agent` — create and start an agent
- `coco_get_project_tree` — get project hierarchy
- `coco_check_budget` — check cost budget status
- `coco_queue_decision` — add a decision to the queue

**Impact:** Any Claude Code session (not just CoCo-managed ones) can interact with CoCo, making it the central nervous system.

---

## Sources

- [awesome-claude-code (hesreallyhim)](https://github.com/hesreallyhim/awesome-claude-code)
- [awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)
- [awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills)
- [Superpowers](https://github.com/obra/superpowers)
- [Claude Squad](https://github.com/smtg-ai/claude-squad)
- [Claude Code Agent Teams Docs](https://code.claude.com/docs/en/agent-teams)
- [Claude Code Skills Docs](https://code.claude.com/docs/en/skills)
- [Claude Code Changelog](https://code.claude.com/docs/en/changelog)
- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Context7 MCP](https://github.com/upstash/context7)
- [Slack MCP Server](https://github.com/korotovsky/slack-mcp-server)
- [MCP Servers (Official)](https://github.com/modelcontextprotocol/servers)
- [OpenCode vs Claude Code](https://www.builder.io/blog/opencode-vs-claude-code)
- [OpenWork](https://github.com/different-ai/openwork)
- [Claude Code Issues (GitHub)](https://github.com/anthropics/claude-code/issues)
- [Claude Code Pain Points (MacRumors)](https://www.macrumors.com/2026/03/26/claude-code-users-rapid-rate-limit-drain-bug/)
- [OpenAI Codex App](https://openai.com/index/introducing-the-codex-app/)
- [GPT-5.3-Codex](https://openai.com/index/introducing-gpt-5-3-codex/)
- [Vertex AI Agent Builder](https://cloud.google.com/products/agent-builder)
- [LangGraph vs CrewAI vs AutoGen (2026)](https://medium.com/data-science-collective/langgraph-vs-crewai-vs-autogen-which-agent-framework-should-you-actually-use-in-2026-b8b2c84f1229)
- [Claude Code Swarm Orchestration (Addy Osmani)](https://addyosmani.com/blog/claude-code-agent-teams/)
- [TeammateTool Discovery](https://paddo.dev/blog/claude-code-hidden-swarm/)
- [Repomix](https://github.com/yamadashy/repomix)
- [Shipyard Multi-Agent](https://shipyard.build/blog/claude-code-multi-agent/)
- [Claude Code Technical Debt Guide (Pixelmojo)](https://www.pixelmojo.io/blogs/claude-code-technical-debt-mitigation-guide)
- [Best MCP Servers (SkillsIndex)](https://skillsindex.dev/blog/complete-guide-mcp-servers-2026/)
- [VoltAgent awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)

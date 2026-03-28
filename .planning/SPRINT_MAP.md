# CoCo Platform — Sprint Map (10-day cap per sprint)

**Updated:** 2026-03-28

---

## Completed

| Sprint | Theme | Days | Status |
|--------|-------|------|--------|
| 1 | 12-Phase Build (Foundation → Polish) | ~46 | DONE — 99%, 96/97 criteria |
| 2 | Restructure + Audit Fixes | ~7 | DONE — hierarchy, 28 fixes, 31 stabilization fixes, 4 foundation workstreams |
| 3 | Build What Competitors Can't | 10 | DONE — 10/10 features + UX wins + durable EventBus + smoke tests + inbox batch |

## Planned

| Sprint | Theme | Days | Status |
|--------|-------|------|--------|
| **4** | **The Big Three** | **10** | Ready to start |
| **5** | **CoCo as Nervous System** | **6** | Planned |
| **6** | **Deep Intelligence** | **10** | Outlined |
| **7** | **Self-Improvement + Replay** | **10** | Outlined |
| **8** | **Open-Source Prep** | **10** | Vision |
| **9** | **Launch** | **10** | Vision |

---

## Sprint 4: The Big Three (10 days)

| Day | Stream A (Frontend) | Stream B (Agent SDK) | Stream C (Knowledge) |
|-----|---------------------|----------------------|----------------------|
| 1 | Unify Chat: JarvisOverlay component | SDK: agent_sdk_client.py wrapper | Auto-classifier service |
| 2 | Unify Chat: wire into HomePage | SDK: migrate jarvis.py fallback | Auto-classifier: Haiku calls |
| 3 | (done) | SDK: migrate chat.py streaming | Auto-classifier: suggestions tab |
| 4 | | SDK: chat.py testing + parity | Agent context injection from KH |
| 5 | | SDK: ProcessManager migration start | Content-to-action (regex pass) |
| 6 | | SDK: ProcessManager async reader | (done) |
| 7 | | SDK: cost tracking (real tokens) | |
| 8 | | SDK: testing + feature flag | |
| 9 | | SDK: parallel run validation | |
| 10 | | SDK: cleanup + docs | |

**Deliverables:**
- Jarvis merged into Home as overlay, /jarvis → redirect
- Agent SDK replaces subprocess.Popen (behind feature flag)
- Real token counts in cost_ledger
- Auto-classifier with >0.85 confidence auto-routes
- Agent context injection from Knowledge Hub

---

## Sprint 5: CoCo as Nervous System (6 days)

| Day | Work |
|-----|------|
| 1 | MCP server skeleton (`backend/app/mcp/server.py`) + 8 core tools (activate, decide, search, status, health, cost, process, session_log) |
| 2 | 14 remaining MCP tools (briefing, context, teach, forget, people, yolo_activate, yolo_classify, approve, reject, todo_list, todo_add, todo_done, verify, mode) |
| 3 | Rewrite SKILL.md: 42K → 3K tokens (thin routing table + personality + dashboard format) |
| 4 | Platform orchestration: brain context injection + YOLO permissions into spawned agents |
| 5 | Verification gate service (`verification.py`) + wire into workflows + self-improve gate integration |
| 6 | Auto-activation hook + queue sync + events.jsonl bridge + integration testing |

**Deliverables:**
- CoCo skill: 42K → 3K tokens (93% reduction)
- 22 MCP tools on Platform backend
- Auto-activation on every Claude Code session (zero manual `/coco`)
- All spawned agents get brain.json context + YOLO permissions
- Verification gates as a reusable service
- Decision queue synced between CLI and Platform

---

## Sprint 6: Deep Intelligence (10 days)

| Day | Work |
|-----|------|
| 1-3 | Agent SDK completion (Week 2-3: edge cases, session persistence, subagent support) |
| 4-6 | Cross-source insight engine (entity extraction + FTS similarity + insights table + frontend) |
| 7-8 | Content-to-action pipeline (LLM pass for emails/meetings, platform.db staging, YOLO/careful modes) |
| 9-10 | Self-Improvement: full cycle with gates (PM → Dev → Review → Approve), git worktree isolation |

---

## Sprint 7: Self-Improvement + Replay (10 days)

| Day | Work |
|-----|------|
| 1-3 | CoCo Builds Itself: frontend (SelfImprovePage, ImprovementCard, DiffViewer) |
| 4-5 | CoCo Builds Itself: self-triggered weekly cron + decision queue integration |
| 6-8 | Agent Replay: shareable HTML time-lapse of agent sessions |
| 9-10 | Morning Podcast Briefing: auto-generated 2-3min audio of overnight activity |

---

## Sprint 8: Open-Source Prep (10 days)

| Day | Work |
|-----|------|
| 1-4 | Core/Studio split (free: PM dashboard + agent mgmt + KH, paid: Jarvis + voice + replay + analytics) |
| 5-6 | README, docs, contributing guide, license |
| 7-8 | Cost Leaderboard (anonymous opt-in community benchmarks) |
| 9-10 | Security hardening for public release (auth, rate limiting, secrets audit) |

---

## Sprint 9: Launch (10 days)

| Day | Work |
|-----|------|
| 1-2 | HN launch post + demo video |
| 3-4 | Community setup (Discord, GitHub Discussions, issue templates) |
| 5-7 | Polish pass (empty states, error messages, loading skeletons, accessibility) |
| 8-10 | Onboarding flow (first-run wizard, sample data, guided tour) |

---

## Decision Log

| Decision | Date | Rationale |
|----------|------|-----------|
| Home + Analytics stay separate | 2026-03-28 | User preference — Home = daily driver, Analytics = data/trends |
| Home + Jarvis merge (Jarvis = overlay) | 2026-03-28 | Product team consensus — reduce to 2 chat modes |
| 10-day sprint cap | 2026-03-28 | Predictable cadence, overflow moves to next sprint |
| Agent SDK migration split across S4+S6 | 2026-03-28 | Too big for one sprint (2-3 weeks) |
| CoCo Builds Itself split across S6+S7 | 2026-03-28 | Foundation in S6, frontend+polish in S7 |
| Slim CoCo Skill (42K→3K) in S5 | 2026-03-28 | Highest ROI — saves tokens every session |

# Sprint 9 Plan: "Launch"

**Date:** 2026-03-28
**Duration:** 10 days
**Prerequisites:** Sprint 8

---

## Workstream A: HN Launch + Demo Video (Days 1-2)

### Hacker News Post

**Title:** Show HN: CoCo — An AI PM cockpit for Claude Code (local-first, open-source)

**Hook:** "What if your AI agents had a project manager watching over them?"

### Differentiators

| Competitor | Gap CoCo Fills |
|------------|---------------|
| Paperclip | No PM layer — CoCo adds oversight, decisions, cost tracking |
| Linear | SaaS, not local — CoCo runs entirely on your machine |
| Cursor | IDE-bound — CoCo is IDE-agnostic, works with any editor |
| Claude Squad | Terminal-only — CoCo provides a full visual control plane |

### Assets

4 screenshots for the post:
1. **Home briefing** — morning dashboard with podcast player and activity summary
2. **Jarvis cinematic** — voice interface with the orb animation
3. **Cost tracking** — per-agent and per-project cost breakdown
4. **Agent org chart** — team → project → agent hierarchy view

### Demo Video (90 seconds)

Sequence: Home → Jarvis voice command → Agents spawning → Inbox decisions → Cost dashboard → Knowledge Hub → end card with GitHub link

Save final HN post draft to `.planning/LAUNCH_HN_POST.md`.

---

## Workstream B: Community Setup (Days 3-4)

### Discord Server

8 channels:
- `#welcome` — rules, getting started, links
- `#general` — open discussion
- `#show-and-tell` — share your CoCo setups and workflows
- `#help` — troubleshooting and Q&A
- `#bug-reports` — structured bug reporting (template pinned)
- `#feature-requests` — ideas and voting
- `#contributing` — dev discussion, PR reviews, architecture
- `#releases` — changelog announcements (webhook from GitHub)

### GitHub

- 3 issue templates: `bug_report.yml`, `feature_request.yml`, `question.yml`
- PR template with checklist
- `config.yml` for issue template chooser
- `CONTRIBUTING.md` finalized (from Sprint 8)
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1

### Good First Issues

Label 10-15 tickets as `good first issue`:
- Small, well-scoped tasks with clear acceptance criteria
- Mix of frontend and backend
- Each linked to relevant code files
- Response commitment: within 24 hours

---

## Workstream C: Polish Pass (Days 5-7)

### Day 5: Accessibility Audit

- Run `axe-core` audit on all 16 pages
- Add `aria-labels` on all icon-only buttons (~40 instances)
- Landmark roles (`main`, `nav`, `aside`, `header`) on all page layouts
- `aria-live` regions for SSE-updated content (agent status, chat messages)
- Focus order verification on top-5 most-used pages

### Day 6: Empty States + Loading Skeletons

Pattern for every page:
- **Loading:** Skeleton shimmer matching content layout
- **Empty:** Icon + CoCo-voice heading + CTA button
- **Error:** Friendly message + retry button

16-page audit:
| Page | Loading | Empty | Error |
|------|---------|-------|-------|
| Home | Skeleton | Welcome wizard | Retry |
| Projects | Skeleton | "No projects yet" + Create | Retry |
| Agents | Skeleton | "No agents recruited" + Recruit | Retry |
| Chat | Skeleton | "Start a conversation" | Retry |
| Inbox | Skeleton | "All caught up" | Retry |
| Knowledge | Skeleton | "Knowledge Hub empty" + Import | Retry |
| Todos | Skeleton | "Nothing to do" + Add | Retry |
| Goals | Skeleton | "No goals set" + Create | Retry |
| Tasks | Skeleton | "No tasks" + Create | Retry |
| Costs | Skeleton | "No cost data yet" | Retry |
| Settings | Skeleton | N/A | Retry |
| Tree | Skeleton | "Empty tree" | Retry |
| Activity | Skeleton | "No activity yet" | Retry |
| Replay | Skeleton | "No replays" + Generate | Retry |
| Self-Improve | Skeleton | "Run first cycle" + Start | Retry |
| Jarvis | Skeleton | "Say something" | Retry |

### Day 7: Performance + Contrast

- Lighthouse score >90 on Home page (Performance, Accessibility, Best Practices)
- Color contrast WCAG AA compliance on all text
- Touch targets minimum 44x44px
- Lazy-load heavy pages (Replay, Self-Improve, Costs charts)

---

## Workstream D: Onboarding Flow (Days 8-10)

### Day 8: Backend

- `onboarding.py` router — state management, sample data loader
- `onboarding_state` table — tracks wizard progress per install
- Sample data loader: creates demo team, 2 projects, 5 todos, 2 agents, 3 knowledge items

### Schema

```sql
CREATE TABLE onboarding_state (
    id         TEXT PRIMARY KEY DEFAULT 'default',
    step       INTEGER DEFAULT 0,
    completed  INTEGER DEFAULT 0,
    data       TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### Day 9: OnboardingWizard.tsx

5-step wizard:
1. **Welcome** — "Meet CoCo, your AI project manager" + edition display
2. **Connect Source** — point to a project directory or GitHub repo
3. **First Briefing** — generate and show a sample Home briefing
4. **First Agent** — recruit an agent on a small task (live demo)
5. **Done** — summary + "Explore CoCo" CTA

### Day 10: Progressive Discovery

- `FeatureTooltip.tsx` — 6 contextual tooltips on first visit to each major page
  - Tracks seen state in `localStorage`
  - Dismissible, non-blocking
- `DidYouKnow.tsx` — rotating tips on Home page ("Did you know you can talk to Jarvis?")
- `ShortcutsTour.tsx` — triggered by `?` key, modal with all keyboard shortcuts

### Files

| New | Modified |
|-----|----------|
| `backend/app/routers/onboarding.py` | `frontend/src/App.tsx` |
| `frontend/src/components/onboarding/OnboardingWizard.tsx` | `frontend/src/pages/HomePage.tsx` |
| `frontend/src/components/shared/FeatureTooltip.tsx` | |
| `frontend/src/components/shared/DidYouKnow.tsx` | |
| `frontend/src/components/shared/ShortcutsTour.tsx` | |

---

## Deliverables Checklist

- [ ] HN post final draft saved in `.planning/LAUNCH_HN_POST.md`
- [ ] 90-second demo video uploaded to YouTube
- [ ] Discord server live with 8 channels
- [ ] GitHub issue templates committed
- [ ] 10-15 issues labeled `good first issue`
- [ ] All 16 pages verified: loading + empty + error states
- [ ] WCAG AA accessibility pass (axe-core clean)
- [ ] Lighthouse >90 on Home page
- [ ] Onboarding wizard functional with sample data option
- [ ] Feature tooltips + keyboard shortcuts tour working

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Demo video production takes too long | Fallback: 4 annotated screenshots + GIF |
| HN post doesn't get traction | Multi-channel distribution: Reddit r/ChatGPT, r/ClaudeAI, Twitter/X, Discord communities |
| Sprint 8 runs late | Defer onboarding (Workstream D), launch with polish-only (Workstreams A-C) |

---

## Sprint 5.5 Compatibility Addendum

> Sprint 5.5 introduces SQLAlchemy Core + hub mirror tables. All new code in Sprint 9+ MUST use SA Core, not raw sqlite3.

### Schema changes (1 table → SA Core definition in `tables.py`)

| Raw SQL in this plan | SA Core replacement |
|---|---|
| `CREATE TABLE onboarding_state` (line 130) | `onboarding_state = Table("onboarding_state", metadata, ...)` in `tables.py` |

### Connection pattern changes

`onboarding.py` router uses `get_db()` from `app.db.session`:

```python
from app.db.session import get_db
from app.db.tables import onboarding_state, nodes, agents

with get_db() as conn:
    conn.execute(onboarding_state.insert().values(id="default", step=0, ...))
```

### Sample data loader

The onboarding sample data loader (Day 8: "demo team, 2 projects, 5 todos, 2 agents, 3 knowledge items") must use SA Core inserts into platform tables. Do NOT read from `get_hub_db()` — use `hub_*` mirror tables if hub data is needed for seeding.

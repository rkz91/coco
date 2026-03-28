# Sprint 5 Plan: "CoCo as the Nervous System"

**Date:** 2026-03-28
**Duration:** 6 days (within 10-day cap)
**Prerequisites:** Sprint 4 complete

---

## The Problem

CoCo's SKILL.md is 164KB / ~42K tokens. Loading it consumes 4.2% of the 1M context window on every `/coco` activation. The skill is monolithic — 27 sections, most unused in any session.

Additionally, CoCo CLI and CoCo Platform are disconnected — they share data files but don't orchestrate each other.

## The Solution: Three-Layer Architecture

```
Layer 1: Thin Skill (~3K tokens)     ← Always in context
         Routing table + personality + dashboard format

Layer 2: CoCo MCP Server             ← Zero context cost
         22 tools on Platform backend (localhost:8000)
         All heavy logic lives here

Layer 3: Claude Code Hook             ← Auto-activation
         SessionStart → coco_activate
         No manual /coco needed
```

---

## Day 1-2: CoCo MCP Server (Layer 2)

### New files:
- `backend/app/mcp/__init__.py`
- `backend/app/mcp/server.py` — FastMCP entry point
- `backend/app/mcp/tools/__init__.py`
- `backend/app/mcp/tools/activate.py` — coco_activate
- `backend/app/mcp/tools/decide.py` — coco_decide
- `backend/app/mcp/tools/brain.py` — teach, forget, people
- `backend/app/mcp/tools/yolo.py` — yolo_activate, yolo_classify, mode
- `backend/app/mcp/tools/todos.py` — todo_list, todo_add, todo_done
- `backend/app/mcp/tools/system.py` — health, cost, process, verify
- `backend/app/mcp/tools/session.py` — session_log, briefing, status, search, context

### 22 MCP Tools:

| Tool | Wraps | Day |
|------|-------|-----|
| `coco_activate` | /api/home + brain + sessions | 1 |
| `coco_decide` | queue.json + brain rules | 1 |
| `coco_search` | /api/search | 1 |
| `coco_status` | /api/home (compact) | 1 |
| `coco_health` | /api/health + KH health | 1 |
| `coco_cost` | /api/costs/summary | 1 |
| `coco_process` | KH ingest + process | 1 |
| `coco_session_log` | ~/.coco/sessions/*.json | 1 |
| `coco_briefing` | /api/home/briefing | 2 |
| `coco_context` | KH get_project_context | 2 |
| `coco_teach` | PATCH /api/brain | 2 |
| `coco_forget` | DELETE /api/brain/people | 2 |
| `coco_people` | GET /api/brain/people | 2 |
| `coco_yolo_activate` | config.json YOLO state | 2 |
| `coco_yolo_classify` | Action classifier logic | 2 |
| `coco_approve` | POST /api/drafts/{id}/approve | 2 |
| `coco_reject` | POST /api/drafts/{id}/reject | 2 |
| `coco_todo_list` | GET /api/todos | 2 |
| `coco_todo_add` | POST /api/todos | 2 |
| `coco_todo_done` | PATCH /api/todos/{id}/transition | 2 |
| `coco_verify` | Verification gate runner | 2 |
| `coco_mode` | config.json autonomy state | 2 |

### Registration:
```json
// ~/.claude/mcp.json
{
  "mcpServers": {
    "coco-platform": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/Rijul_Kalra/projects/coco-platform/backend", "python", "-m", "app.mcp.server"]
    }
  }
}
```

### Dependencies:
- Add `mcp>=1.26.0` to `pyproject.toml`

---

## Day 3: Slim SKILL.md (Layer 1)

### Rewrite `~/.claude/skills/coco/SKILL.md`:
- **42K tokens → ~3K tokens (93% reduction)**
- Keep: Identity, personality, mode indicator, routing table, dashboard format, fallthrough rules
- Move to MCP: All command logic, YOLO engine, verification gates, output formats, session management, teach/forget, people, orchestration chains

### Routing table format (in slim skill):
```
| Command | MCP Tool |
|---------|----------|
| /coco | mcp__coco-platform__coco_activate |
| /coco decide | mcp__coco-platform__coco_decide |
| /coco search <q> | mcp__coco-platform__coco_search |
| ... (22 entries) |
| Natural language | Route to closest MCP tool |
| Non-CoCo | Respond as Claude |
```

### Backup:
- Save current SKILL.md as `SKILL.md.v1-monolithic.bak`

---

## Day 4: Platform Orchestration (Workstream 2)

### Brain context injection:
- Modify `collaboration_context.py`: add `build_coco_context(node_id)`
- Reads brain.json people + rules relevant to the agent's project
- Injected into every spawned agent's system prompt

### YOLO permissions injection:
- Modify `collaboration_context.py`: add `build_yolo_constraints(project_id)`
- If YOLO active, inject permission matrix into agent prompt
- Modify `process_manager.py`: accept `yolo_mode` parameter

---

## Day 5: Verification Gate Service

### New file: `backend/app/services/verification.py`
- `run_gate(gate_name, input_data, output_data, node_id) -> GateResult`
- Spawns 2-3 verifier agents in parallel
- Gates: G1 (Ideation), G2 (Plan), G3 (Implementation), G4 (Acceptance)
- Reusable across: self-improve, manual workflows, /coco build

### Wire into:
- `collaboration_context.py` — workflow step advancement
- `self_improve.py` — between improvement stages
- `collaboration.py` — new `POST /api/workflows/{id}/verify` endpoint

---

## Day 6: Auto-Activation + Integration

### Auto-activation hook (Layer 3):
- New file: `~/.coco/hooks/auto-activate.js`
- SessionStart hook that triggers `coco_activate` MCP tool
- Graceful fallback if Platform not running
- Modify `~/.claude/settings.json` to register hook

### Queue sync:
- `brain.py`: add queue CRUD endpoints
- Self-improve items → queue.json on approval needed
- Agent action items → queue.json

### Events bridge:
- `event_bus.py`: append agent events to `~/.coco/events.jsonl`
- CLI sessions see Platform agent activity

### Integration testing:
- Test: MCP tools from Claude Code
- Test: auto-activation with Platform up/down
- Test: brain context in spawned agents
- Test: verification gates on a workflow

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| MCP server startup latency | Medium | Low | Pre-warm with `uv sync` during install |
| Dashboard format quality drops | Low | Medium | Keep format template in slim skill, not MCP |
| YOLO state persistence across sessions | Low | Low | Add auto-expire timestamps |
| Two MCP servers competing (KH + CoCo) | Low | Low | Claude Code handles multiple natively |
| Auto-activate hook fails silently | Medium | Low | Graceful fallback text output |

---

## Success Criteria

1. `/coco` activation uses <3K tokens (was 42K)
2. All 22 MCP tools callable from Claude Code
3. CoCo activates automatically on every session start
4. Spawned agents include brain.json context in their prompts
5. Verification gates run between self-improve steps
6. Decision queue synced between CLI and Platform

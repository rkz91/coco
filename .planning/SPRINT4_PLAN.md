# Sprint 4 Plan: "The Big Three"

**Date:** 2026-03-28
**Duration:** 10 days (3 parallel streams)
**Prerequisites:** Sprint 3 complete

---

## Stream A: Unify Chat Story (Days 1-2) — Frontend Only

**Day 1: JarvisOverlay Component**
- Create `frontend/src/components/home/JarvisOverlay.tsx` — extracts JarvisPage cinematic UI into a fixed overlay (z-60)
- Reuses ALL existing Jarvis components unchanged (BriefingSequence, ReactiveCanvas, HealthRing, JarvisInput, GlassCard)
- Reuses hooks: useJarvisAudio, useCanvas

**Day 2: Wire into HomePage + Cleanup**
- Modify `HomePage.tsx`: add jarvisMode state, "Activate Jarvis" button, accept ?jarvis=true query param
- Modify `JarvisPage.tsx`: replace with `<Navigate to="/?jarvis=true" replace />`
- Modify `App.tsx`: /jarvis route becomes redirect
- Modify `Sidebar.tsx`: Jarvis nav → onClick activates overlay
- Remove /jarvis hide guards from CocoOrb.tsx and FloatingMic.tsx
- Add "activate jarvis" voice command to useVoiceCommands.ts

**No backend changes.**

---

## Stream B: Claude Agent SDK Migration (Days 1-10)

**Day 1: SDK Wrapper**
- Add `anthropic>=0.50.0`, `claude-agent-sdk>=1.0.0` to pyproject.toml
- Create `backend/app/services/agent_sdk_client.py` — AgentSDKClient class (spawn, stream_chat, quick_command)
- Create `backend/app/services/agent_events.py` — typed event normalization
- Add `USE_AGENT_SDK` feature flag to config.py

**Day 2: Migrate Jarvis Fallback (lowest risk)**
- Modify `jarvis.py` _claude_fallback(): if USE_AGENT_SDK, use AgentSDKClient.quick_command()

**Days 3-4: Migrate Chat Streaming**
- Modify `chat.py` chat_event_generator(): if USE_AGENT_SDK, use AgentSDKClient.stream_chat()
- Replace word-count token estimate with real usage.input_tokens + usage.output_tokens
- Write real costs to cost_ledger
- Day 4: Test SSE streaming parity

**Days 5-6: Migrate ProcessManager**
- Modify `process_manager.py` spawn(): if USE_AGENT_SDK, delegate to AgentSDKClient.spawn()
- Day 5: Run SDK in asyncio event loop within thread (Option A)
- Day 6: Migrate to fully async asyncio.create_task (Option B)

**Day 7: Cost Tracking**
- Wire real token counts from SDK into cost_ledger with per-agent attribution

**Days 8-9: Testing + Parallel Run**
- Run both code paths, compare token counts, output, streaming behavior

**Day 10: Cleanup + Docs**
- Set USE_AGENT_SDK=true as default if stable
- Keep subprocess path for rollback

---

## Stream C: Knowledge Moat (Days 1-5)

**Day 1: Auto-Classifier Service**
- Create `backend/app/services/auto_classifier.py` — classify_single(), classify_batch()
- Confidence >=0.85 → auto-classify, <0.85 → suggest

**Day 2: Haiku Integration**
- Wire Anthropic API calls with structured JSON output
- Few-shot examples, batch processing every 5 min

**Day 3: Frontend Suggestions**
- Add `GET /api/content/suggestions`, `POST /api/content/{id}/accept-suggestion`
- Add "Suggestions" tab to InboxPage with accept/reject buttons

**Day 4: Agent Context Injection**
- Add `build_knowledge_context(node_id, project_id, token_budget=2000)` to collaboration_context.py
- Inject into agent prompts on spawn and chat system prompt

**Day 5: Content-to-Action (Regex Pass)**
- Enhance action extraction regex patterns
- Create platform-native todos from extracted items

---

## New Files

| File | Stream |
|------|--------|
| `frontend/src/components/home/JarvisOverlay.tsx` | A |
| `backend/app/services/agent_sdk_client.py` | B |
| `backend/app/services/agent_events.py` | B |
| `backend/app/services/auto_classifier.py` | C |

## Schema Changes

- `content_classifications`: add `confidence REAL`, `reasoning TEXT`, `suggested_project_id TEXT`

## Day-by-Day Schedule

| Day | Stream A | Stream B | Stream C |
|-----|----------|----------|----------|
| 1 | JarvisOverlay component | SDK wrapper + deps | Auto-classifier service |
| 2 | Wire into HomePage, cleanup | Migrate jarvis fallback | Haiku integration |
| 3 | (done) | Migrate chat.py streaming | Suggestions tab (frontend) |
| 4 | | Chat streaming testing | Agent context injection |
| 5 | | ProcessManager migration start | Content-to-action regex |
| 6 | | ProcessManager async reader | (done) |
| 7 | | Cost tracking (real tokens) | |
| 8 | | Testing + parallel run | |
| 9 | | Parallel run validation | |
| 10 | | Cleanup + docs | |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SDK API instability | Medium | High | Pin version, thin wrapper, keep subprocess fallback |
| SDK streaming differs from stream-json | Medium | Medium | Test parity Day 4, keep both paths |
| Haiku classification quality | Medium | Medium | Few-shot examples, 0.85 threshold |
| Threading vs async in ProcessManager | Medium | High | Start with asyncio-in-thread, migrate fully async |

## Success Criteria

1. Jarvis merged into Home — /jarvis redirects, overlay works with audio
2. Agent SDK behind feature flag — chat and agents work with SDK
3. Real token counts in cost_ledger
4. Auto-classifier routes >85% confidence items correctly
5. Spawned agents include project knowledge in context

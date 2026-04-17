# Session Handoff — 2026-04-16

> Stop point for the day. Resume from this file. Everything you need is here.
> Companion docs: `STABILITY-PLAN.md`, `CRON-ECOSYSTEM-MAP.html`.

---

## 0. TL;DR — what to do tomorrow

1. **Verify no overnight jetsam:** `find /Library/Logs/DiagnosticReports -name 'JetsamEvent-*' -newermt '2026-04-16 18:00:00'` → must be empty.
2. **Restart pykeen to activate Adam-checkpoint kwargs** — Section 2.9 confirmed PID 1411 cached imports from before the edit so the kwargs never took effect. `launchctl kickstart -k gui/$UID/com.coco.pykeen-train`. Adam state reset is negligible at MRR=0.0.
3. **Verify pykeen is advancing post-restart:** `ps -p $(pgrep -f '[p]ython.*pykeen_bridge\.py') -o pid,etime,%cpu,rss` and `cat ~/.coco/knowledge/pykeen-model/grokking_state.json`.
4. **Verify pykeen checkpoint file appeared (post-restart):** `ls -la ~/.coco/knowledge/pykeen-model/pykeen_training_checkpoint.pt` should exist within ~10 min.
5. **Confirm master-cron yielded at Fri 01:00:** `tail -5 ~/.coco/knowledge/master-cron.stdout.log` should show "pykeen_bridge.py is active, yielding machine." (See Section 11.2 — guard bypassed at 18:22 while pykeen was live. Not fully understood.)
6. **Check email-watcher + think have been firing:** `ls -la ~/.coco/knowledge/.last-cron-run` mtime should NOT advance overnight (master-cron yielded), but other agents should have run.
7. **Fix stale Haiku model IDs** before re-enabling digests — Section 11.3. Two fallback paths will error silently if local MLX fails.
8. Then pick one of the **pending improvements** in Section 6 and proceed.

---

## 1. Current live state at session end (2026-04-16 18:42 EDT)

### Processes running
| PID | Process | Status |
|---|---|---|
| 1411 | `pykeen_bridge.py --full --top 50` | Daemon, ~6h elapsed, 155% CPU, 530 MB RSS, round 51 → 52 |
| 1418 | `litestream replicate` | Daemon, idle |
| 8952 | `pykeen_dashboard.py` | User-launched browser dashboard |
| 8791 | `knowledge-dashboard.py --serve` | User-launched browser dashboard |

### Launchd agents — currently loaded
| Label | State | Schedule |
|---|---|---|
| `com.coco.pykeen-train` | running (PID 1411) | KeepAlive |
| `com.coco.litestream` | running (PID 1418) | KeepAlive |
| `com.coco.pykeen-dashboard` | running (PID 8952) | (user launched) |
| `com.coco.knowledge-dashboard` | running (PID 8791) | (user launched) |
| `com.coco.master-cron` | idle, registered | next fire **Fri 2026-04-17 01:00** (will yield to pykeen) |
| `com.coco.email-watcher` | loaded, fires on interval | every 15 min |
| `com.coco.think` | loaded, fires on interval | every 30 min |
| `com.coco.mlx-vlm-server` | **running (PID 55642)** | KeepAlive — warm 26B-A4B (see Section 2.13) |

### Launchd agents — STOPPED (booted out)
- `com.coco.meeting-prep` (was every 20 min)
- `com.coco.morning-briefing` (was 06:00 daily) — **will not fire 06:00 tomorrow**
- `com.coco.weekly-report` (was Fri 16:00) — **will not fire Fri 16:00**
- `com.coco.backup` (was Sun 03:00) — **will not fire Sun 03:00**
- `com.coco.log-rotate` (was Sun 04:00) — **will not fire Sun 04:00; logs growing unrestricted**
- `com.coco.mempalace` (was KeepAlive) — vector search currently unavailable
- `com.coco.pykeen-dashboard` and `com.coco.knowledge-dashboard` are listed in launchd but were originally user-launched

To re-enable any: `launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.coco.<NAME>.plist`

---

## 2. Today's work — chronological

### 2.1 Crash diagnosis
- Examined `/Library/Logs/DiagnosticReports/JetsamEvent-2026-04-16-122843.ips`
- **Root cause: 5 concurrent Python processes × ~3.8 GB RSS = ~19 GB peak** — 5 parallel MLX model loads from cron, OOM jetsam
- Earlier theory (boot-storm CPU contention from STABILITY-PLAN v1) was secondary; primary cause was memory

### 2.2 Stopped all scheduled cron agents
Booted out 9 agents to halt the bleeding. Kept `pykeen-train` (training in progress) and `litestream` (continuous replication).

### 2.3 Committed MLX flock fix
Commit `e0d27b2`: `fix: serialize MLX subprocess spawns via shared flock on ~/.coco/knowledge/mlx.lock`
- Files committed:
  - `backend/app/services/local_llm_client.py` — added `_mlx_exclusive()` context manager (threading.Lock + fcntl.flock)
  - `scripts/generate_product_articles.py` — same pattern
- Not in the commit (outside repo): `~/.coco/knowledge/base_generator.py` — already had the same flock pattern (added today, mtime 12:17)
- All three writers use the same lockfile: `~/.coco/knowledge/mlx.lock`

### 2.4 Built ecosystem map
`CRON-ECOSYSTEM-MAP.html` at repo root — beautiful-mermaid HTML with:
- L0 macro view (6 buckets)
- L1a Wiki subsystem (writers, queue, models, readers)
- L1b Memory topology (7 stores)
- L1c CoCo Platform integration
- L2 Email pipeline
- Agent-by-agent table (14 rows including 3 wiki services)
- Model RAM/speed matrix
- Wiki security debt table (SEC-1/2/3/5/7 + DEV-1)
- Storage lock pressure table
- Improvement candidates (consolidation + risks + sequence)

### 2.5 PyKEEN Adam checkpoint
Edited `~/.coco/knowledge/pykeen_bridge.py:186-189` — added to `training_kwargs`:
```python
"checkpoint_name": "pykeen_training_checkpoint.pt",
"checkpoint_directory": str(MODEL_DIR),
"checkpoint_frequency": 5,        # minutes
"checkpoint_on_failure": True,
```
Takes effect on next `pipeline()` call (round 52). No restart needed.

### 2.6 One-time flock validation test
- Backed up `~/.coco/knowledge/run-cron.sh` to `/tmp/run-cron.sh.backup-20260416T182201`
- Patched run-cron.sh to disable pykeen-yield guard
- Kickstarted master-cron (`launchctl kickstart gui/$UID/com.coco.master-cron`)
- Monitored 19 samples × 30s
- **Result: flock holds perfectly (max 1 MLX, 0 failures)**, but **free memory dipped to 0.1 GB during MLX cold-loads**
- Aborted (`pkill -TERM -f 'run-cron.sh'`) and restored guard from backup
- No jetsam during test ✓
- pykeen PID 1411 unaffected ✓

### 2.7 Researched MLX warm-pool fix
- `mlx_vlm 0.4.4` ships a built-in FastAPI server (`mlx_vlm.server`) with OpenAI-compatible endpoints (`/v1/chat/completions`, `/v1/responses`, `/health`, `/unload`). Default port 8080. Streaming supported.
- `mlx_lm 0.31.2` also has `mlx_lm.server` (more mature).
- This is the path to eliminate cold-load yo-yo entirely.

### 2.8 Tracked cloud fallback rate
From 88,277 lines of `master-cron.stderr.log` history:
- MLX successes: **15**
- MLX timeouts: **72** (4.8× more failures than successes)
- Articles via Sonnet 4.6 (cloud fallback): **80**
- Articles via local model: **72**
- ~$1 lifetime cloud cost — small, but operationally MLX is failing >50% of the time

### 2.9 Priority 1 sanity checks (later session, ~19:09 EDT)

| Check | Status | Finding |
|---|---|---|
| Jetsam since 18:00 | ✅ | None — flock fix holding |
| pykeen PID 1411 alive | ✅ | 6h39m elapsed, 160% CPU, 530 MB RSS, **round 68** (up from 51→52 at handoff) |
| Rounds advancing | ✅ | +16 rounds in ~27 min; cadence ~11 min/round |
| Adam checkpoint file | ⚠️ | NOT appearing at `~/.coco/knowledge/pykeen-model/pykeen_training_checkpoint.pt`. **Root cause:** PID 1411 started 12:30 (before kwargs edit) — Python imports are cached; running process won't pick up `.py` edits. Handoff's "No restart needed" claim is wrong. Needs restart. |
| master-cron log | ✅ | Last entries: 18:14 clean yield, 18:22 test-mode run — no fires since |
| `.last-cron-run` stamp | ⚠️ | File missing — expected, master-cron has been yielding |
| Launchd agents | ✅ | think, email-watcher (PID 38456), master-cron, pykeen-train, litestream, both dashboards |
| MRR | — | Still 0.0 at round 68 — plateau continues |

**Open item:** restart pykeen to activate checkpoint kwargs. Adam state reset is negligible since MRR=0.0 means we're nowhere near grokking anyway.

### 2.10 Hardware correction + model re-analysis

User confirmed machine is **64 GB M4 Max at peak**, not 32 GB as the original handoff's warm-pool math assumed.

Revised baseline:
- macOS + apps: ~8-10 GB; pykeen: ~4 GB peak; mempalace: ~1.5 GB; misc: ~1 GB → ~15 GB committed before LLM
- Single warm 31B dense (17.4 GB) → ~33 GB total, **~31 GB free** — comfortable
- Dual warm 26B-A4B (15.6 GB) + 31B (17.4 GB) → ~48 GB, ~16 GB free — tight but workable

Original Section 7 Decision #2 ("try Qwen2.5-7B first") is **obsolete** on 64 GB. Gemma4-26B-A4B stays as default; 31B becomes a viable escalation model.

### 2.11 Wiki article detail overhaul (~19:30-20:10 EDT)

**Problem:** articles only ~3 paragraphs. User wants them "as detailed as possible."

**Root cause (surprisingly simple):** `article_generator.py` lines 76 and 112 explicitly instructed "aim for 200-400 words total". The model was obediently following it. Not a model-size problem — a **prompt problem**.

**Six stacked limits found and raised:**
| Location | Old | New |
|---|---|---|
| `article_generator.py:76,112` — word target in both system prompts | 200-400 | **Hard floors: 1,800 total, 250/300/350/300/200/150 per section** |
| `base_generator.py:161` `MAX_ARTICLE_WORDS` | 600 | 2500 |
| `base_generator.py:160` `MAX_EVIDENCE_CHARS` | 16K | 24K |
| `base_generator.py:522` MLX `--max-tokens` | 2000 | 5000 |
| `article_generator.py:454` SDK async `max_tokens` | 1024 | 4096 |
| `batch_regen.py:307` batch `max_tokens` | 2048 | 4096 |

**Graph neighbors integration:** `cross_project_connections` table has **12,498 rows** and was not reaching the article prompt. Added:
- `KnowledgeEngine.enrich_with_graph_neighbors()` — top N by strength, joined to `global_entities`
- Called from both engine.py article generation paths (lines 1012, 1315)
- `graph_neighbors` formatter in `base_generator.build_evidence_block`
- Added to `_categorize_evidence` default shape + aggregations (confidence + sources)

**wiki_improver Pass 2 promoted to pipeline:**
- Threshold rewritten: `sections <= 2` → `(LENGTH(body_json) < 5000 OR sections < 5)` — catches every legacy short article
- Entity types expanded: added `role`, `org_unit`, `document`
- **Bug fixed:** previous query used `a.word_count` (doesn't exist as a column) → switched to `LENGTH(a.body_json)` as proxy (~5K chars ≈ 600 words)
- Wired into `master_cron.py` as **Phase 14** — runs after global phases 7-13, `batch_size=15` per cron fire → ~60 legacy articles deepened per day → full 1,138-article refresh in **~3 weeks**

### 2.12 Prompt engineering study: 4-way model × prompt comparison

Test entity: **OneTrust** (system, 224 cross-project neighbors, 148 evidence chunks in `3pi-v2` — 101 doc_snippets, 32 email_snippets, 15 graph_neighbors).

| Run | Prompt | Words | Time | Time/word | Key specificity wins |
|---|---|---|---|---|---|
| **26B v1** | old "200-400 words" | 868 | 40.6s | 47ms | dates, 1 field name (`customField1158`) |
| **31B v1** | old | 930 | 281s (4:41) | 302ms | Graham Holton + Tobias Dietrich named, acronyms expanded (OHD, BRD, VSA) |
| **26B v2** | new (hard floors + decomposition + specificity + self-check + role framing) | **1,503** | **67.3s** | **45ms** | matches 31B v1 on stakeholders, ALSO quotes vendor GUIDs (`e21294b0-26b9-…`), finds 2nd field (`supplier_is_false_positive`), names "LPICA ITURBE BUJ Y PAREDES SC", "eos Rechtsanwaelte GmbH" — hits 4/6 section floors |
| **31B v2** | new | 1,276 | 250s | 196ms | better Open Questions (crisp technical gaps), correct `[inferred]` usage, full BRD filename quoted, "GRC system" framing — but misses all 6 section floors |

**Decisive finding:** the length plateau was a **prompt issue, not a model issue**. With the new prompt, 26B-A4B nearly doubles output (+73%) and matches 31B's specificity at 1/7th the latency.

**Counter-intuitive 31B finding:** 31B produced **LESS** than 26B with the same prompt (1276 vs 1503, −15%) and missed **every** section floor. It appears to weight the "every sentence must carry evidence-backed content" rule over the word-count floors — refusing to pad. Quality per word is higher (sharper Open Questions, correct `[inferred]` marker usage), but quality per second is worse: **26B produces 4.4× more words per second** and more total content.

**Prompt levers that worked (combined — no single one is sufficient):**
1. **Hard word floors per section** (not "aim for")
2. **Decomposition** — 4-6 sub-questions per section giving the model surface area to cover
3. **Specificity floors** — "at least 3 dates", "at least 5 technical artifacts", "at least 6 named entities"
4. **Evidence usage floor** — "reference ≥40% of provided items"
5. **Anti-brevity framing** — "a short response is a failed response"
6. **Role framing** — "senior knowledge analyst producing a definitive reference article"
7. **Reference anchor** — "think flagship Wikipedia article on enterprise software, 2000+ words"
8. **Self-check list** — silent verification before returning, expand if any section short
9. **Writing rules** — every paragraph ≥3 sentences, weave evidence types, no hedging

**Residual gap:** Current Status (172) and Open Questions (111) sections still underperform their floors (200, 150). Appears to be evidence-limited on those topics, not prompt-limited. Acceptable for now.

**FINAL VERDICT — single warm lane, Gemma4-26B-A4B only.** The earlier "dual-warm 26B + 31B" plan is obsolete. 31B's quality edge is narrow (slightly sharper Open Questions, correct `[inferred]` usage) and does not justify 3.7× latency for 15% LESS output. Reserve 31B for nothing — cold-load only, on-demand, for the rare case quality matters more than throughput.

**Output files (ephemeral — in /tmp):**
- `/tmp/onetrust-article.md` — 26B v1 (baseline)
- `/tmp/onetrust-article-31b.json` — 31B v1
- `/tmp/onetrust-v2-26b.json` — 26B v2 (**the quality bar for the new system**)
- `/tmp/onetrust-v2-31b.json` — 31B v2 (numbers in table above)

Worth copying to a persistent location for reference.

### 2.13 MLX warm-pool SHIPPED (Phase 2 of the ecosystem plan)

Previously the biggest pending structural item (Priority 2 in Section 6). Shipped this session.

**What's deployed:**
- `~/Library/LaunchAgents/com.coco.mlx-vlm-server.plist` — NEW launchd agent. Runs `python -m mlx_vlm.server --model mlx-community/gemma-4-26b-a4b-it-4bit --host 127.0.0.1 --port 8088`. `KeepAlive=true`, `RunAtLoad=false` (boot-storm safe), `Nice=5`, `ProcessType=Background`, `OMP/MKL=4`. Logs to `~/.coco/logs/mlx-vlm-server.{stdout,stderr}.log`.
- `base_generator.py` refactored — `_call_local_llm` tries warm server first via `/v1/chat/completions` (OpenAI-compatible), falls back to cold-load subprocess when server down or serving a different model. Health probe cached 60s. New helpers: `_warm_server_model()`, `_call_warm_server()`, `_strip_mlx_artifacts()` (shared post-processing). Flock preserved on the subprocess path.

**Current live state:**
- `com.coco.mlx-vlm-server` — loaded, running, **PID 55642** at write-time, 16.4 GB RSS, loaded model `mlx-community/gemma-4-26b-a4b-it-4bit`, listening on 127.0.0.1:8088
- Idle at 0% CPU between requests — Apple Silicon unified memory is happy holding 16 GB as "just bytes"

**Measured impact (warm vs cold, same OneTrust regen, new prompt):**
| | Cold 26B v2 | **Warm 26B v2** | Δ |
|---|---|---|---|
| Wall time | 67.3s | **43.0s** | **−24s (−36%)** |
| Words | 1503 | 1384 | −119 (−8%, stochastic) |
| Generation tps | — | 67.0 | — |
| Peak memory | — | 17.8 GB | — |

**Why the real wins are bigger than −36%:**
1. **Timeout elimination** — 72 MLX timeouts in history (Section 2.8) came from cold-load + inference exceeding 180s. Warm removes cold-load entirely. Expected post-warm timeout rate: ~0%.
2. **No memory yo-yo** — steady 17.8 GB instead of 0→17.8→0 cycles; the MLX jetsam pathway is effectively closed.
3. **Flock becomes unnecessary** on the warm path — server queues internally. `_mlx_exclusive()` still wraps the subprocess fallback for safety.
4. **Cloud fallback stops accumulating** — the 80 Sonnet fallback articles per history (→~$1 lifetime) should trend to zero.

**Daily throughput:** 80 articles × 43s = 57 min/day (vs cold 90 min/day); 0% timeout rate; zero cloud cost.

**What did NOT carry over from the original Priority 2 plan:**
- NO Phase 3 (idle unload). 64 GB unified memory holds 16 GB warm indefinitely; no reason to unload.
- NO dual-warm — Section 2.12 verdict stands. Only 26B-A4B in the warm server.
- Qwen2.5-7B fallback — obsolete per Section 2.10 (64 GB correction).

**Residual cleanup (not urgent):**
- Port the same warm-server client into `backend/app/services/local_llm_client.py` (platform station path) and `scripts/generate_product_articles.py` (batch gen path). They still use the subprocess + flock path; they work unchanged but don't benefit from the warm pool until refactored.
- Decide if `mlx.lock` can be removed once all 3 call sites migrate. For now: safe to keep — only fires on subprocess fallback.

---

## 3. All files modified today

### Inside the repo (committed in `e0d27b2`)
- `backend/app/services/local_llm_client.py` — added flock around MLX subprocess
- `scripts/generate_product_articles.py` — added flock around MLX subprocess

### Inside the repo (NEW, NOT committed)
- `STABILITY-PLAN.md` — v2 plan addressing all 8 BLOCKs + 5 FLAGs from earlier review
- `CRON-ECOSYSTEM-MAP.html` — beautiful-mermaid ecosystem map
- `SESSION-HANDOFF-2026-04-16.md` — this file
- (also various PLATFORM-ANALYSIS-*.pdf/.svg, .html prototypes from earlier sessions — see `git status`)

### Outside the repo — wiki detail overhaul (Section 2.11, later session)
| Path | Change |
|---|---|
| `~/.coco/knowledge/article_generator.py` | Both system prompts rewritten (HUMAN + SYSTEM) with hard floors, decomposition, specificity floors, role framing, self-check. Async SDK `max_tokens` 1024→4096. |
| `~/.coco/knowledge/base_generator.py` | `MAX_ARTICLE_WORDS` 600→2500, `MAX_EVIDENCE_CHARS` 16K→24K, MLX `--max-tokens` 2000→5000, new `graph_neighbors` formatter in `build_evidence_block`, `graph_neighbors` added to aggregations |
| `~/.coco/knowledge/engine.py` | NEW `KnowledgeEngine.enrich_with_graph_neighbors()` method; called from both article-gen paths (lines 1012, 1315); `graph_neighbors: []` added to `_categorize_evidence` default shape |
| `~/.coco/knowledge/batch_regen.py` | `max_tokens` 2048→4096 |
| `~/.coco/knowledge/wiki_improver.py` | `pass_depth()` threshold rewritten to `LENGTH(body_json) < 5000 OR sections < 5`; entity types expanded to include `role, org_unit, document`; fixed bug where query referenced non-existent `word_count` column |
| `~/.coco/knowledge/master_cron.py` | NEW **Phase 14**: runs `wiki_improver.pass_depth(batch_size=15)` after global phases 7-13 |

### Outside the repo — MLX warm-pool shipped (Section 2.13)
| Path | Change |
|---|---|
| `~/Library/LaunchAgents/com.coco.mlx-vlm-server.plist` | NEW launchd agent — runs `python -m mlx_vlm.server` on 127.0.0.1:8088, KeepAlive, RunAtLoad=false, Nice=5, Background, OMP/MKL=4. Logs to `~/.coco/logs/mlx-vlm-server.{stdout,stderr}.log` |
| `~/.coco/knowledge/base_generator.py` | Added `_MLX_SERVER_URL`, `_MLX_SERVER_HEALTH_CACHE`, `_warm_server_model()`, `_call_warm_server()`, `_strip_mlx_artifacts()`; `_call_local_llm()` now tries warm server first and falls back to the existing subprocess+flock path |

### Inside the repo (uncommitted edits, NOT today's flock work — pre-existing)
- `frontend/src/bones/home-dashboard.bones.json` — modified, unrelated
- `scripts/think.py` — added `sweep_stale_items()` function, unrelated to today's stability work

### Outside the repo (not in version control)
| Path | Change |
|---|---|
| `~/.coco/knowledge/run-cron.sh` | Full rewrite: pykeen-yield guard, atomic lock, signal trap, `--force`, stamp-before-run, clock-skew handling, bash 3.2-safe |
| `~/.coco/knowledge/master_cron.py` | Already had `PARALLEL_WORKERS = 1` (no edit needed) |
| `~/.coco/knowledge/base_generator.py` | Already had flock added (file mtime 12:17 today, by earlier work) |
| `~/.coco/knowledge/pykeen_bridge.py` | Added Adam checkpoint kwargs (lines 186-189) |
| `~/.coco/lib/pykeen_guard.sh` | NEW — shared `check_pykeen_active()` library |
| `~/Library/LaunchAgents/com.coco.master-cron.plist` | Removed RunAtLoad, Nice=10, Background, OMP=2/MKL=2 |
| `~/Library/LaunchAgents/com.coco.meeting-prep.plist` | Nice=5, Background, interval 900→1200 |
| `~/Library/LaunchAgents/com.coco.mempalace.plist` | Removed RunAtLoad, Nice=10, Background, ThrottleInterval=300, OMP=1 |
| `~/Library/LaunchAgents/com.coco.think.plist` | Removed RunAtLoad, Nice=10, Background, LowPriorityIO, interval 900→1800, OMP=1 |
| `~/Library/LaunchAgents/com.coco.email-watcher.plist` | Removed RunAtLoad, Nice=5, Background, LowPriorityIO, interval 600→900 |
| `~/Library/LaunchAgents/com.coco.pykeen-train.plist` | Merged thread env vars (OMP/MKL/VECLIB/NUMEXPR=8, PYTHONUNBUFFERED=1) |

### Backups available for rollback
- `/tmp/run-cron.sh.backup-20260416T182201` — pre-test run-cron.sh (already restored, kept for reference)
- `/Users/Rijul_Kalra/Library/LaunchAgents/.backup-2026-04-16T12-21-10/` — all 5 modified plists + scripts; contains `rollback.sh` script

To rollback Group C plist treatments + scripts: `bash /Users/Rijul_Kalra/Library/LaunchAgents/.backup-2026-04-16T12-21-10/rollback.sh`

---

## 4. Commits made today

```
e0d27b2  fix: serialize MLX subprocess spawns via shared flock on ~/.coco/knowledge/mlx.lock
```

That's the only commit. The pykeen_bridge.py Adam checkpoint, run-cron.sh rewrite, and plist edits are in `~/.coco/` which is **NOT under git version control** here. (Worth setting up a dotfiles repo for `~/.coco/` separately — see Section 6.)

---

## 5. Project memory updates

Created in `~/.claude/projects/-Users-Rijul-Kalra-projects-coco-platform/memory/`:
- `project_crash_rca.md` — Root cause = OOM from 5 parallel MLX loads (~19 GB), fixed by flock in `e0d27b2`. Indexed in `MEMORY.md`.

---

## 6. Pending items — full backlog

Ordered by recommended priority. Each has enough context to resume cold.

### Priority 1 — Validate flock & checkpoint under real load
- ✅ **Jetsam check:** no new events since 18:00 — flock fix is holding (Section 2.9)
- ❌ **Adam checkpoint kwargs NOT active on PID 1411** — Python import cache means the running process never saw the edit. **Action (in TL;DR #2): `launchctl kickstart -k gui/$UID/com.coco.pykeen-train`.** Adam state loss is negligible since MRR=0.0 means we're nowhere near grokking. (Section 2.9)
- ⏰ **master-cron yield:** next scheduled fire is Fri 01:00; log shows a clean 18:14 yield as precedent. **But Section 11.2 flags a 18:22 run that bypassed the guard** — root cause not yet identified, verify Fri 01:00 behaves correctly.

### Priority 2 — MLX warm-pool fix — ✅ SHIPPED (see Section 2.13)
**Phase 2 shipped this session.** Warm server live as `com.coco.mlx-vlm-server` (PID 55642), 16 GB Gemma4-26B-A4B held in RAM, `base_generator._call_local_llm` routes through `/v1/chat/completions` with subprocess fallback. Measured −36% wall time (67.3s → 43.0s) and eliminates the cold-load pathway that produced the 83% MLX timeout rate. Phase 1 (stats tracker) and Phase 3 (idle unload) are no longer needed — see Section 2.13 for rationale.

The original plan below is preserved for reference / context.

---

**Phase 1 — Track (1 day, low risk)**
- Build a small script that parses `~/.coco/knowledge/master-cron.stderr.log` after each run, appends row to `~/.coco/knowledge/mlx-stats.csv`: `[date, mlx_calls, mlx_successes, mlx_timeouts, cloud_fallbacks, total_articles, est_cloud_cost_usd]`
- Surface in morning-briefing (`~/.coco/knowledge/morning_briefing.py`)
- Goal: per-day numbers instead of lifetime aggregates

**Phase 2 — Warm-pool MLX server (3–5 days, medium risk)**
- New launchd daemon `com.coco.mlx-vlm-server`, running `python -m mlx_vlm.server --model mlx-community/gemma-4-26b-a4b-it-4bit --port 8088`
- Refactor `~/.coco/knowledge/base_generator.py:495-560` (`_call_local_llm`) to use `httpx.post('http://localhost:8088/v1/chat/completions', ...)` instead of `subprocess.run([..., 'mlx_vlm', 'generate', ...])`
- Same change in `backend/app/services/local_llm_client.py:195-303`
- Same change in `scripts/generate_product_articles.py:226-309`
- Remove `_mlx_exclusive()` flock from MLX path (server serializes internally)
- Keep cloud fallback for safety

**Memory trade-off (corrected after Section 2.10):** On **64 GB** M4 Max (not 32 GB), warm 26B-A4B (~15.6 GB) leaves ~31 GB free headroom with pykeen + mempalace running. Dual warm 26B+31B (~33 GB) leaves ~16 GB free — tight but workable. The "switch to Qwen2.5-7B" fallback is obsolete; stay on Gemma.

**Urgency increased by Section 2.12 timing data:** 31B cold-load + inference under pykeen contention hit 281s per article. That's **7× slower than 26B-A4B** for 73% more quality. Warm-pool is no longer optional if 31B becomes the `article-rich` escalation model.

**Phase 3 — Idle unload (optional polish)**
- Wrap server with idle-timeout: if no `/v1/chat/completions` request in 30 min, call `POST /unload` on the server to free model
- First request after idle takes the cold-load hit
- Cuts steady-state memory back down when idle

**Decision needed:** not memory-bound on 64 GB (Section 2.10). Phase 3 idle-unload is polish, not required. Per Section 2.12 final verdict, **single warm lane = Gemma4-26B-A4B only**; 31B is cold-load on-demand. The earlier "swap to Qwen2.5-7B" fallback is obsolete.

**Prerequisite work before Phase 2** (surfaced in Section 11):
- Framework for `article-*` tasks in `_LOCAL_MODEL_REGISTRY` is `mlx_vlm` — wrong for text-only Gemma usage. Switch to `mlx_lm` (or run `mlx_lm.server` instead of `mlx_vlm.server`). Estimated 2–3× speedup and less RAM for same model.
- `_call_local_llm` `timeout=180s` with `--max-tokens=5000` is under-sized at ~25 tok/s; 5000 tokens needs ~200s just for generation. Raise to 360s, or lower max-tokens. Likely cause of half the 72 MLX timeouts.

### Priority 3 — Wiki security fixes (5 findings, blocks any external exposure)
Pending in `~/.coco/knowledge/REVIEW-SECURITY-DEV.md`:

| ID | Severity | Finding | Location |
|---|---|---|---|
| SEC-1 | high | Stored XSS via article content rendering | `wiki_server.py` :355–386, :1172–1197 |
| SEC-2 | high | SQL injection via string interpolation in `q_projects()` | `wiki_server.py` :187–189 |
| SEC-3 | medium | FTS5 MATCH injection via unsanitized search queries | `wiki_server.py` :145, `knowledge_search.py` :179, :189, :448 |
| SEC-5 | high | Path traversal in `/file/` route | `wiki_server.py` :1627–1630, :293–327 |
| SEC-7 | high | Personal document content exposed without access control | `wiki_server.py` :1669 (entire `/file/` route) |
| DEV-1 | medium | 1,683-line monolith — split | `wiki_server.py` entire file |

**Blast radius:** wiki currently runs only on localhost:8888 so external exploit is bounded. But any integration into the CoCo Platform frontend (or Tailscale exposure) inherits all 5 bugs. Treat as localhost-only prototype until SEC-1/2/3/5/7 are closed.

### Priority 4 — Group C2 plist cleanup (deferred)
The 5 plists not yet treated with the Background/Nice/LowPriorityIO/RunAtLoad-removed pattern:
- `com.coco.backup`
- `com.coco.log-rotate`
- `com.coco.morning-briefing`
- `com.coco.weekly-report`
- `com.coco.litestream`

**Note:** all 5 are currently booted out, so they don't fire at boot regardless. But re-enabling any of them brings back the boot-storm risk unless they get the same treatment. Pattern is already proven on the first 5 — copy it.

### Priority 5 — Re-enable stopped agents
Decide one-by-one when to re-enable. Suggested order (lowest memory risk first):
1. `think` (already re-enabled)
2. `email-watcher` (already re-enabled)
3. `mempalace` — needed for vector search; currently NO vector search available
4. `morning-briefing` — needed for daily 06:00 summary
5. `meeting-prep` — needed for upcoming meeting briefings
6. `weekly-report` — Friday afternoon report
7. `backup` — Sunday weekly snapshot (only matters if litestream isn't enough)
8. `log-rotate` — **important to re-enable soon**: master-cron stderr is already 88,277 lines and growing

### Priority 6 — Smaller improvements (consolidation)
From `CRON-ECOSYSTEM-MAP.html` improvement section:
- **Email-watcher subprocess chain** — collapse 6–10 `subprocess.run` calls per bundle into in-process function calls. ~4–8× faster, no fork storm.
- **Unified queue store** — `think` writes `queue.json`, `email-watcher` writes `pending_todos.json` + `pending_decisions.json`. Platform has to merge. Replace with one source of truth (SQLite table or single JSON).
- **Reporting core** — share query code across `morning-briefing`, `weekly-report`, `last-cron-result.json`.
- **wiki_improver scheduling** — currently manual-only. Either wrap in plist with `StartInterval=21600` (6h) gated by idle-check + flock, or fold its 6 passes into a new `master-cron` phase 11.
- **Backup vs litestream** — litestream already does 30d incremental WAL replication. Weekly `sqlite3 .backup` is redundant unless you want a fully-independent on-disk snapshot.

### Priority 7 — Open observations to investigate
- **PyKEEN MRR stuck at 0.0** after 50 rounds (490K epochs). Either genuine pre-grokking plateau (RotatE on small KGs does this) or a hyperparameter issue. Check after round 100.
- **PyKEEN RSS spike to 4.17 GB** during the test (sample 9 of monitor) — likely from new checkpoint code allocating Adam state buffers. Watch over time, see if it stabilizes.
- **Dashboards in launchctl** — `com.coco.pykeen-dashboard` and `com.coco.knowledge-dashboard` showed up in `launchctl list` but weren't in original inventory. They were started manually and got registered. Not added to `CRON-ECOSYSTEM-MAP.html` yet.
- **Set up `~/.coco/` under git** — many critical files (run-cron.sh, base_generator.py, pykeen_bridge.py, plists) live outside the repo and aren't versioned. Today's edits would be lost in a disk failure. Recommend: dedicated dotfiles repo.

---

## 7. Open decisions needing your input

| # | Decision | Default if no input |
|---|---|---|
| 1 | MLX warm-pool: Phase 1 tracker first, or skip to Phase 2 server? | Tracker first (safer, gets baseline) |
| 2 | ~~Default article-standard model: Gemma4-26B vs Qwen2.5-7B?~~ **RESOLVED (Section 2.12):** single warm lane, Gemma4-26B-A4B. Qwen fallback obsolete on 64 GB. | — |
| 3 | Re-enable `mempalace`? Vector search currently unavailable. | Re-enable — it's a daemon, ~1.5 GB, not in MLX path |
| 4 | Re-enable `log-rotate`? Logs growing unbounded. | Re-enable Sunday after Group C2 treatment |
| 5 | Reboot timing: per STABILITY-PLAN, defer until grokking checkpoint or accept Adam reset. With Adam now checkpointing → reboot anytime if 48h clean | Keep observing through weekend |
| 6 | Pykeen-yield guard policy: master-cron yields when pykeen runs. Acceptable indefinitely, or add an "after N hours of pykeen, force a master-cron run" escape hatch? | Keep as-is — pykeen progress is more valuable than fresh articles right now |
| 7 | **NEW (Section 11.2):** pykeen-yield guard bypassed at 18:22 despite pykeen running continuously since 12:30. Harden the `pgrep` check with a lockfile written by `pykeen_bridge.py` at startup? | Yes — cheap, reliable. Add to Section 11 follow-ups. |
| 8 | **NEW (Section 11.3):** fix stale Haiku IDs in `digest_generator.py:25` (`20250514`, invalid) and `graphrag_bridge.py:102` (`20250929`, also wrong) to `claude-haiku-4-5-20251001`? | Yes — do before re-enabling Monday digests + Phase 11 graph. |
| 9 | **NEW (Section 11.4):** switch `_LOCAL_MODEL_REGISTRY` framework from `mlx_vlm` to `mlx_lm` for `article-*` tasks (text-only)? | Yes — 2–3× faster, lower RAM. Coordinate with Phase 2 warm-pool so we don't double-edit. |

---

## 8. Key paths reference card

```
# Source tree (coco-platform repo)
~/projects/coco-platform/
├── backend/app/services/local_llm_client.py    # MLX client w/ flock
├── scripts/generate_product_articles.py        # Batch article gen w/ flock
├── STABILITY-PLAN.md                           # The crash-fix plan v2
├── CRON-ECOSYSTEM-MAP.html                     # Visual map (this session)
└── SESSION-HANDOFF-2026-04-16.md               # This file

# Knowledge engine (NOT in repo — dotfiles candidate)
~/.coco/knowledge/
├── run-cron.sh                                 # Wrapper w/ pykeen-yield guard + 6h dedup + flock
├── master_cron.py                              # Main pipeline orchestrator; NEW Phase 14 (wiki_improver depth pass)
├── cron.py                                     # 15 phases (1–10, 12–15); claude binary resolver
├── engine.py                                   # NEW enrich_with_graph_neighbors(); used by article-gen paths
├── base_generator.py                           # Article gen + MLX client w/ flock + _LOCAL_MODEL_REGISTRY
├── article_generator.py                        # Entity article prompts (hard floors) + SDK async
├── batch_regen.py                              # Batch article regen (max_tokens 4096)
├── digest_generator.py                         # STALE Haiku ID (Section 11.3)
├── graphrag_bridge.py                          # Phase 11 graph build; STALE Haiku ID (Section 11.3)
├── pykeen_bridge.py                            # KG training daemon (Adam kwargs — PID 1411 needs restart)
├── wiki_server.py                              # 1,683-line monolith (5 SEC findings)
├── wiki_improver.py                            # 6-pass improver; pass_depth() now master-cron Phase 14
├── ingest_wiki_articles.py                     # OneDrive HTML → DB (manual)
├── email_watcher.py                            # 16-step pipeline (see Section 11.5)
├── email_processor.py / pii_scrub.py / email_to_brain.py   # email_watcher steps 2/3/7
├── action_router.py / urgency_scorer.py / decision_detector.py  # email_watcher A3/A4/A5
├── cross_project_detector.py / deadline_tracker.py / evidence_contradiction.py / stakeholder_pulse.py  # C1/C3/C4/C2
├── meeting_prep.py                             # v1 data-only; v2 narrative TODO = Gemma candidate
├── morning_briefing.py                         # No LLM; queries coco.db + brain DBs
├── weekly_report.py                            # No LLM; pure data compilation
├── mempalace_service.py                        # ChromaDB daemon
├── knowledge-dashboard.py / pykeen_dashboard.py  # HTTP dashboards (always-on)
├── REVIEW-SECURITY-DEV.md                      # Wiki security findings
├── pykeen-model/                               # Trained KG models + checkpoints
│   ├── grokking_state.json
│   └── pykeen_training_checkpoint.pt           # will appear ~10 min after pykeen restart
├── articles/                                   # Rendered MD (entity, project, etc.)
├── email-evidence/                             # Processed email bundles
├── knowledge.db                                # 2,345 articles
├── mlx.lock                                    # Shared flock file
└── master-cron.{stdout,stderr}.log

~/.coco/lib/
└── pykeen_guard.sh                             # NEW — shared guard library

~/.coco/projects/<slug>/
└── project_brain.db                            # Per-project SQLite

# State files
~/.coco/brain.json                              # Attention rules + people
~/.coco/queue.json                              # Triage decision queue
~/.coco/last-morning-briefing.json
~/.coco/.last-cron-run                          # Dedup stamp

# Vector memory
~/.mempalace/palace/                            # ChromaDB (mempalace_drawers)
~/.claude/media-memory/                         # ChromaDB (files/screenshots)

# Knowledge Hub (RO from CoCo)
~/.hub/hub.db

# LaunchAgents
~/Library/LaunchAgents/com.coco.*.plist

# Backups (today)
/Users/Rijul_Kalra/Library/LaunchAgents/.backup-2026-04-16T12-21-10/
/tmp/run-cron.sh.backup-20260416T182201

# Crash reports
/Library/Logs/DiagnosticReports/JetsamEvent-*.ips

# Project memory (auto-loaded by Claude Code)
~/.claude/projects/-Users-Rijul-Kalra-projects-coco-platform/memory/
├── MEMORY.md                                   # Index
├── project_crash_rca.md                        # NEW today
└── ...
```

---

## 9. Resume tomorrow — first 10 minutes

```bash
# 1. Sanity checks
cd ~/projects/coco-platform
date
find /Library/Logs/DiagnosticReports -name 'JetsamEvent-*' -newermt '2026-04-16 18:00:00'   # MUST be empty
pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1 | xargs -I{} ps -p {} -o pid,etime,%cpu,rss
cat ~/.coco/knowledge/pykeen-model/grokking_state.json
ls -la ~/.coco/knowledge/pykeen-model/pykeen_training_checkpoint.pt   # NEW file from Adam fix

# 2. Confirm cron behavior overnight
launchctl list | grep com.coco
tail -20 ~/.coco/knowledge/master-cron.stdout.log
ls -la ~/.coco/knowledge/.last-cron-run

# 3. MLX fallback rate (run after re-running master-cron once if you want delta)
LOG=~/.coco/knowledge/master-cron.stderr.log
echo "MLX done:    $(grep -c 'local_llm done' $LOG)"
echo "MLX timeout: $(grep -c 'local_llm timed out' $LOG)"
echo "via Sonnet:  $(grep -c 'model=claude-sonnet-4-6' $LOG)"

# 4. Open the map in browser
open CRON-ECOSYSTEM-MAP.html
```

Then pick from Section 6 priorities.

---

## 10. Verification — checklist

This file's claims, cross-checked at write time. Tomorrow, re-verify items marked ⏰.

- [x] Commit `e0d27b2` exists on `main` — verify with `git log --oneline -1`
- [x] `~/.coco/knowledge/run-cron.sh` contains the pykeen-yield block (NOT TEST MODE) — verified earlier at line 30
- [x] `~/.coco/knowledge/pykeen_bridge.py` lines 186-189 contain the new checkpoint kwargs — verified earlier
- [x] pykeen PID 1411 alive at session end
- [x] No new JetsamEvent files since 18:22 — verified twice during session
- [x] Backup `/tmp/run-cron.sh.backup-20260416T182201` exists
- [x] Backup `~/Library/LaunchAgents/.backup-2026-04-16T12-21-10/` exists with rollback.sh
- [x] `CRON-ECOSYSTEM-MAP.html` exists at repo root, contains L0/L1a/L1b/L1c/L2 + wiki security table
- [x] `STABILITY-PLAN.md` exists at repo root
- [x] Project memory file `project_crash_rca.md` exists
- [ ] ⏰ Adam checkpoint file `pykeen_training_checkpoint.pt` appears ~10 min after pykeen restart (TL;DR #2)
- [ ] ⏰ master-cron yielded cleanly at next 01:00 fire (Section 11.2)
- [ ] ⏰ No jetsam through next 24h
- [ ] ⏰ Warm MLX server (PID 55642) still up and serving Gemma4-26B-A4B (Section 2.13)
- [ ] ⏰ `last-cron-result.json` exists after Fri 01:00 run (Section 11.2 — missing after 18:22 SIGTERM)

---

## 11. Cron ecosystem audit — full inventory + gaps (added 2026-04-16 late-session follow-up)

This section fills the gaps between the per-agent tables earlier in the doc and what the code actually does at runtime. Cross-referenced against `~/Library/LaunchAgents/com.coco.*.plist`, `launchctl list | grep coco`, `ps aux`, and the source files in `~/.coco/knowledge/`.

### 11.1 Full agent inventory + LLM routing

14 launchd agents exist (13 original + `com.coco.mlx-vlm-server` shipped in Section 2.13). Only **one** consumes an LLM today — `master-cron`. Everything else is pure data plumbing.

| Agent | Schedule | Script | LLM model(s) | Notes |
|---|---|---|---|---|
| `com.coco.master-cron` | Plist says 01:00 + 14:00 daily (Section 11.2 notes actual fires at 12:00 + 18:22 today) | `run-cron.sh` → `master_cron.py` → `cron.py` | **Gemma4-26B-A4B** (local, default) → Sonnet 4.6 via QB Gateway → `claude -p` CLI. Digest Phase 10 **passes** Haiku but local-first still applies. Phase 11 (graph) uses GraphRAG CLI with `anthropic/claude-haiku-4-5-20250929` (bypasses `call_claude`). | Warm server (Section 2.13) now the primary path. |
| `com.coco.mlx-vlm-server` (NEW) | `KeepAlive`, `RunAtLoad=false` | `python -m mlx_vlm.server --model gemma-4-26b-a4b-it-4bit --port 8088` | Serves Gemma4-26B-A4B | 16.4 GB RSS steady, idle ~0% CPU |
| `com.coco.pykeen-train` | `KeepAlive.SuccessfulExit=false`, no cron | `pykeen_bridge.py --full --top 50` | **None** — PyTorch TransE/RotatE CPU training | PID 1411, 7+ h elapsed, MRR=0.0 at round 68. Import-cache blocks Adam kwargs — needs restart. |
| `com.coco.pykeen-dashboard` | Always on (`KeepAlive`) | `pykeen_dashboard.py` | None | HTTP dashboard |
| `com.coco.knowledge-dashboard` | Always on (`KeepAlive`) | `knowledge-dashboard.py --serve` | None | HTTP dashboard |
| `com.coco.email-watcher` | Every 900s (15 min) | `email_watcher.py` | **None** (pure regex + inverse-frequency routing) | See 11.5 for the 16-step pipeline. Export step via AppleScript. |
| `com.coco.meeting-prep` | Every 1200s (20 min) | `meeting_prep.py` | **None** (v1). `TODO(v2)`: Haiku narrative — candidate for Gemma hand-off. | Reads Calendar.app, matches attendees. |
| `com.coco.morning-briefing` | 06:00 daily | `morning_briefing.py` | None | Queries coco.db + brain DBs → `~/.coco/last-morning-briefing.json` |
| `com.coco.weekly-report` | Fri 16:00 | `weekly_report.py` | None | Pure data compilation per project |
| `com.coco.think` | Every 1800s (30 min) | `~/.coco/think.py` | None | Reads `~/.hub/hub.db` (RO), writes `queue.json` atomically |
| `com.coco.mempalace` | Always on (`KeepAlive`) | `mempalace_service.py` | None — ChromaDB `all-MiniLM-L6-v2` local embedder | Unix socket keep-warm. Currently booted out. |
| `com.coco.litestream` | Always on (`KeepAlive`) | `litestream replicate` | n/a | Continuous WAL replication |
| `com.coco.backup` | Sun 03:00 | `~/.coco/backup.sh` | n/a | Weekly snapshot |
| `com.coco.log-rotate` | Sun 04:00 | `~/.coco/scripts/rotate-logs.sh` | n/a | Log rotation. **Currently booted out** — master-cron stderr at 88K lines and growing. |

**Implication for "hot-load Gemma4-26B":** only `master-cron` actually benefits today (already wired via `base_generator.call_claude()`). No other cron calls an LLM. Options to expand utility: wire `meeting_prep.py` v2 narrative, add Gemma-powered exec summary to `weekly_report.py`, swap GraphRAG Phase 11 to the warm server via LiteLLM `api_base`.

### 11.2 Investigation: master-cron behaviour today

**Initial observation that triggered the investigation (in another window):**
- `launchctl list | grep coco` showed `com.coco.master-cron` last exit status = **143** (SIGTERM).
- `master-cron.log` showed two "Master Cron starting: 36 projects" banners today — at **12:00:40** and **18:22:07**.
- `~/.coco/knowledge/last-cron-result.json` **does not exist** (the file is only written at the end of `run_all()`).
- Pykeen PID 1411 was continuously alive from 12:30 onward per `ps aux` (etime 7h+, 154% CPU).
- The log tail shows progress through Phase 3 for both `ab1` and `3pi-v2` at 18:22, then silence — confirming the SIGTERM.

**Apparent problem:** `run-cron.sh` contains a pykeen co-tenancy guard —
```bash
if pgrep -f '[p]ython.*pykeen_bridge\.py' >/dev/null 2>&1; then
    echo "$(date): pykeen_bridge.py is active, yielding machine."
    exit 0
fi
```
If pykeen was live from 12:30 through 18:22, this guard should have short-circuited the 18:22 fire. Instead the log shows master-cron proceeded to Phase 3 before being killed.

**Resolution — it was the Section 2.6 validation test, NOT a guard failure:**
- Section 2.6 explicitly records: "Backed up `~/.coco/knowledge/run-cron.sh` to `/tmp/run-cron.sh.backup-20260416T182201`, **patched run-cron.sh to disable pykeen-yield guard**, kickstarted master-cron, monitored 19 samples × 30s, aborted (`pkill -TERM -f 'run-cron.sh'`) and restored guard from backup."
- The backup stamp `20260416T182201` (= 18:22:01) matches the 18:22:07 "Master Cron starting" entry exactly. The guard was intentionally disabled for that run.
- The SIGTERM (exit 143 = 128+15) is the deliberate `pkill -TERM` that ended the test.
- `last-cron-result.json` is absent because the test was aborted before `run_all()` completed — expected.
- Section 2.6 also confirms "No jetsam during test ✓" and "pykeen PID 1411 unaffected ✓".

**Conclusion:** the pykeen-yield guard has NOT been observed failing in production. The only fire where the guard didn't stop master-cron is the one where the tester explicitly removed it. The guard is currently restored (verify: `grep -n 'yielding machine' ~/.coco/knowledge/run-cron.sh` should show it).

**Still outstanding (genuine unknowns):**

1. **12:00 fire.** The plist defines `StartCalendarInterval` at 01:00 and 14:00 — neither matches 12:00:40. This earlier fire is not explained by Section 2.6. Hypotheses (not yet verified):
   - A manual `launchctl kickstart` earlier in the session that wasn't logged to §2
   - A prior plist revision that defined 12:00 instead of 14:00, reloaded after 12:00 fired
   - The 12:00 run also completed to Phase 3 then stalled naturally — log shows both projects reached Phase 3 at 12:03/12:08 then nothing, so it may have simply run until the 18:22 test `pkill` swept it up. Run `launchctl print gui/$UID/com.coco.master-cron | grep -A10 'calendar interval'` Friday morning to confirm current schedule.
2. **Guard robustness.** Decision #7 (hardening `pgrep` with a `pykeen.pid` file + `kill -0` liveness probe) is still worthwhile defensively — pgrep on a loaded system can race. Keep as a "nice to have" but not an emergency after today.
3. **Why 12:00 Phase-3 work didn't produce a `last-cron-result.json`.** If the 12:00 fire was real and the test `pkill -TERM -f 'run-cron.sh'` at ~18:22 caught it mid-run, that also explains the missing result file. Investigate by: `tail -200 ~/.coco/knowledge/cron.log | grep -E 'Phase|complete'` Friday — looking for a `"Master Cron complete"` between 12:00 and 18:22 would prove the 12:00 run finished cleanly.

**Action for tomorrow:** the "guard bypassed" line in TL;DR #5 can be softened to "verify guard still present — Section 11.2 resolved the 18:22 observation as the deliberate validation test." The 12:00 fire is the only remaining unknown and can be closed by a single `launchctl print` check.

### 11.2b Other anomalies from today

1. **email_watcher dead code.** `ProjectRouter.thread_cache` is read at `email_watcher.py:289` for signal 8 (thread_inheritance boost, weight 0.3), but nothing in the codebase populates it. Thread continuity is effectively a no-op until this is wired.

2. **Warm-server / pykeen memory co-residency.** Section 2.13 shows warm server at 16.4 GB RSS. Pykeen at 530 MB → 4.17 GB peak (Priority 7 observation). On 64 GB M4 Max this is fine, but combined with a cold-path fallback that spawns a 15 GB subprocess, peak could transiently hit ~36 GB during that fallback. Flock-protected so only one cold-load at a time — acceptable.

### 11.3 Stale model IDs (fix before next master-cron fire)

Commit `9693c19 fix: update stale model IDs to Claude 4.6 family` missed two files:

| File:line | Current (stale) | Correct |
|---|---|---|
| `~/.coco/knowledge/digest_generator.py:25` | `claude-haiku-4-5-20250514` — **invalid Anthropic ID** | `claude-haiku-4-5-20251001` |
| `~/.coco/knowledge/graphrag_bridge.py:102` | `anthropic/claude-haiku-4-5-20250929` — wrong date suffix | `anthropic/claude-haiku-4-5-20251001` |

Neither has fired since `9693c19` because master-cron has been yielding/sigtermed and Phase 10 digests only run Mondays. Fix before re-enabling digests or running Phase 11 (GraphRAG) standalone — otherwise the QB Gateway will 4xx and the fallback chain silently degrades.

### 11.4 Framework mismatch in `_LOCAL_MODEL_REGISTRY`

`base_generator.py:99-104` forces `framework="vlm"` for every `article-*` task:

```python
"article-stub":     ("mlx-community/gemma-4-26b-a4b-it-4bit", "vlm"),
"article-standard": ("mlx-community/gemma-4-26b-a4b-it-4bit", "vlm"),
"article-rich":     ("mlx-community/gemma-4-31b-it-4bit",     "vlm"),
```

`mlx_vlm` loads a vision tower + multimodal preprocessor even for text-only prompts. For pure article generation, `mlx_lm` is 2–3× faster and uses less RAM for the same weights. Two changes needed together:
- Registry: `"vlm"` → `"lm"` for all three `article-*` entries (the vision tower is never used; we only send text evidence blocks).
- Warm server plist (`com.coco.mlx-vlm-server`): swap `python -m mlx_vlm.server` → `python -m mlx_lm.server`. Both expose the same OpenAI-compatible API on port 8088 so the client refactor in Section 2.13 continues to work unchanged.

Also: `_call_local_llm` uses `timeout=180s` with `--max-tokens=5000`. At the warm server's measured 67 tok/s (Section 2.13), 5000 tokens needs ~75s — fine. But on cold-load fallback at ~25 tok/s, 5000 tokens needs ~200s which exceeds the 180s timeout. Raise cold-path timeout to 360s (warm path is unaffected).

### 11.5 email_watcher — actually 16 steps, not 14

Paths card was labeled "14-step pipeline." Actual `run_cycle()` in `email_watcher.py:466` has 16 discrete steps:

1. Export from Outlook (`email_export.py --resume`)
2. Process + thread + classify (`email_processor.py --process`) — hard gate
3. PII scrub Presidio (`pii_scrub.py --scrub-texts --in-place`) — hard gate
4. Enumerate new bundles (glob `EVIDENCE_DIR/*.json` minus processed set; dead-letter malformed)
5. Route via `ProjectRouter` (9-signal inverse-frequency scoring, threshold 0.6)
6. Inject per-project `CLAUDE.local.md` digest (atomic tmp+rename)
7. Register in brain DBs (`email_to_brain.py`)
   - 7b. Brain export refreshes auto-section of `CLAUDE.local.md`
   - 7c. **A2** — enqueue ≤10 stale articles into `article_generation_queue` (circuit-breaker gated)
8. SSE emit `email.new_batch` to platform (`http://localhost:3001/api/events/emit`)
9. Collect action items
10. **A3** — route actions to hub todos (`action_router`)
11. **A4** — urgency scoring + macOS notification (`urgency_scorer`)
12. **A5** — decision detection (`decision_detector`)
13. **C1** — cross-project impact alerts (`cross_project_detector`)
14. **C3** — deadline extraction + tracking (`deadline_tracker`)
    - 14b. **C4** — evidence/article contradiction detection
15. **C2** — stakeholder pulse update (`stakeholder_pulse`)
16. Prune 30-day-old pending-* JSON files, then commit `processed_bundles` to state (at-least-once semantics)

Known issues to fix later (Priority 6 improvement already listed):
- 10+ `subprocess.run` fanouts per cycle — fork storm on large batches. Today's 19:08 log showed 5000+ threads across 18 projects.
- No cycle lock — if steps 5+ exceed 900s, launchd fires a second concurrent daemon.
- `onedrive_base.rglob(f"*{slug}*")` runs **per slug per cycle** (~18 full OneDrive walks). Cache once per cycle.
- `thread_cache` (signal 8) is dead code per Section 11.2.

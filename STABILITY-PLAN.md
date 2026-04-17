# Laptop Stability Plan — pykeen-First (v2, post-review)

**Date:** 2026-04-16
**Owner:** Rijul
**Status:** Draft v2 — addresses all 8 BLOCKs + 5 FLAGs from v1 review

## Goal

Stop boot-storm crashes. pykeen (knowledge-graph grokking training) keeps its current scheduling; everything else yields via Background QoS + positive Nice.

## Correct Entity References (fixed from v1)

- **pykeen label:** `com.coco.pykeen-train` (NOT `com.coco.pykeen`)
- **pykeen plist file:** `~/Library/LaunchAgents/com.coco.pykeen-train.plist`
- **pykeen PID:** resolve dynamically, do not hardcode. Canonical command:
  ```bash
  PYKEEN_PID=$(pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1)
  ```
- pykeen's `RunAtLoad=false`; it fires at boot via `KeepAlive={SuccessfulExit=false}`. Our changes must not interfere with that.

## Hard Constraints

1. Do NOT `bootout`, `kill`, `signal`, `stop`, or `unload` `com.coco.pykeen-train`. Current PID will keep running.
2. Changes to `com.coco.pykeen-train.plist` are permitted as file-level edits only (no reload). launchd does NOT watch plist files for content changes; edits take effect on the next KeepAlive respawn (likely much later).
3. Priority boost via `Nice=-5` is NOT available for user LaunchAgents (silently clamped to 0). We make pykeen faster by making everything else slower, not by boosting pykeen.
4. `ProcessType=Interactive` is NOT applied to pykeen — raises thermal throttling risk under sustained 150%+ CPU load, potentially *worse* for grokking throughput.

## Root Cause (unchanged)

- Multiple launchd agents fire simultaneously at boot via `RunAtLoad=true` AND via `KeepAlive` logic when the process isn't present. Combined CPU spike with pykeen's boot start crashes the laptop.
- `run-cron.sh` dedup guard is broken: stamp only touched on successful completion, so crashes leave the file absent and next boot re-fires the full pipeline.
- `master_cron.py` `PARALLEL_WORKERS=2` compounds contention when it fires.

---

## Changes

### Group A — Shell fix (zero disruption)

**File:** `/Users/Rijul_Kalra/.coco/knowledge/run-cron.sh` — full replacement:

```bash
#!/opt/homebrew/bin/bash
# Wrapper for master_cron.py. Loads QB AI Gateway credentials.
# Called by com.coco.master-cron launchd plist.

set -euo pipefail

# --- Parse --force anywhere in args (used by both shell and Python) ---
FORCE_RUN=0
for arg in "$@"; do
    [ "$arg" = "--force" ] && FORCE_RUN=1
done

# --- Mutual exclusion via atomic mkdir ---
LOCK_DIR="/tmp/coco-cron.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    if [ -f "$LOCK_DIR/pid" ]; then
        LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")
        if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
            echo "$(date): Another cron running (PID $LOCK_PID), skipping."
            exit 0
        fi
    fi
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" 2>/dev/null || { echo "$(date): Failed to acquire lock"; exit 1; }
fi
echo $$ > "$LOCK_DIR/pid"

# --- pykeen co-tenancy: robust match, anchored on python interpreter ---
if pgrep -f '[p]ython.*pykeen_bridge\.py' >/dev/null 2>&1; then
    echo "$(date): pykeen_bridge.py is active, yielding machine."
    rm -rf "$LOCK_DIR"
    exit 0
fi

# --- Dedup guard with clock-skew + stale-stamp handling ---
LAST_RUN_FILE="$HOME/.coco/knowledge/.last-cron-run"
if [ "$FORCE_RUN" -eq 1 ]; then
    echo "$(date): --force supplied, bypassing 6h dedup."
elif [ -f "$LAST_RUN_FILE" ]; then
    LAST_EPOCH=$(stat -f %m "$LAST_RUN_FILE" 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    ELAPSED=$(( NOW_EPOCH - LAST_EPOCH ))
    if [ "$ELAPSED" -lt 0 ] || [ "$ELAPSED" -gt 2592000 ]; then
        # Clock skew or >30d old — treat as first run
        echo "$(date): Stamp anomaly (elapsed=${ELAPSED}s), treating as first run."
    elif [ "$ELAPSED" -lt 21600 ]; then
        echo "$(date): Cron ran $(( ELAPSED / 3600 ))h ago (<6h), skipping."
        rm -rf "$LOCK_DIR"
        exit 0
    fi
fi

# --- Touch stamp BEFORE run (prevents crash-then-bypass bug) ---
mkdir -p "$(dirname "$LAST_RUN_FILE")"
touch "$LAST_RUN_FILE"

# --- Load QB AI Gateway credentials ---
QB_KEY_FILE="$HOME/.coco/.qb-gateway-key"
if [ -f "$QB_KEY_FILE" ]; then
    QB_KEY=$(cat "$QB_KEY_FILE")
    QB_PROJECT="39867e95-6e22-4c1b-b20d-aba44c739c72"
    export ANTHROPIC_API_KEY="$QB_KEY"
    export ANTHROPIC_BASE_URL="https://anthropic.prod.ai-gateway.quantumblack.com/${QB_PROJECT}"
fi

# --- Run Python as background child with proper signal forwarding ---
# Do NOT use `exec` — bash fires EXIT trap BEFORE exec, destroying the lock.
PY=/opt/homebrew/opt/python@3.14/bin/python3.14

CHILD=""
cleanup() {
    if [ -n "$CHILD" ]; then
        kill -TERM "$CHILD" 2>/dev/null || true
        wait "$CHILD" 2>/dev/null || true
    fi
    rm -rf "$LOCK_DIR"
}
trap cleanup EXIT INT TERM

# Empty-array-safe under set -u (macOS bash 3.2+)
"$PY" "$HOME/.coco/knowledge/master_cron.py" "${@+"$@"}" &
CHILD=$!
wait "$CHILD"
EXIT_CODE=$?
CHILD=""  # prevent trap from killing already-exited child
exit "$EXIT_CODE"
```

**Shebang change:** `/bin/bash` (3.2) → `/opt/homebrew/bin/bash` (5.x) for reliable `set -u` + empty-array handling. Fallback if homebrew bash is missing: keep `/bin/bash` and use `"${@+"$@"}"` pattern which works in 3.2 too (tested).

**Key fixes vs v1 draft:**
- `trap` is set via `cleanup()` function and cleared in happy path via `CHILD=""` so it doesn't kill the already-exited child. Lock cleanup still runs on abnormal exit.
- No `exec`. `wait "$CHILD"` + trap forwards SIGTERM cleanly.
- `--force` is NOT stripped from args — forwarded to Python (`master_cron.py:461` accepts it).
- `pgrep -f '[p]ython.*pykeen_bridge\.py'` anchors on python-interpreter invocation; avoids self-match, editor greps, log tails.
- Clock-skew branch catches negative `ELAPSED` (NTP rewind, DST anomalies).
- `rm -rf "$LOCK_DIR"` on all early exits (was missing on some paths in v1).

### Group B — Pipeline config (zero disruption)

**File:** `/Users/Rijul_Kalra/.coco/knowledge/master_cron.py`

```diff
-    PARALLEL_WORKERS = 2
+    # Reduced 2 → 1: on a laptop also running pykeen, 2 workers still caused
+    # SQLite lock retries. 1 fully serializes writes, leaves headroom for pykeen.
+    PARALLEL_WORKERS = 1
```

No other code assumes >= 2 workers (verified against `ThreadPoolExecutor` usage at line 244, `as_completed` at 247, `gc.collect()` at 231).

### Group C — 5 non-pykeen plists (pykeen-train explicitly excluded)

| plist | RunAtLoad | KeepAlive | ProcessType | Nice | Schedule | Notes |
|---|---|---|---|---|---|---|
| `com.coco.master-cron` | **remove** | — | Background (existing) | **+10** | cron 01:00 / 14:00 | Add `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2` |
| `com.coco.meeting-prep` | absent | — | Background (existing) | **+5** | `StartInterval` 900 → **1200** | Nice is only new key |
| `com.coco.mempalace` | **remove** (cosmetic*) | keep SuccessfulExit=false | **Background** (new) | **+10** | KeepAlive respawn only | Bump `ThrottleInterval` 60 → **300**; add `OMP_NUM_THREADS=1` |
| `com.coco.think` | **remove** | — | **Background** (new) | **+10** | `StartInterval` 900 → **1800** | Add `OMP_NUM_THREADS=1` |
| `com.coco.email-watcher` | **remove** | — | **Background** (new) | **+5** | `StartInterval` 600 → **900** | |

*\*mempalace KeepAlive fires at boot regardless of RunAtLoad. We accept the boot start (KeepAlive is needed for crash recovery) but throttle heavily: `ThrottleInterval=300` means 5-min gap between any crash-respawn, and Background QoS + Nice=10 makes the boot start cheap (E-cores, not P-cores).*

All 5 get `LowPriorityIO=true`. Reload loop (pykeen-train NEVER in this list):

```bash
for L in master-cron meeting-prep mempalace think email-watcher; do
  plutil -lint ~/Library/LaunchAgents/com.coco.$L.plist || { echo "BAD $L"; exit 1; }
  launchctl bootout  gui/$UID/com.coco.$L 2>/dev/null || true
  launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.coco.$L.plist || exit 1
  launchctl print    gui/$UID/com.coco.$L | grep -E 'state|nice|process type'
  # Verify pykeen still alive after EACH reload
  pgrep -f '[p]ython.*pykeen_bridge\.py' >/dev/null || { echo "PYKEEN DIED! ABORT"; exit 2; }
  sleep 5  # space out reloads; avoids thundering herd on KeepAlive respawns
done
```

### Group C2 — Additional plist audit (defer to follow-up)

v1 plan missed these agents on the machine: `com.coco.litestream`, `com.coco.backup`, `com.coco.morning-briefing`, `com.coco.weekly-report`, `com.coco.log-rotate`. Some likely have `RunAtLoad=true`.

**For this rollout:** leave untouched (don't expand scope). **Follow-up (Group F):** audit all for RunAtLoad, apply the same Background+Nice treatment. Adds ~30 min to total rollout; safe to defer because pykeen-train protection doesn't depend on them.

### Group D — pykeen-train plist enhancement (file edit ONLY, no reload)

**File:** `~/Library/LaunchAgents/com.coco.pykeen-train.plist`

Current state (lines 16-20):
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>HOME</key>
    <string>/Users/Rijul_Kalra</string>
</dict>
```

Patched state (merge new keys INTO existing dict — do NOT add a second `EnvironmentVariables` block):
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>HOME</key>
    <string>/Users/Rijul_Kalra</string>
    <key>OMP_NUM_THREADS</key>
    <string>8</string>
    <key>MKL_NUM_THREADS</key>
    <string>8</string>
    <key>VECLIB_MAXIMUM_THREADS</key>
    <string>8</string>
    <key>NUMEXPR_NUM_THREADS</key>
    <string>8</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
</dict>
```

**Removed from v1:**
- ~~`PYTORCH_MPS_HIGH_WATERMARK_RATIO`~~ — pykeen intentionally CPU-only (user confirmed: small model, MPS not beneficial).
- ~~`Nice=-5`~~ — silently clamped to 0 for user LaunchAgents.
- ~~`ProcessType=Interactive`~~ — triggers thermal throttling on sustained load; worse for grokking.

**Verification step (post-edit):**
```bash
plutil -lint ~/Library/LaunchAgents/com.coco.pykeen-train.plist  # must succeed
diff <(plutil -convert xml1 -o - ~/Library/LaunchAgents/.backup-*/com.coco.pykeen-train.plist) \
     <(plutil -convert xml1 -o - ~/Library/LaunchAgents/com.coco.pykeen-train.plist) \
     | grep -E "^[<>]"  # confirm only additions, no deletions
# pykeen-train current PID must still match pre-edit PID
```

### Group E — Shared guard library

**File:** `/Users/Rijul_Kalra/.coco/lib/pykeen_guard.sh` (NEW — parent dir does not exist)

```bash
#!/opt/homebrew/bin/bash
# Source in any cron script that should yield to pykeen training.

check_pykeen_active() {
    # Primary: pgrep with anchored regex (no self-match, no log-tail match)
    if /usr/bin/pgrep -f '[p]ython.*pykeen_bridge\.py' >/dev/null 2>&1; then
        return 0
    fi
    # Secondary: grokking_state.json mtime < 15 min = active training
    local state="$HOME/.coco/knowledge/pykeen-model/grokking_state.json"
    if [ -f "$state" ]; then
        local now=$(date +%s)
        local mtime=$(stat -f %m "$state" 2>/dev/null || echo "0")
        [ "$mtime" -gt 0 ] && [ $((now - mtime)) -lt 900 ] && return 0
    fi
    return 1
}
```

Rollout pre-step: `mkdir -p ~/.coco/lib/`.

### Group F — Follow-ups (out of scope for this rollout)

1. **Patch `pykeen_bridge.py`** to use PyKEEN's `checkpoint_name` + `checkpoint_frequency` in `training_kwargs` so Adam optimizer state persists across restarts. Biggest single win for grokking — every interruption currently drops ~20-50K effective epochs of progress.
2. **Audit remaining plists** (litestream, backup, morning-briefing, weekly-report, log-rotate) and apply same treatment.
3. **Delete orphan tmp:** `rm ~/.coco/knowledge/pykeen-model/tmp6cgnotaf.tmp`.
4. ~~MPS migration~~ — dropped per user (small model; CPU is the right choice).

---

## Rollout Sequence (with explicit gates)

All steps wrapped in `set -euo pipefail`. Each gate halts on failure.

```bash
#!/opt/homebrew/bin/bash
set -euo pipefail

# ─── Pre-flight ─────────────────────────────────────────────
PYKEEN_PID=$(pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1)
[ -z "$PYKEEN_PID" ] && { echo "ABORT: pykeen not running"; exit 1; }
echo "pykeen PID: $PYKEEN_PID"
ps -p "$PYKEEN_PID" -o pid,etime,%cpu,rss

TS=$(date +%Y-%m-%dT%H-%M-%S)
BK=~/Library/LaunchAgents/.backup-$TS
mkdir -p "$BK"

for L in master-cron meeting-prep mempalace think email-watcher pykeen-train; do
    cp -p ~/Library/LaunchAgents/com.coco.$L.plist "$BK/"
done
cp -p ~/.coco/knowledge/run-cron.sh "$BK/run-cron.sh.bak"
cp -p ~/.coco/knowledge/master_cron.py "$BK/master_cron.py.bak"

# Generate rollback.sh (see below) into $BK/rollback.sh, chmod +x
# ...

# ─── Gate 1: pykeen baseline CPU ────────────────────────────
BASELINE_CPU=$(ps -p "$PYKEEN_PID" -o %cpu= | tr -d ' ')
echo "pykeen baseline CPU: $BASELINE_CPU%"

# ─── Group A: shell patch ──────────────────────────────────
# Write new run-cron.sh (content above)
bash -n ~/.coco/knowledge/run-cron.sh  # syntax check
# Gate: pykeen still alive
ps -p "$PYKEEN_PID" >/dev/null || { echo "ABORT: pykeen died"; exit 2; }

# ─── Group B: master_cron.py ────────────────────────────────
# Apply PARALLEL_WORKERS=1 patch
python3 -c "import ast; ast.parse(open('$HOME/.coco/knowledge/master_cron.py').read())"
ps -p "$PYKEEN_PID" >/dev/null || { echo "ABORT"; exit 2; }

# ─── Group E: guard library ────────────────────────────────
mkdir -p ~/.coco/lib
# Write pykeen_guard.sh (content above)
bash -n ~/.coco/lib/pykeen_guard.sh
ps -p "$PYKEEN_PID" >/dev/null || { echo "ABORT"; exit 2; }

# ─── Group C: plist reloads (one at a time, pykeen-train EXCLUDED) ────
for L in master-cron meeting-prep mempalace think email-watcher; do
    plutil -lint ~/Library/LaunchAgents/com.coco.$L.plist
    launchctl bootout  gui/$UID/com.coco.$L 2>/dev/null || true
    launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.coco.$L.plist
    sleep 5
    # Per-step pykeen invariant
    ps -p "$PYKEEN_PID" >/dev/null || { echo "ABORT after $L: pykeen died"; exit 2; }
done

# ─── Gate 2: all 5 reloaded green + pykeen CPU delta OK ───────────
CURRENT_CPU=$(ps -p "$PYKEEN_PID" -o %cpu= | tr -d ' ')
DELTA=$(echo "$CURRENT_CPU - $BASELINE_CPU" | bc | tr -d '-')
[ "${DELTA%.*}" -gt 30 ] && { echo "WARN: pykeen CPU delta $DELTA%"; }

# ─── Group D: pykeen-train plist edit (FILE ONLY — no reload) ────
# Use plutil -replace (idempotent: creates-or-overwrites, safe on re-runs).
# -insert would fail on second run if the key already exists.
PKP=~/Library/LaunchAgents/com.coco.pykeen-train.plist
plutil -replace EnvironmentVariables.OMP_NUM_THREADS       -string "8" "$PKP"
plutil -replace EnvironmentVariables.MKL_NUM_THREADS       -string "8" "$PKP"
plutil -replace EnvironmentVariables.VECLIB_MAXIMUM_THREADS -string "8" "$PKP"
plutil -replace EnvironmentVariables.NUMEXPR_NUM_THREADS   -string "8" "$PKP"
plutil -replace EnvironmentVariables.PYTHONUNBUFFERED      -string "1" "$PKP"
plutil -lint "$PKP"

# Final gate: pykeen STILL on original PID (we did not reload)
NEW_PID=$(pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1)
[ "$NEW_PID" = "$PYKEEN_PID" ] || { echo "ABORT: pykeen PID changed $PYKEEN_PID → $NEW_PID"; exit 3; }
echo "DONE. pykeen-train new env vars take effect on next KeepAlive respawn."
```

## Rollback — `$BK/rollback.sh`

```bash
#!/opt/homebrew/bin/bash
set -uo pipefail  # NOT -e — we want to attempt all restores even on partial failure
BK="$(cd "$(dirname "$0")" && pwd)"

# pykeen health is a WARNING, not an abort (rollback may be triggered precisely
# because pykeen died — must still be able to run).
PYKEEN_PID=$(pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1 || true)
FORCE_DEAD=0
for arg in "$@"; do [ "$arg" = "--force-dead" ] && FORCE_DEAD=1; done
if [ -z "$PYKEEN_PID" ]; then
    if [ "$FORCE_DEAD" -eq 1 ]; then
        echo "WARN: pykeen not running, proceeding with --force-dead."
    else
        echo "pykeen not running. Re-run with --force-dead to proceed anyway."
        exit 1
    fi
fi

# Restore 5 non-pykeen plists
FAIL=0
for L in master-cron meeting-prep mempalace think email-watcher; do
    if ! cp -p "$BK/com.coco.$L.plist" ~/Library/LaunchAgents/; then FAIL=1; continue; fi
    launchctl bootout  gui/$UID/com.coco.$L 2>/dev/null || true
    launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.coco.$L.plist || FAIL=1
done

# Restore pykeen-train plist (reverses Group D edits). Do NOT reload.
cp -p "$BK/com.coco.pykeen-train.plist" ~/Library/LaunchAgents/ || FAIL=1

# Restore scripts
cp -p "$BK/run-cron.sh.bak" ~/.coco/knowledge/run-cron.sh || FAIL=1
cp -p "$BK/master_cron.py.bak" ~/.coco/knowledge/master_cron.py || FAIL=1

# Remove Group E file (optional; harmless if left)
rm -f ~/.coco/lib/pykeen_guard.sh

# Verify pykeen (warn only)
CURRENT_PID=$(pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1 || true)
if [ -n "$CURRENT_PID" ]; then
    echo "OK: pykeen running (PID $CURRENT_PID)"
else
    echo "WARN: pykeen not running after rollback."
fi

exit $FAIL
```

## Test Plan

Every test now includes a pykeen CPU invariant.

```bash
# Helpers
pykeen_pid() { pgrep -f '[p]ython.*pykeen_bridge\.py' | head -1; }

# 3-sample median over ~3s, robust against grokking CPU oscillation (150-210%)
pykeen_cpu_median() {
    local pid=$(pykeen_pid)
    [ -z "$pid" ] && { echo "0"; return; }
    local s1=$(ps -p "$pid" -o %cpu= | tr -d ' ')
    sleep 1
    local s2=$(ps -p "$pid" -o %cpu= | tr -d ' ')
    sleep 1
    local s3=$(ps -p "$pid" -o %cpu= | tr -d ' ')
    printf "%s\n%s\n%s\n" "$s1" "$s2" "$s3" | sort -n | sed -n '2p'
}

# pykeen is healthy iff: still alive AND still training (CPU not collapsed)
# Use alive-check + "still using CPU" threshold; avoid brittle delta math.
assert_pykeen_ok() {
    local pre_pid=$1
    local cur_pid=$(pykeen_pid)
    [ "$cur_pid" = "$pre_pid" ] || { echo "FAIL: pykeen PID changed $pre_pid → $cur_pid"; exit 1; }
    local cpu=$(pykeen_cpu_median)
    # Training workload is sustained >100% CPU; <50% median over 3s = problem.
    awk -v c="$cpu" 'BEGIN { exit (c+0 >= 50 ? 0 : 1) }' \
        || { echo "FAIL: pykeen CPU collapsed to $cpu%"; exit 1; }
}

stamp_mtime() { stat -f %m ~/.coco/knowledge/.last-cron-run 2>/dev/null || echo "0"; }
```

1. **Fresh boot simulation, no stamp, pykeen active → yield** — pykeen is always active in our scenario, so this is a deterministic yield test:
   ```bash
   PRE_PID=$(pykeen_pid); rm -f ~/.coco/knowledge/.last-cron-run
   OUT=$(bash ~/.coco/knowledge/run-cron.sh --all)
   echo "$OUT" | grep -q "yielding machine" || { echo "FAIL: did not yield"; exit 1; }
   [ ! -f ~/.coco/knowledge/.last-cron-run ] || { echo "FAIL: stamp created on yield"; exit 1; }
   assert_pykeen_ok "$PRE_PID"
   ```
2. **pykeen active → yield preserves stamp** —
   ```bash
   touch ~/.coco/knowledge/.last-cron-run
   MTIME_BEFORE=$(stamp_mtime); PRE_PID=$(pykeen_pid)
   bash ~/.coco/knowledge/run-cron.sh --all
   MTIME_AFTER=$(stamp_mtime)
   [ "$MTIME_BEFORE" = "$MTIME_AFTER" ] || { echo "FAIL: stamp changed on yield"; exit 1; }
   assert_pykeen_ok "$PRE_PID"
   ```
3. **Scheduled fire while pykeen active** — pre-age the stamp to 12h old; pykeen still active; script must yield without touching stamp:
   ```bash
   touch -t $(date -v-12H +%Y%m%d%H%M) ~/.coco/knowledge/.last-cron-run
   MTIME_BEFORE=$(stamp_mtime); PRE_PID=$(pykeen_pid)
   bash ~/.coco/knowledge/run-cron.sh --all
   [ "$MTIME_BEFORE" = "$(stamp_mtime)" ] || { echo "FAIL: stamp changed"; exit 1; }
   assert_pykeen_ok "$PRE_PID"
   ```
4. **Dedup window + `--force`** — requires pykeen-gone (run only after current grokking checkpoint). Skipped if pykeen is active. Assert both dedup-skip and `--force` bypass behaviors via log-string match.
5. **Stale-stamp branch** — requires pykeen-gone. `touch -t 202601010000 ~/.coco/knowledge/.last-cron-run && bash run-cron.sh --all` → stdout contains "Stamp anomaly, treating as first run".
6. **Concurrent invocation** — requires pykeen-gone. `(bash run-cron.sh --all &) ; sleep 1 ; bash run-cron.sh --all` → second exit stdout contains "Another cron running".
7. **Boot-storm simulation** (run LAST, after all above pass):
   ```bash
   PRE_PID=$(pykeen_pid)
   for L in master-cron meeting-prep mempalace think email-watcher; do
       launchctl kickstart gui/$UID/com.coco.$L   # no -k; avoids KeepAlive cascade
       sleep 3
   done
   sleep 30
   assert_pykeen_ok "$PRE_PID"
   top -l 1 -n 20 -o cpu | head -25  # visual: aggregate non-pykeen CPU < 60%
   ```
8. **Rollback dry-run** — back up current state to a scratch dir, run `$BK/rollback.sh --force-dead`, `diff -r` against originals, verify restoration.

## Monitoring (24-48h)

Observation commands:
- `top -l 0 -s 30 -o cpu -n 15 | grep -E 'coco|pykeen'` — pykeen etime grows, others idle at Nice 5-10 on E-cores.
- `du -sh /tmp/coco-*.log /tmp/pykeen-grok.log` every 6h.
- `ls -la ~/.coco/knowledge/.last-cron-run` — mtime updates at 01:00/14:00, not on login.

**"Clean telemetry" pass criteria** (all must hold for 48h):
- No non-pykeen `com.coco.*` process sustained >0% CPU over any 30-second sample at foreground QoS.
- `pykeen-grok.log` mtime advances at least once per 5-minute window (training alive).
- Zero kernel panics: `log show --predicate 'eventMessage CONTAINS "panic"' --last 48h` returns empty.
- Zero stability-related respawns: `log show --predicate 'subsystem == "com.apple.launchd"' --last 48h | grep com.coco | grep -i "exit\|crash"` returns only clean KeepAlive events, no abnormal exits.

## Reboot Timing (CORRECTED)

- **v1 said:** "Reboot once mid-week to confirm boot storm gone" — premature.
- **v2 policy:** Reboot ONLY after BOTH gates pass:
  - **Gate A — Clean telemetry (automated):** 48h observation window meets all 4 pass criteria above.
  - **Gate B — User-confirmed grokking checkpoint (manual judgment):** user decides the current grokking run has reached an acceptable stopping point, OR explicitly accepts the restart cost of losing Adam optimizer state. This gate is non-automatable and is the user's call.

## Unresolved / Deferred (user decision)

- `meeting-prep` DEFER vs SKIP when pykeen active: current plan is SKIP (simpler, idempotent). Flip only if user reports missed meeting prep.
- Group C2 (audit remaining 5 plists) — defer unless boot storm still observed after Group C takes effect.
- Group F items — schedule separately.

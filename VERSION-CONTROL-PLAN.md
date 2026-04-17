# Version Control Plan — Bring Everything Under Git

**Created:** 2026-04-16
**Trigger:** today's session edited 9 critical Python files in `~/.coco/knowledge/` and 1 launchd plist in `~/Library/LaunchAgents/`. None of those are under version control. A disk failure between now and "tomorrow" loses today's wiki-detail overhaul, warm-pool integration, prompt rewrite, graph-neighbors integration, Phase 14 wiring, and Haiku ID fixes.

---

## 1. Current state — what's where

| Bucket | Location | Versioned? | Today's edits? |
|---|---|---|---|
| **Knowledge engine code** | `~/.coco/knowledge/*.py`, `*.sh` | ❌ No | ✅ 9 files, ~hundreds of lines |
| **Launchd agents** | `~/Library/LaunchAgents/com.coco.*.plist` | ❌ No | ✅ 1 NEW plist (`com.coco.mlx-vlm-server.plist`) plus 6 from earlier today (Group C treatments) |
| **Shared lib** | `~/.coco/lib/pykeen_guard.sh` | ❌ No | Pre-existing (today's earlier session) |
| **Knowledge DB** | `~/.coco/knowledge/knowledge.db` | ❌ No (litestream replicating WAL) | Read/write daily — generated content |
| **Brain DB** | `~/.coco/projects/<slug>/project_brain.db` | ❌ No | Per-project, sensitive |
| **Config** | `~/.coco/config.json`, `brain.json`, `queue.json` | ❌ No | State files, may contain person names |
| **Logs** | `~/.coco/logs/*`, `~/.coco/knowledge/*.log` | ❌ No | Disposable |
| **Platform code** | `~/projects/coco-platform/{backend,frontend,scripts}/` | ✅ Yes (git) | Today's warm-pool client ports — committed as `5736680` |
| **Planning docs** | `~/projects/coco-platform/*.md`, `*.html` | ✅ Yes | Today's STABILITY-PLAN, ECOSYSTEM-MAP, HANDOFF — committed as `e963af9` and `fd13de8` |

### What's actually at risk if disk dies tomorrow morning

- **9 Python files in `~/.coco/knowledge/`** — today's heavy edits. `article_generator.py` (prompt rewrite), `base_generator.py` (warm-pool client + MAX limits), `engine.py` (graph neighbors), `wiki_improver.py` (Phase 14 trigger), `master_cron.py` (Phase 14 wiring), `digest_generator.py` (Haiku fix), `graphrag_bridge.py` (Haiku fix), `batch_regen.py` (max_tokens), and the new `regen_one.py`.
- **1 launchd plist** — `com.coco.mlx-vlm-server.plist` (and the 5-6 Group C plists modified earlier today).
- **The shared lib** — `~/.coco/lib/pykeen_guard.sh`.

That's roughly 1,500-2,000 lines of code from today alone, not recoverable from any cloud sync.

---

## 2. Phase 0 — Immediate safety net (2 minutes, do tonight)

Take a tarball snapshot of everything code-shaped in `~/.coco/` and stash it where Time Machine + iCloud already protect things. Pure safety net — buys time to do the rest properly.

**Use the whitelist version below — NOT a blacklist.** Initial draft of this plan used `tar --exclude=...` patterns and produced a broken 304 MB tarball because `~/.coco/` contains 1.5 GB of venvs (`graphrag-env/`, `mempalace-env/`, `graphify-env/`), 737 MB of backups, 109 MB of voice memos, etc. that the exclude patterns missed. Whitelist via `find` is the only safe approach.

```bash
SNAP="$HOME/Library/Mobile Documents/com~apple~CloudDocs/coco-snapshots/coco-code-$(date +%Y%m%d-%H%M).tar.gz"
mkdir -p "$(dirname "$SNAP")"

# Build a whitelist of code-only files via find, then tar from the manifest.
MANIFEST=$(mktemp)
{
    find ~/.coco -maxdepth 3 \
        \( -name '*.py' -o -name '*.sh' -o -name '*.md' \) \
        -not -path '*/graphrag-env/*' \
        -not -path '*/mempalace-env/*' \
        -not -path '*/graphify-env/*' \
        -not -path '*/node_modules/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/backups/*' \
        -not -path '*/articles/*' \
        -not -path '*/email-evidence/*' \
        -not -path '*/product_evidence/*' \
        -not -path '*/pykeen-model/*' \
        -not -path '*/voices/*' \
        -not -path '*/podcasts/*' \
        -not -path '*/session-summaries/*' \
        -not -path '*/sessions/*' \
        -not -path '*/calendar-blocker/*' \
        -not -path '*/logs/*' \
        -not -path '*/.git/*'
    find ~/Library/LaunchAgents -maxdepth 1 -name 'com.coco.*.plist'
} | sort -u > "$MANIFEST"

tar -czf "$SNAP" -T "$MANIFEST"
rm -f "$MANIFEST"
ls -lh "$SNAP"
```

This goes to iCloud Drive and rides Time Machine. **Validated 2026-04-16: produces ~650 KB tarball with 145 files** (all 9 today's-edits + new launchd plist confirmed present). Repeat at end of any session that edits these files until Phase 2 lands.

**One-shot copy-paste for end-of-session habit:** save as `~/.coco/snapshot.sh` and run after each session.

---

## 3. Phase 1 — Clean the coco-platform repo (15 minutes, today/tomorrow)

The platform repo currently has ~70 untracked files (PLATFORM-ANALYSIS PDFs, prototype HTMLs, Screenshots-clone/, frontend/pw-*.cjs Playwright scratch files, USER-JOURNEY-*.html). These shouldn't be committed — they're working artifacts. They should be `.gitignore`d so `git status` becomes useful again.

Add to `.gitignore`:

```gitignore
# Generated analysis artifacts (regenerated on demand)
PLATFORM-ANALYSIS-*.pdf
PLATFORM-ANALYSIS-*.svg
PLATFORM-ANALYSIS-rendered*
PLATFORM-ANALYSIS.html
PLATFORM-ANALYSIS.md
FEATURE-INVENTORY.html
KNOWLEDGE-QUALITY-REPORT.html
USER-JOURNEY-*.html
lovable-clone.html

# Screenshot working dirs
Screenshots-clone/
backend/Screenshots-clone/

# Playwright scratch scripts (one-off, never reused)
frontend/pw-*.cjs

# Prototype iterations (live in a separate working area)
prototypes/path-*.html
prototypes/PATH-*.html
prototypes/comparison.html
prototypes/QA-REPORT.md
```

Then triage the two pre-existing dirty files (Bucket B from the parallel-window analysis):
- `frontend/src/bones/home-dashboard.bones.json` (+788/−658) — looks like a full regeneration. Confirm whether it's intentional, then commit standalone.
- `scripts/think.py` (+43/−23, `sweep_stale_items()`) — feature work from a prior session. Commit with its own message.

Both of these should land in their own commits, not bundled with today's stability work.

---

## 4. Phase 2 — Set up the dotfiles repo (30-60 minutes, this week)

**Recommended structure:** dedicated private repo `~/projects/coco-dotfiles/` with selective symlinks managed by an idempotent install script.

### 4.1 Why this shape (vs alternatives)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Fold into coco-platform** | One repo, existing CI | Tightly couples knowledge engine to platform; runtime expects `~/.coco/knowledge/` paths | ❌ wrong coupling |
| **B. `git init ~/.coco/`** | Zero symlinks, in-place | `~/.coco/` is full of state (DBs, logs, generated content) — `.gitignore` becomes a battle | ⚠️ fragile |
| **C. Dedicated dotfiles repo + symlinks** | Clean separation; only code in repo; data stays put; standard pattern | Requires install.sh; symlinks must be maintained | ✅ recommended |
| **D. Move to `~/projects/coco-knowledge/` + env var** | Cleanest | Requires changing all path lookups in code | Future cleanup, not now |

### 4.2 Repo layout

```
~/projects/coco-dotfiles/    ← new private repo
├── README.md                ← this file's "how to install"
├── install.sh               ← idempotent symlink creator
├── verify.sh                ← check symlinks point to the right place
├── .gitignore               ← belt-and-braces secret protection
├── coco/
│   ├── knowledge/           ← all the .py files we edit
│   │   ├── article_generator.py
│   │   ├── base_generator.py
│   │   ├── batch_regen.py
│   │   ├── digest_generator.py
│   │   ├── engine.py
│   │   ├── graphrag_bridge.py
│   │   ├── master_cron.py
│   │   ├── pykeen_bridge.py
│   │   ├── regen_one.py
│   │   ├── run-cron.sh
│   │   ├── wiki_improver.py
│   │   ├── meeting_prep.py
│   │   ├── morning_briefing.py
│   │   ├── weekly_report.py
│   │   ├── email_watcher.py
│   │   ├── mempalace_service.py
│   │   ├── wiki_server.py
│   │   ├── wiki_improver.py
│   │   ├── ingest_wiki_articles.py
│   │   └── ... (every .py + .sh that's editable code, NOT data)
│   └── lib/
│       └── pykeen_guard.sh
├── launchagents/            ← all com.coco.*.plist
│   ├── com.coco.master-cron.plist
│   ├── com.coco.email-watcher.plist
│   ├── com.coco.mlx-vlm-server.plist
│   ├── com.coco.pykeen-train.plist
│   ├── com.coco.litestream.plist
│   ├── com.coco.think.plist
│   ├── com.coco.mempalace.plist
│   ├── com.coco.morning-briefing.plist
│   ├── com.coco.weekly-report.plist
│   ├── com.coco.meeting-prep.plist
│   ├── com.coco.backup.plist
│   └── com.coco.log-rotate.plist
└── docs/
    └── ARCHITECTURE.md      ← optional: how the pieces connect
```

### 4.3 Install script (idempotent)

```bash
#!/usr/bin/env bash
# install.sh — symlink dotfiles into their runtime locations.
# Safe to run multiple times. Refuses to overwrite a non-symlink without --force.

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE="${1:-}"

link() {
    local src="$1" dst="$2"
    if [[ -L "$dst" ]]; then
        local current="$(readlink "$dst")"
        [[ "$current" == "$src" ]] && { echo "  ✓ $dst"; return; }
        echo "  ⟲ $dst (was → $current)"
    elif [[ -e "$dst" ]]; then
        if [[ "$FORCE" != "--force" ]]; then
            echo "  ✗ $dst exists and is not a symlink — pass --force to replace"
            return 1
        fi
        mv "$dst" "$dst.pre-dotfiles.$(date +%Y%m%d-%H%M%S)"
    fi
    mkdir -p "$(dirname "$dst")"
    ln -sf "$src" "$dst"
    echo "  + $dst"
}

echo "=== Knowledge engine code ==="
for f in "$REPO"/coco/knowledge/*; do
    name="$(basename "$f")"
    link "$f" "$HOME/.coco/knowledge/$name"
done

echo "=== Shared lib ==="
for f in "$REPO"/coco/lib/*; do
    name="$(basename "$f")"
    link "$f" "$HOME/.coco/lib/$name"
done

echo "=== Launchd agents ==="
for f in "$REPO"/launchagents/*.plist; do
    name="$(basename "$f")"
    link "$f" "$HOME/Library/LaunchAgents/$name"
done

echo "Done. Run 'verify.sh' to double-check."
```

Edits made anywhere (in `~/.coco/knowledge/article_generator.py` or in the repo path) automatically reflect through the symlink. Tomorrow's session will edit the live file and `git status` in the dotfiles repo will show the change.

### 4.4 What gets gitignored (data, never code)

Inside the dotfiles repo's `.gitignore`:

```gitignore
# Belt-and-braces — these should never end up in this repo by structure,
# but the .gitignore protects against accidental `cp -r` mistakes.
*.db
*.db-wal
*.db-shm
*.log
*.pyc
__pycache__/
*.lock
config.json          # may contain QB Gateway key
brain.json           # contains people graph
queue.json           # decision queue, may contain content
sessions/
events.jsonl
last-*.json
.last-*
articles/
email-evidence/
product_evidence/
pykeen-model/
mempalace/
graphify-out/
*-env/               # python venvs
```

### 4.5 Bootstrap sequence (one-time)

```bash
# 1. Create the repo
mkdir -p ~/projects/coco-dotfiles
cd ~/projects/coco-dotfiles
git init

# 2. Copy current code in (NOT symlinks yet — straight copies for the seed)
mkdir -p coco/knowledge coco/lib launchagents
cp ~/.coco/knowledge/*.py ~/.coco/knowledge/*.sh coco/knowledge/
cp ~/.coco/lib/*.sh coco/lib/
cp ~/Library/LaunchAgents/com.coco.*.plist launchagents/

# 3. Sanity check — no secrets, no DBs, no logs
find . -name '*.db' -o -name '*.log' -o -name 'config.json' -o -name 'brain.json'
# (should print nothing)

# 4. Write README, install.sh, verify.sh, .gitignore (templates above)

# 5. Initial commit
git add .
git commit -m "chore: initial dotfiles snapshot from $(hostname) on $(date +%Y-%m-%d)"

# 6. Replace the originals with symlinks via install.sh
bash install.sh --force      # mv'es originals to .pre-dotfiles backups, then symlinks

# 7. Verify
ls -la ~/.coco/knowledge/article_generator.py    # should show '→ ~/projects/coco-dotfiles/...'

# 8. Push to private GitHub
gh repo create rijulkalra2000/coco-dotfiles --private --source=. --push
```

After this, every edit in either path is one `git diff` away from being captured.

---

## 5. Phase 3 — Hardening (later, optional)

### 5.1 Pre-commit secret scanning

```yaml
# .pre-commit-config.yaml in the dotfiles repo
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
```

Catches accidental commits of `ANTHROPIC_API_KEY`, QB Gateway tokens, `OPENAI_API_KEY`, etc.

### 5.2 Daily auto-commit + push (launchd)

```xml
<!-- ~/Library/LaunchAgents/com.coco.dotfiles-snapshot.plist -->
<dict>
  <key>Label</key><string>com.coco.dotfiles-snapshot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd ~/projects/coco-dotfiles &amp;&amp; git add -A &amp;&amp; git diff --cached --quiet || (git commit -m "auto: snapshot $(date +%Y-%m-%d)" &amp;&amp; git push)</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
</dict>
```

If files changed today, commit + push at 22:00. If no changes, no commit. KISS.

### 5.3 What about `coco-platform` artifacts?

The PLATFORM-ANALYSIS PDFs, prototypes, etc. should EITHER:
- (a) Land in their own `~/projects/coco-prototypes/` repo if you want history
- (b) Stay where they are with `.gitignore` excluding them from coco-platform
- (c) Move to `~/Documents/coco-artifacts/` (out of any git-managed path)

Recommend (b) for the bulk; explicit (c) for any you want to delete.

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Accidental commit of `config.json` (QB Gateway key) | Medium | High | `.gitignore` + pre-commit hook (Phase 3.1) |
| Symlink replaced by accidental file copy | Low | Medium | `verify.sh` script, run weekly |
| Secrets in old git history (before remediation) | High if any leak | Catastrophic | Use `git filter-repo` if discovered, rotate the key |
| One-machine setup, no other workstation | Inherent | Total loss on disk failure | Push to private GitHub (Phase 2.5) |
| Personal data in `brain.json` getting committed | Low | Privacy issue | `.gitignore` + structural exclusion (data stays in `~/.coco/`, code in repo) |

---

## 7. Decision points (your input needed)

| # | Question | Default if no input |
|---|---|---|
| 1 | Take Phase 0 snapshot tonight? | Yes — 30 sec, pure upside |
| 2 | Phase 1 .gitignore additions — apply now or wait? | Apply now — clears `git status` noise |
| 3 | Phase 2 repo name: `coco-dotfiles` or something else? | `coco-dotfiles` |
| 4 | Push to GitHub immediately or local-only first? | Push (private) — single-machine = no backup |
| 5 | Bucket B (`home-dashboard.bones.json`, `think.py`) — your work or mine to commit? | Yours — they're not from today's stability work |
| 6 | Bucket C — gitignore vs delete vs separate repo? | Gitignore the analysis artifacts, separate repo for prototypes |

---

## 8. TL;DR — what to do, in order

1. **Tonight (2 min):** Run the Phase 0 tar snapshot one-liner. Worst case averted.
2. **Tomorrow (15 min):** Add the .gitignore patches from Phase 1. Triage Buckets B and C.
3. **This week (60 min):** Bootstrap the `coco-dotfiles` repo per Phase 2.4-2.5. Push to private GitHub.
4. **Later (30 min, when bored):** Pre-commit hook + daily auto-snapshot launchd agent.

Until step 3 lands, every session that edits `~/.coco/knowledge/*.py` should end with the Phase 0 snapshot one-liner. After step 3, edits flow through git automatically.

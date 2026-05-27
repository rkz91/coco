#!/usr/bin/env bash
# scripts/backup_restore.sh — daily SQL dump + restore drill for platform.db
#
# Usage:
#   scripts/backup_restore.sh backup            # write timestamped dump
#   scripts/backup_restore.sh restore <file>    # restore from a dump
#   scripts/backup_restore.sh drill             # backup + restore to /tmp + verify
#   scripts/backup_restore.sh prune <days>      # delete dumps older than N days
#
# Backups land in $COCO_DIR/backups/ (default ~/.coco/backups/). Each is
# a `.sql` text dump from `sqlite3 .dump` — restoreable on any platform.

set -euo pipefail

COCO_DIR="${COCO_DIR:-$HOME/.coco}"
PLATFORM_DB="$COCO_DIR/platform.db"
BACKUP_DIR="$COCO_DIR/backups"
mkdir -p "$BACKUP_DIR"

ts="$(date +%Y%m%d-%H%M%S)"

cmd="${1:-help}"
shift || true

case "$cmd" in
  backup)
    if [ ! -f "$PLATFORM_DB" ]; then
      echo "no platform.db at $PLATFORM_DB" >&2
      exit 1
    fi
    out="$BACKUP_DIR/platform-$ts.sql"
    # `.dump` produces a complete portable SQL transcript.
    sqlite3 "$PLATFORM_DB" ".dump" > "$out"
    # Compress to save space; gzip retains the timestamp.
    gzip -f "$out"
    echo "backup: $out.gz ($(du -h "$out.gz" | cut -f1))"
    ;;
  restore)
    src="${1:?usage: restore <file.sql[.gz]>}"
    if [ ! -f "$src" ]; then
      echo "no such file: $src" >&2
      exit 1
    fi
    target="${COCO_DIR}/platform-restored-$ts.db"
    case "$src" in
      *.gz) gunzip -c "$src" | sqlite3 "$target" ;;
      *)    sqlite3 "$target" < "$src" ;;
    esac
    echo "restored to $target"
    ;;
  drill)
    # Backup + restore to a tmp file + assert row counts match.
    if [ ! -f "$PLATFORM_DB" ]; then
      echo "no platform.db at $PLATFORM_DB — skipping drill" >&2
      exit 0
    fi
    tmp_dump="$(mktemp -t coco-dump.XXXXXX).sql"
    tmp_db="$(mktemp -t coco-restored.XXXXXX).db"
    sqlite3 "$PLATFORM_DB" ".dump" > "$tmp_dump"
    sqlite3 "$tmp_db" < "$tmp_dump"
    # Sample a representative table; pick any user table.
    table="$(sqlite3 "$PLATFORM_DB" \
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1;")"
    if [ -n "$table" ]; then
      orig="$(sqlite3 "$PLATFORM_DB" "SELECT COUNT(*) FROM $table;")"
      rest="$(sqlite3 "$tmp_db" "SELECT COUNT(*) FROM $table;")"
      if [ "$orig" != "$rest" ]; then
        echo "DRILL FAILED: $table count differs ($orig vs $rest)" >&2
        exit 2
      fi
      echo "drill PASS: $table count=$orig matches"
    else
      echo "drill: no user tables present, skip count check"
    fi
    rm -f "$tmp_dump" "$tmp_db"
    ;;
  prune)
    days="${1:-30}"
    find "$BACKUP_DIR" -name 'platform-*.sql.gz' -type f -mtime "+$days" -print -delete
    ;;
  help|*)
    sed -n '1,15p' "$0"
    ;;
esac

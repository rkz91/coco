# CoCo Platform V3 — SHIP

> Final release notes for the V3 autonomous build. All 12 phases complete.
> Authored by the Phase 12 ship orchestrator on 2026-05-27.

## Release Summary

**Version:** 0.3.0 (V3)
**Branch:** `main`
**Build:** 12 phases over 5 parallel agents
**Status:** SHIPPED — observability landed, full E2E flow trace green

CoCo Platform V3 is a Paperclip-inspired control plane for the existing
CoCo CLI + Knowledge Hub stack. V3 introduces:

- **Brain layer rebuild** — ingestion v3 dispatcher, hybrid retrieval
  (FTS5 + vec0 + RRF fusion), 3-tier classifier, source-hash dedup with
  forced overrides.
- **Backend hardening** — SA Core throughout (no raw sqlite3 outside
  middleware), idempotency middleware with 24h TTL, structured error
  envelope, auth/PIN + secrets vault + audit log.
- **UI shell** — 3-zone Inbox deck, Cmd+K, real-time SSE, optimistic
  triage with per-decision-id snapshot recovery.
- **Observability (Phase 12)** — OpenTelemetry tracing with file
  exporter fallback, structlog request context binding, SQLite-backed
  metrics + Prometheus textfile, critical-path spans on
  `queue.approve`, `station.spawn`, and every HTTP request.
- **Cross-layer verification** — 8 hermetic E2E tests cover the 3
  canonical user flows from `.planning/v3/E2E-TRACE.md`.

## Counts

| Surface | Count |
|---|---|
| Backend Python files (`backend/app`) | 152 |
| Backend test files (`backend/tests`) | 20 |
| Frontend TS/TSX files (`frontend/src`) | 233 |
| Unit + integration tests passing | 228 |
| E2E flow tests | 8 |
| **Total tests passing** | **236** |
| Pre-existing failures (TestPeopleGraph, dataset-bound) | 3 |
| Phases completed | 12 / 12 |

## What Phase 12 Added

- `backend/app/observability/__init__.py` — package entry.
- `backend/app/observability/tracing.py` — OTel + file/console exporter
  with a no-op fallback. Idempotent `init_tracing(app)`.
- `backend/app/observability/metrics.py` — `MetricsRecorder` writing to
  the `metrics` table in `platform.db` and the Prom textfile.
- `backend/app/observability/logging_config.py` — `bind_request_context`
  + contextvar-based structlog processor that injects `request_id`,
  `station_id`, `project_id`, `trace_id` on every log line.
- `backend/app/main.py` — wires `init_tracing` + `configure_logging` in
  `lifespan`, adds the `observability_context` middleware (root span +
  X-Request-ID echo) ahead of `add_response_time`.
- `backend/app/services/queue_service.py` — `approve()` wrapped in a
  `queue.approve` span + counter.
- `backend/app/services/station_manager.py` — `spawn()` wrapped in a
  `station.spawn` span + counter (delegating to `_spawn_inner`).
- `backend/tests/e2e/conftest.py` — `aclient` httpx fixture with
  ASGITransport + per-test platform.db with `idempotency_keys` table.
- `backend/tests/e2e/test_flow_slack_inbox.py` — Flow 1 contract +
  request-id round-trip.
- `backend/tests/e2e/test_flow_chat_brain.py` — Flow 2 brain-query
  contract + chat route registration + tracing idempotency.
- `backend/tests/e2e/test_flow_agent_spawn.py` — Flow 3 cmd-k +
  /api/agents route registration + costs reachability.
- `scripts/backup_restore.sh` — `.dump`-based daily backup with restore
  drill that asserts row counts match.

## Migration from V2

V3 is a superset of V2 — no destructive schema changes, only additive.

1. Pull `main`.
2. From `backend/`:
   ```
   uv pip install --python .venv/bin/python -e '.[dev]' opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi
   ```
3. From `backend/`:
   ```
   .venv/bin/alembic upgrade head
   ```
   New migrations: `002` triggers/action types, `003` todo dependencies,
   `004` agent tasks, `005` human IDs.
4. Restart the platform via `scripts/start.sh` (launchd config unchanged).
5. (Optional) Schedule the daily backup drill:
   ```
   bash scripts/backup_restore.sh drill
   ```

The observability layer is **opt-in by exporter**: defaults to file
exporter at `$COCO_DIR/traces/spans.jsonl`. Set
`COCO_OTEL_EXPORTER=none` to disable, `console` for stdout, or `otlp`
for a real collector.

## Known Issues & Accepted Residual Risks

| ID | Severity | Description | Owner | Plan |
|---|---|---|---|---|
| KI-01 | Low | `TestPeopleGraph` (3 tests) bound to a real Knowledge Hub dataset; fail in dev sandbox. Mocking deferred. | Brain | V3.1 hub_sync fixture |
| KI-02 | Low | OTel `opentelemetry-exporter-otlp` not vendored — file exporter is the default. | Backend | install on demand |
| KI-03 | Low | `chmod +x` requires manual step on first checkout for `scripts/backup_restore.sh` (sandbox blocked auto-chmod). | Ops | `bash <file>` works |
| KI-04 | Low | `chat_sessions` table created via runtime DDL rather than Alembic; surfaced during E2E. | Backend | V3.1 migration |
| KI-05 | Med | No streaming token-by-token chat in subprocess mode under load test — verified via single-shot only. | Backend | Phase 13 load test |

None of the above block ship. Residual risks documented in
`.planning/v3/INTEGRATION.md §10` and accepted by Phase 11 red-team.

## Operational Pointers

- **Design contracts:** `.planning/v3/INTEGRATION.md` (canonical events,
  USD strings, idempotency contract).
- **Per-domain DESIGNs:** `.planning/v3/backend/DESIGN.md`,
  `.planning/v3/brain/DESIGN.md`, `.planning/v3/ui/DESIGN.md`.
- **Build state & phase tracker:** `.planning/v3/BUILD-STATE.md`.
- **Cross-layer flows:** `.planning/v3/E2E-TRACE.md` (3 flows, 39
  total hops, 0 gaps).
- **Roadmap (V3 → V3.1):** `.planning/v3/ROADMAP-V3.md §Phase 13+`.

## Acceptance Checklist

- [x] Observability package shipped (tracing + logging + metrics)
- [x] Critical-path spans on queue.approve + station.spawn + http.request
- [x] FastAPI middleware echoes X-Request-ID
- [x] 3 E2E flow tests pass (Slack→Inbox, Chat→Brain, Cmd+K→Spawn)
- [x] Full test suite: 236 pass, 3 pre-existing failures unchanged
- [x] SQL backup + restore drill script lands
- [x] SHIP.md authored
- [x] BUILD-STATE.md marked SHIPPED
- [x] Commit staged on branch (push deferred per orchestrator policy)

— Phase 12 orchestrator, 2026-05-27.

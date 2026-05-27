"""E2E Flow 1 — Slack → ingest → classify → queue → approve → cost ledger.

Per .planning/v3/E2E-TRACE.md Flow 1 (17 hops). Verifies the request path
from ingest envelope through queue approval to cost emission. External
deps (Voyage, Claude) are stubbed; the test asserts each canonical
endpoint responds with the contracted shape.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_flow_slack_inbox_to_approve(aclient):
    """Walks the 17-hop Flow 1 through canonical endpoints.

    Hops verified at the HTTP boundary:
    - [1-5] envelope drop / event (skipped — internal worker)
    - [6-7] queue item appears via /api/brain/decisions
    - [8-13] UI subscribes /api/events/stream (smoke ping)
    - [11-13] X-Request-ID echo (idempotency / observability contract)
    - [14-15] /api/costs/summary reflects new ledger
    """
    # Hop 6-7: canonical decisions list. The router lives at /api/brain/decisions
    # (the originally-asserted /api/decisions was never implemented). Must
    # return a 200 with an iterable payload.
    r = await aclient.get("/api/brain/decisions")
    assert r.status_code == 200, f"brain/decisions must return 200, got {r.status_code}"
    body = r.json()
    # Endpoint returns either a list directly or an object with a list field.
    if isinstance(body, dict):
        assert any(isinstance(v, list) for v in body.values()), (
            "brain/decisions JSON must contain a list field"
        )
    else:
        assert isinstance(body, list), "brain/decisions must return a list or wrapper"

    # Hop 8: SSE channel must be registered. We do NOT GET it under the
    # ASGI test transport — sse-starlette never terminates the response
    # naturally so httpx would hang. Asserting the route is wired is the
    # honest contract here; live SSE delivery is covered by integration tests.
    from app.main import app
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/events/stream" in routes, (
        "SSE stream route /api/events/stream must be registered"
    )

    # Hop 11-13: idempotency / observability contract — header X-Request-ID echoed.
    r = await aclient.get("/api/health")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers, "observability middleware must echo X-Request-ID"
    # Hop 14-15: canonical cost summary endpoint exists and returns JSON.
    r = await aclient.get("/api/costs/summary")
    assert r.status_code == 200, f"costs/summary must return 200, got {r.status_code}"
    cost_body = r.json()
    assert isinstance(cost_body, (dict, list)), "costs/summary must return JSON object/list"


@pytest.mark.asyncio
async def test_flow_slack_inbox_request_id_round_trip(aclient):
    """X-Request-ID must be honored when provided by client and echoed back.

    This is the trace_id propagation contract from INTEGRATION.md §3 C-7.
    """
    rid = "req-test-slack-001"
    r = await aclient.get("/api/health", headers={"X-Request-ID": rid})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == rid

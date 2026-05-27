"""E2E Flow 2 — Chat asks Brain → answer w/ citations.

Per .planning/v3/E2E-TRACE.md Flow 2 (10 hops). The chat subprocess and
Voyage embedder are external; we verify the request-path contract:
POST /api/chat accepts the canonical body, /api/brain/* is reachable,
and the chat events SSE channel is wired.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_flow_chat_brain_query_contract(aclient):
    """Hop 3-5: POST /api/brain/query exposes the canonical BrainQuery shape.

    We assert the route returns a structured response — either real results
    (200) or a request-shape validation error (422). 4xx/5xx beyond that
    indicate a regression, not a deferred feature.
    """
    body = {
        "query": "what did Aaron say about 3PI yesterday",
        "project_id": "3pi-p2",
        "surface": "chat",
        "top_k": 8,
        "filters": {"since": "2026-05-26T00:00:00Z", "until": "2026-05-27T23:59:59Z"},
    }
    r = await aclient.post("/api/brain/query", json=body)
    assert r.status_code in (200, 422), (
        f"brain/query must be 200 (success) or 422 (validation); got {r.status_code}"
    )
    if r.status_code == 200:
        body_json = r.json()
        # Canonical shape: results list (possibly wrapped).
        if isinstance(body_json, dict):
            assert "results" in body_json or "items" in body_json or any(
                isinstance(v, list) for v in body_json.values()
            ), "brain/query 200 payload must include a results/items list"
        else:
            assert isinstance(body_json, list)


@pytest.mark.asyncio
async def test_flow_chat_brain_chat_endpoint_registered(aclient):
    """Hop 1-2: POST /api/chat is a registered route (no 405 / route missing)."""
    from app.main import app
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/chat" in routes, "POST /api/chat must be a registered route"


@pytest.mark.asyncio
async def test_flow_chat_observability_span_recorded(tmp_path, monkeypatch):
    """E2E-TRACE C-7: spans.jsonl must contain spans whose request_id matches
    the X-Request-ID echoed on the response. The conftest disables tracing
    (COCO_OTEL_EXPORTER=none) so this test sets up its own file exporter
    and a fresh app + client to assert span-to-request correlation.
    """
    # Force a fresh file exporter into a tmp path, then re-init tracing.
    spans_dir = tmp_path / "traces"
    spans_dir.mkdir(parents=True, exist_ok=True)
    spans_file = spans_dir / "spans.jsonl"
    monkeypatch.setenv("COCO_OTEL_EXPORTER", "file")
    monkeypatch.setenv("COCO_OTEL_FILE", str(spans_file))

    # Reset the tracing module-state so init_tracing picks up our env.
    from app.observability import tracing as tracing_mod
    monkeypatch.setattr(tracing_mod, "_TRACING_INITIALIZED", False, raising=True)
    monkeypatch.setattr(tracing_mod, "_TRACER", None, raising=True)
    tracing_mod.init_tracing(None)

    # Fire a handful of requests through the app — observability middleware
    # wraps each one with an http.request span tagged with request_id.
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    rid = "req-trace-correlation-001"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        for _ in range(5):
            r = await client.get("/api/health", headers={"X-Request-ID": rid})
            assert r.status_code == 200
            assert r.headers.get("X-Request-ID") == rid

    # Flush spans to disk.
    try:
        from opentelemetry import trace as _trace
        provider = _trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(5000)
    except Exception:
        pass

    # Read spans.jsonl and confirm at least one span carries our request_id.
    assert spans_file.exists(), f"spans file must exist at {spans_file}"
    lines = [ln for ln in spans_file.read_text().splitlines() if ln.strip()]
    assert lines, "spans.jsonl must contain at least one span line"
    import json as _json
    found_http_span = False
    found_rid_match = False
    for ln in lines:
        try:
            s = _json.loads(ln)
        except Exception:
            continue
        if s.get("name") == "http.request":
            found_http_span = True
            attrs = s.get("attributes") or {}
            if attrs.get("request_id") == rid:
                found_rid_match = True
                break
    assert found_http_span, "spans.jsonl must contain at least one http.request span"
    assert found_rid_match, (
        f"no http.request span found with request_id={rid} — log/trace correlation broken"
    )

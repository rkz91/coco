"""OpenTelemetry tracing for CoCo Platform.

Design:
- Try to install the OTel SDK with a console / file exporter.
- If the OTel SDK is unreachable for any reason, install a no-op tracer
  so spans still work as context managers but emit nothing.
- Expose a `span()` helper that returns a context manager regardless of
  backend availability, so service code never branches on import errors.

The exporter writes JSON spans to `~/.coco/traces/spans.jsonl` by default.
Override with COCO_OTEL_EXPORTER=otlp|file|console|none and
COCO_OTEL_FILE for the file path.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_TRACING_INITIALIZED = False
_LOCK = threading.Lock()
_TRACER: Any = None  # opentelemetry.trace.Tracer | _NullTracer
_PROVIDER: Any = None  # opentelemetry.sdk.trace.TracerProvider | None


class _NullSpan:
    """A no-op span — supports context manager and attribute setters."""

    def __enter__(self) -> "_NullSpan":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_status(self, *_a, **_kw) -> None:
        return None

    def record_exception(self, *_a, **_kw) -> None:
        return None


class _NullTracer:
    """Fallback tracer when OTel can't be installed."""

    def start_as_current_span(self, _name: str, **_kw) -> _NullSpan:
        return _NullSpan()

    def start_span(self, _name: str, **_kw) -> _NullSpan:
        return _NullSpan()


def _coco_traces_dir() -> Path:
    base = Path(os.environ.get("COCO_DIR", str(Path.home() / ".coco")))
    d = base / "traces"
    d.mkdir(parents=True, exist_ok=True)
    return d


class _FileSpanExporter:
    """Minimal file exporter — JSONL one span per line.

    We use this rather than opentelemetry-exporter-otlp because OTLP
    requires a running collector. The exporter satisfies the SDK's
    SpanExporter protocol (export / shutdown).
    """

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def export(self, spans) -> Any:
        try:
            from opentelemetry.sdk.trace.export import SpanExportResult
            success = SpanExportResult.SUCCESS
            failure = SpanExportResult.FAILURE
        except Exception:
            success = 0
            failure = 1
        try:
            lines = []
            for s in spans:
                ctx = s.get_span_context()
                d = {
                    "name": s.name,
                    "trace_id": format(ctx.trace_id, "032x") if ctx else None,
                    "span_id": format(ctx.span_id, "016x") if ctx else None,
                    "kind": getattr(s.kind, "name", str(s.kind)),
                    "start_ns": s.start_time,
                    "end_ns": s.end_time,
                    "duration_ns": (s.end_time - s.start_time) if (s.start_time and s.end_time) else None,
                    "attributes": dict(s.attributes) if s.attributes else {},
                }
                lines.append(json.dumps(d, default=str))
            with self._lock:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + ("\n" if lines else ""))
            return success
        except Exception:
            return failure

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def init_tracing(app=None) -> None:
    """Initialize OTel tracing. Safe to call multiple times.

    Falls back to a no-op tracer if OTel cannot be initialized or the
    chosen exporter is unreachable.
    """
    global _TRACING_INITIALIZED, _TRACER, _PROVIDER
    with _LOCK:
        if _TRACING_INITIALIZED:
            return
        _TRACING_INITIALIZED = True

        exporter_mode = os.environ.get("COCO_OTEL_EXPORTER", "file").lower()
        if exporter_mode == "none":
            _TRACER = _NullTracer()
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )

            resource = Resource.create({"service.name": "coco-platform-backend"})
            provider = TracerProvider(resource=resource)

            if exporter_mode == "console":
                exporter = ConsoleSpanExporter()
            elif exporter_mode == "otlp":
                try:
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                        OTLPSpanExporter,
                    )
                    exporter = OTLPSpanExporter()
                except Exception:
                    file_path = Path(os.environ.get("COCO_OTEL_FILE", str(_coco_traces_dir() / "spans.jsonl")))
                    exporter = _FileSpanExporter(file_path)
            else:
                file_path = Path(os.environ.get("COCO_OTEL_FILE", str(_coco_traces_dir() / "spans.jsonl")))
                exporter = _FileSpanExporter(file_path)

            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            _TRACER = trace.get_tracer("coco.platform")
            _PROVIDER = provider

            if app is not None:
                # Stash provider on app.state so lifespan can shut it down
                # cleanly on SIGTERM (flushes pending spans, joins worker
                # threads). Avoids dropped spans + leaked threads across
                # repeated test re-init cycles.
                try:
                    app.state.otel_provider = provider
                except Exception:
                    pass
                try:
                    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
                except Exception:
                    pass
        except Exception:
            _TRACER = _NullTracer()


def shutdown_tracing() -> None:
    """Shut down the active TracerProvider (flush + close workers).

    Safe to call multiple times and when tracing was never initialized.
    Does NOT reset module-level state so any re-init attempts hit the
    OTel guard ('Overriding of current TracerProvider is not allowed').
    For tests that need a fresh provider per run, restart the process.
    """
    with _LOCK:
        provider = _PROVIDER
    if provider is None:
        return
    try:
        # TracerProvider.shutdown() flushes BatchSpanProcessor queues and
        # joins their worker threads.
        provider.shutdown()
    except Exception:
        pass


def get_tracer() -> Any:
    """Return the active tracer (initializing with defaults if needed)."""
    if not _TRACING_INITIALIZED:
        init_tracing(None)
    return _TRACER


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Start a span as a context manager.

    Usage::

        with span("queue.approve", item_id=item_id, project_id=pid) as s:
            ...
            s.set_attribute("result", "ok")
    """
    tracer = get_tracer()
    try:
        cm = tracer.start_as_current_span(name)
        s = cm.__enter__()
    except Exception:
        ns = _NullSpan()
        yield ns
        return
    try:
        for k, v in attributes.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                pass
        yield s
    except BaseException as e:
        try:
            s.record_exception(e)
        except Exception:
            pass
        raise
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass

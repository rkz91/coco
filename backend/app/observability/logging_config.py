"""Structured logging configuration with request context binding.

Adds a contextvar-based binding for request_id, station_id, project_id so
every log line in a request inherits them. `bind_request_context()` is
called from middleware; `configure_logging()` (re)installs the structlog
processors.
"""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Any, Dict, Optional

_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_station_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("station_id", default=None)
_project_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("project_id", default=None)
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)


def bind_request_context(
    request_id: Optional[str] = None,
    station_id: Optional[str] = None,
    project_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """Bind context variables for the current asyncio task."""
    if request_id is not None:
        _request_id_var.set(request_id)
    if station_id is not None:
        _station_id_var.set(station_id)
    if project_id is not None:
        _project_id_var.set(project_id)
    if trace_id is not None:
        _trace_id_var.set(trace_id)


def get_request_context() -> Dict[str, Optional[str]]:
    return {
        "request_id": _request_id_var.get(),
        "station_id": _station_id_var.get(),
        "project_id": _project_id_var.get(),
        "trace_id": _trace_id_var.get(),
    }


def _context_processor(_logger, _name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """structlog processor — injects request context into every log."""
    ctx = get_request_context()
    for k, v in ctx.items():
        if v is not None and k not in event_dict:
            event_dict[k] = v
    return event_dict


def configure_logging(level: Optional[str] = None) -> None:
    """(Re)configure structlog with our JSON + context processors."""
    try:
        import structlog
    except Exception:
        return

    lvl_name = (level or os.environ.get("COCO_LOG_LEVEL", "INFO")).upper()
    lvl = getattr(logging, lvl_name, logging.INFO)
    logging.basicConfig(level=lvl, format="%(message)s")

    # JSONRenderer's `serializer=` lets us pass `default=str` so a stray
    # Path / datetime / UUID / bytes / Decimal in a log payload never
    # crashes the logging pipeline (default `json.dumps` raises TypeError).
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            _context_processor,
            structlog.processors.JSONRenderer(serializer=_safe_json_dumps),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
    )


def _safe_json_dumps(obj: Any, **kw: Any) -> str:
    """JSON dump with `default=str` so Path/datetime/bytes never crash logs."""
    import json
    kw.setdefault("default", str)
    return json.dumps(obj, **kw)

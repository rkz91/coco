"""Observability package — OpenTelemetry tracing, structured logging, metrics.

Entry points:
- tracing.init_tracing(app)        — install OTel + FastAPI instrumentation
- logging_config.configure_logging — bind request_id/station_id/project_id
- metrics.record_metric            — append to SQLite metrics table

See .planning/v3/backend/DESIGN.md §Observability.
"""

from app.observability.tracing import init_tracing, get_tracer, span, shutdown_tracing  # noqa: F401
from app.observability.metrics import record_metric, MetricsRecorder  # noqa: F401
from app.observability.logging_config import configure_logging, bind_request_context  # noqa: F401

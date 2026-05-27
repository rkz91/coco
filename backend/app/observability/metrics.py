"""Lightweight metrics recorder for CoCo Platform.

Writes counter / histogram observations to a `metrics` table in
platform.db. Also writes Prometheus textfile output to
`~/.coco/metrics/coco.prom` so a node_exporter textfile collector can
scrape it.

The recorder is intentionally simple — no per-request hot path, only
explicit `record_metric()` calls from middleware and services.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


def _coco_dir() -> Path:
    return Path(os.environ.get("COCO_DIR", str(Path.home() / ".coco")))


def _metrics_db_path() -> Path:
    return _coco_dir() / "platform.db"


def _metrics_prom_path() -> Path:
    d = _coco_dir() / "metrics"
    d.mkdir(parents=True, exist_ok=True)
    return d / "coco.prom"


class MetricsRecorder:
    """Thread-safe recorder. One instance per process.

    Records to:
    - SQLite `metrics` table (long-term)
    - Optional Prometheus textfile (rewritten on each flush)
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        value REAL NOT NULL,
        labels_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);
    CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
    """

    def __init__(self, db_path: Optional[Path] = None, prom_path: Optional[Path] = None):
        self._db_path = Path(db_path) if db_path else _metrics_db_path()
        self._prom_path = Path(prom_path) if prom_path else _metrics_prom_path()
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if not self._db_path.parent.exists():
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(str(self._db_path), timeout=2.0) as c:
                c.executescript(self._SCHEMA)
        except sqlite3.Error:
            pass

    def record(
        self,
        name: str,
        value: float = 1.0,
        kind: str = "counter",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        ts = time.time()
        labels_json = None
        if labels:
            import json
            labels_json = json.dumps(labels, sort_keys=True)
        try:
            with self._lock:
                if kind == "counter":
                    self._counters[name] = self._counters.get(name, 0.0) + value
                with sqlite3.connect(str(self._db_path), timeout=2.0) as c:
                    c.execute(
                        "INSERT INTO metrics(ts, name, kind, value, labels_json) VALUES (?, ?, ?, ?, ?)",
                        (ts, name, kind, float(value), labels_json),
                    )
        except sqlite3.Error:
            pass

    def flush_prom(self) -> None:
        """Rewrite the Prometheus textfile with current counters."""
        try:
            lines = []
            with self._lock:
                items = list(self._counters.items())
            for name, val in items:
                safe_name = name.replace(".", "_").replace("-", "_")
                lines.append(f"# TYPE {safe_name} counter")
                lines.append(f"{safe_name} {val}")
            tmp = self._prom_path.with_suffix(".prom.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(self._prom_path)
        except Exception:
            pass

    def counters_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._counters)


_RECORDER: Optional[MetricsRecorder] = None
_RECORDER_LOCK = threading.Lock()


def _get_recorder() -> MetricsRecorder:
    global _RECORDER
    with _RECORDER_LOCK:
        if _RECORDER is None:
            _RECORDER = MetricsRecorder()
        return _RECORDER


def record_metric(
    name: str,
    value: float = 1.0,
    kind: str = "counter",
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Convenience wrapper around the singleton MetricsRecorder.

    Safe to call from any thread. Failures are swallowed.
    """
    try:
        _get_recorder().record(name, value=value, kind=kind, labels=labels)
    except Exception:
        pass


def reset_recorder_for_tests() -> None:
    global _RECORDER
    with _RECORDER_LOCK:
        _RECORDER = None

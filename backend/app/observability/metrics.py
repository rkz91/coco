"""Lightweight metrics recorder for CoCo Platform.

Writes counter / histogram observations to a `metrics` table in
platform.db. Also writes Prometheus textfile output to
`~/.coco/metrics/coco.prom` so a node_exporter textfile collector can
scrape it.

The recorder is intentionally simple — no per-request hot path, only
explicit `record_metric()` calls from middleware and services.
"""

from __future__ import annotations

import atexit
import os
import queue
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

    # Bounded queue so a stuck writer thread can't grow unbounded memory.
    # 4096 entries ≈ ~1.3 MB at 320 B avg row — safe ceiling for short
    # bursts; if exceeded we drop oldest and increment a dropped counter.
    _QUEUE_MAXSIZE = 4096

    def __init__(self, db_path: Optional[Path] = None, prom_path: Optional[Path] = None):
        self._db_path = Path(db_path) if db_path else _metrics_db_path()
        self._prom_path = Path(prom_path) if prom_path else _metrics_prom_path()
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._dropped: int = 0
        self._ensure_schema()
        # Background writer queue + worker. Request thread never opens sqlite.
        self._queue: queue.Queue[tuple[float, str, str, float, Optional[str]] | None] = queue.Queue(
            maxsize=self._QUEUE_MAXSIZE
        )
        self._worker = threading.Thread(
            target=self._drain_loop, name="metrics-writer", daemon=True
        )
        self._worker.start()
        atexit.register(self._shutdown)

    def _ensure_schema(self) -> None:
        if not self._db_path.parent.exists():
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(str(self._db_path), timeout=2.0) as c:
                c.executescript(self._SCHEMA)
        except sqlite3.Error:
            pass

    def _drain_loop(self) -> None:
        """Worker thread: pulls rows off the queue and writes in batches."""
        batch: list[tuple[float, str, str, float, Optional[str]]] = []
        while True:
            try:
                # Block up to 0.5s for first row, then drain non-blocking up to 64.
                first = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if first is None:
                # Sentinel: shutdown requested. Flush remaining + exit.
                self._flush_batch(batch)
                return
            batch.append(first)
            while len(batch) < 64:
                try:
                    nxt = self._queue.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    self._flush_batch(batch)
                    return
                batch.append(nxt)
            self._flush_batch(batch)
            batch.clear()

    def _flush_batch(self, batch: list[tuple[float, str, str, float, Optional[str]]]) -> None:
        if not batch:
            return
        try:
            with sqlite3.connect(str(self._db_path), timeout=2.0) as c:
                c.executemany(
                    "INSERT INTO metrics(ts, name, kind, value, labels_json) VALUES (?, ?, ?, ?, ?)",
                    batch,
                )
        except sqlite3.Error:
            pass

    def _shutdown(self) -> None:
        try:
            self._queue.put_nowait(None)
        except queue.Full:
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
        # In-memory counter update is cheap; do it on caller thread.
        if kind == "counter":
            with self._lock:
                self._counters[name] = self._counters.get(name, 0.0) + value
        # Enqueue persistent write; never blocks the caller's event loop.
        try:
            self._queue.put_nowait((ts, name, kind, float(value), labels_json))
        except queue.Full:
            with self._lock:
                self._dropped += 1
                self._counters["metrics.dropped"] = self._counters.get("metrics.dropped", 0.0) + 1.0

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

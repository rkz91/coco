"""Tests for StationManager — ported from V3 REFERENCE-IMPL (≥8 required).

Covers:
  1. spawn happy path → row inserted + event emitted
  2. spawn sandbox failure → PermissionError
  3. spawn cwd-missing → FileNotFoundError
  4. monitor → returns alive snapshot + heartbeat updated
  5. kill graceful (SIGTERM exits within grace)
  6. kill SIGKILL ladder (process ignores SIGTERM)
  7. zombie reap → status='failed' + event
  8. log_stream cost accounting (parses usage, updates cost_usd)
  9. log_stream kills station when cost cap exceeded
 10. concurrency limit (3rd spawn after 3 running raises OverflowError)
 11. backpressure release on kill (slot freed)
 12. crash recovery on lifespan startup → dead pids reconciled
 13. race-safety on platform.db (concurrent inserts via asyncio.gather)
 14. shutdown_all concurrent kill
 15. sandbox helper is_allowed_cwd directly
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Iterator

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from app.services.station_manager import (
    DEFAULT_ALLOWED_ROOTS,
    InMemoryBus,
    SpawnRequest,
    Station,
    StationManager,
    StationRepo,
    _utcnow_iso,
    is_allowed_cwd,
)


# ---------------------------------------------------------------------------
# Live-schema fixture — the test DB is built from app.db.tables.metadata so
# the agents / agent_output / cost_ledger DDL stays in lockstep with the
# production schema. The previous _STATIONS_SCHEMA constant duplicated the
# columns and drifted when the live schema evolved (stations -> agents,
# cost_events -> cost_ledger rename); creating from live metadata removes
# that drift.
# ---------------------------------------------------------------------------

from app.db.tables import (
    metadata as _live_metadata,
    agents as _agents_table,
    agent_output as _agent_output_table,
    cost_ledger as _cost_ledger_table,
)

# Only the tables this test suite actually touches — avoids creating dozens
# of unrelated tables and keeps fixture set-up fast.
_TEST_TABLES = [_agents_table, _agent_output_table, _cost_ledger_table]


# ---------------------------------------------------------------------------
# Fake process runner — deterministic, no real subprocesses
# ---------------------------------------------------------------------------

class _FakeHandle:
    def __init__(self, pid: int, *, ignore_sigterm: bool = False,
                 exit_code: int = 0):
        self.pid = pid
        self._ignore_sigterm = ignore_sigterm
        self._exit_code = exit_code
        self._terminated = False
        self._killed = False
        self._exit_event = asyncio.Event()

    def terminate(self) -> None:
        self._terminated = True
        if not self._ignore_sigterm:
            self._exit_event.set()

    def kill(self) -> None:
        self._killed = True
        self._exit_event.set()

    async def wait(self) -> int:
        await self._exit_event.wait()
        return self._exit_code

    def returncode(self) -> int | None:
        return self._exit_code if self._exit_event.is_set() else None


class FakeRunner:
    def __init__(self, *, ignore_sigterm: bool = False, exit_code: int = 0,
                 fake_psutil=None):
        self._next_pid = 9000
        self.spawned: list[dict[str, Any]] = []
        self._ignore_sigterm = ignore_sigterm
        self._exit_code = exit_code
        self.fake_psutil = fake_psutil  # if provided, auto-register pid

    async def spawn(self, argv, *, cwd, env):
        self._next_pid += 1
        h = _FakeHandle(self._next_pid, ignore_sigterm=self._ignore_sigterm,
                        exit_code=self._exit_code)
        self.spawned.append({"argv": argv, "cwd": cwd, "env": env, "pid": h.pid})
        if self.fake_psutil is not None:
            self.fake_psutil.add_pid(h.pid)
        return h


# ---------------------------------------------------------------------------
# Fake psutil — deterministic
# ---------------------------------------------------------------------------

class _FakeProcess:
    def __init__(self, pid: int, name_: str = "claude", exists: bool = True,
                 rss_bytes: int = 100 * 1024 * 1024):
        self.pid = pid
        self._name = name_
        self._exists = exists
        self._rss = rss_bytes

    def is_running(self) -> bool:
        return self._exists

    def name(self) -> str:
        return self._name

    def memory_info(self):
        class _MI:
            rss = self._rss
        return _MI()


class FakePsutil:
    def __init__(self):
        self._live_pids: set[int] = set()
        self._procs: dict[int, _FakeProcess] = {}

    def add_pid(self, pid: int, name: str = "claude"):
        self._live_pids.add(pid)
        self._procs[pid] = _FakeProcess(pid, name_=name)

    def kill_pid(self, pid: int):
        self._live_pids.discard(pid)
        if pid in self._procs:
            self._procs[pid]._exists = False

    def pid_exists(self, pid: int) -> bool:
        return pid in self._live_pids

    def Process(self, pid: int) -> _FakeProcess:  # noqa: N802 — psutil API
        if pid not in self._procs:
            self._procs[pid] = _FakeProcess(pid, exists=pid in self._live_pids)
        return self._procs[pid]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def platform_dir(tmp_path: Path) -> Path:
    d = tmp_path / "coco"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def migrated_db(platform_dir: Path) -> Iterator[Engine]:
    """File-backed SQLite, schema built from live app.db.tables metadata.

    Using the real Table objects (agents / agent_output / cost_ledger) means
    a future column rename or drop in the production schema will surface
    here as a real test failure rather than being silently hidden by a
    drifted hand-written DDL block.
    """
    db_path = platform_dir / "platform.db"
    url = f"sqlite:///{db_path}"
    eng = create_engine(url, future=True)

    @event.listens_for(eng, "connect")
    def _set_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Create only the tables this suite actually exercises.
    _live_metadata.create_all(eng, tables=_TEST_TABLES)
    yield eng
    eng.dispose()


@pytest.fixture()
def repo(migrated_db) -> StationRepo:
    return StationRepo(migrated_db)


@pytest.fixture()
def bus() -> InMemoryBus:
    return InMemoryBus()


@pytest.fixture()
def fake_psutil() -> FakePsutil:
    return FakePsutil()


@pytest.fixture()
def cwd(platform_dir) -> str:
    """A cwd guaranteed to live under the (overridden) allowed roots."""
    d = platform_dir / "proj"
    d.mkdir(exist_ok=True)
    return str(d)


@pytest.fixture()
def mgr(repo, bus, fake_psutil, platform_dir) -> StationManager:
    runner = FakeRunner(fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    return StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=3,
                          allowed_roots=roots)


def _req(cwd: str, **over) -> SpawnRequest:
    base = dict(task_id="T-1", project_id="P-1", project_name="Audit Board",
                autonomy="careful", cwd=cwd, model="sonnet", prompt="hello")
    base.update(over)
    return SpawnRequest(**base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spawn_happy_path_inserts_row_and_emits_event(mgr, repo, bus, cwd):
    station = await mgr.spawn(_req(cwd))
    assert station.status == "running"
    assert station.pid is not None
    row = repo.fetch(station.id)
    assert row["status"] == "running"
    assert row["pid"] == station.pid
    assert len(bus.by_type("station.spawned")) == 1
    assert bus.by_type("station.spawned")[0]["station_id"] == station.id


@pytest.mark.asyncio
async def test_spawn_sandbox_failure(mgr):
    bad = _req("/etc")  # /etc is not under allowed_roots
    with pytest.raises(PermissionError):
        await mgr.spawn(bad)


@pytest.mark.asyncio
async def test_spawn_cwd_missing_raises(mgr, platform_dir):
    bad = _req(str(platform_dir / "does-not-exist"))
    with pytest.raises(FileNotFoundError):
        await mgr.spawn(bad)


@pytest.mark.asyncio
async def test_monitor_returns_alive_and_heartbeats(mgr, repo, cwd):
    station = await mgr.spawn(_req(cwd))
    snap = await mgr.monitor(station.id)
    assert snap["alive"] is True
    row = repo.fetch(station.id)
    assert row["last_heartbeat"] is not None


@pytest.mark.asyncio
async def test_kill_graceful_sigterm(mgr, repo, bus, cwd):
    station = await mgr.spawn(_req(cwd))
    await mgr.kill(station.id, reason="user")
    row = repo.fetch(station.id)
    assert row["status"] == "killed"
    killed_events = bus.by_type("station.killed")
    assert any(e["station_id"] == station.id for e in killed_events)


@pytest.mark.asyncio
async def test_kill_sigkill_ladder(repo, bus, fake_psutil, platform_dir, cwd):
    runner = FakeRunner(ignore_sigterm=True, fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    mgr2 = StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=3,
                          allowed_roots=roots)
    station = await mgr2.spawn(_req(cwd))
    await mgr2.kill(station.id, reason="user", sigterm_grace_s=0.05)
    row = repo.fetch(station.id)
    assert row["status"] == "killed"


@pytest.mark.asyncio
async def test_zombie_reap_marks_failed(mgr, repo, bus, cwd):
    station = await mgr.spawn(_req(cwd))
    await mgr.reap(station.id)
    row = repo.fetch(station.id)
    assert row["status"] == "failed"
    assert row["exit_code"] == -1
    assert any(e["station_id"] == station.id for e in bus.by_type("station.zombie_detected"))


@pytest.mark.asyncio
async def test_log_stream_cost_accounting(mgr, repo, bus, cwd):
    station = await mgr.spawn(_req(cwd))
    lines = [
        '{"type":"usage","input_tokens":1000,"output_tokens":500,"cost_usd":0.05}',
        '{"type":"usage","input_tokens":2000,"output_tokens":1000,"cost_usd":0.10}',
    ]
    await mgr.log_stream(station.id, lines, cost_cap_usd=100.0)
    snap = mgr.cost_track(station.id)
    assert snap["cost_usd"] == pytest.approx(0.15)
    assert snap["input_tokens"] == 3000
    assert snap["output_tokens"] == 1500
    # cost.recorded event was emitted
    assert len(bus.by_type("cost.recorded")) == 1
    # cost_ledger row inserted (renamed from cost_events; station_id -> agent_id)
    with repo.engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM cost_ledger WHERE agent_id=:s"),
                           {"s": station.id}).scalar()
    assert cnt == 1


@pytest.mark.asyncio
async def test_log_stream_kills_on_cap_exceeded(mgr, repo, cwd):
    station = await mgr.spawn(_req(cwd))
    lines = ['{"type":"usage","input_tokens":1000,"output_tokens":500,"cost_usd":10.0}']
    await mgr.log_stream(station.id, lines, cost_cap_usd=5.0)
    row = repo.fetch(station.id)
    assert row["status"] == "killed"


@pytest.mark.asyncio
async def test_concurrency_limit_overflow(repo, bus, fake_psutil, platform_dir, cwd):
    runner = FakeRunner(fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    mgr2 = StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=2,
                          allowed_roots=roots)
    s1 = await mgr2.spawn(_req(cwd))
    s2 = await mgr2.spawn(_req(cwd))
    assert s1.status == "running" and s2.status == "running"
    with pytest.raises(OverflowError):
        await mgr2.spawn(_req(cwd))


@pytest.mark.asyncio
async def test_backpressure_releases_after_kill(repo, bus, fake_psutil, platform_dir, cwd):
    runner = FakeRunner(fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    mgr2 = StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=1,
                          allowed_roots=roots)
    s1 = await mgr2.spawn(_req(cwd))
    with pytest.raises(OverflowError):
        await mgr2.spawn(_req(cwd))
    await mgr2.kill(s1.id, reason="user")
    s2 = await mgr2.spawn(_req(cwd))
    assert s2.status == "running"


@pytest.mark.asyncio
async def test_crash_recovery_reconciles_dead_pids(repo, bus, fake_psutil, platform_dir, cwd):
    """Insert a 'running' row whose pid is dead; crash_recovery transitions it."""
    runner = FakeRunner(fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    mgr2 = StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=3,
                          allowed_roots=roots)
    seed = Station(id="A" * 26, task_id="T-x", project_id="P-x", project_name="X",
                   model="sonnet", pid=99999, status="running", autonomy="careful",
                   cwd=cwd, started_at=_utcnow_iso(), last_heartbeat=_utcnow_iso())
    repo.insert_pending(seed, idempotency_key=None)
    repo.update_running(seed.id, 99999)  # pid not in fake_psutil._live_pids → dead
    n = await mgr2.crash_recovery()
    assert n >= 1
    row = repo.fetch(seed.id)
    assert row["status"] == "failed"
    assert row["exit_code"] == -1
    assert any(e["station_id"] == seed.id for e in bus.by_type("station.failed"))


@pytest.mark.asyncio
async def test_race_safety_concurrent_spawn_writes(repo, bus, fake_psutil, platform_dir, cwd):
    """Spawn many stations concurrently — every row must commit, none lost."""
    runner = FakeRunner(fake_psutil=fake_psutil)
    roots = (str(platform_dir),) + DEFAULT_ALLOWED_ROOTS
    mgr2 = StationManager(repo=repo, bus=bus, runner=runner,
                          psutil_mod=fake_psutil, max_concurrent=20,
                          allowed_roots=roots)
    stations = await asyncio.gather(*[mgr2.spawn(_req(cwd, task_id=f"T-{i}"))
                                      for i in range(10)])
    ids = {s.id for s in stations}
    assert len(ids) == 10  # all unique
    with repo.engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM agents WHERE status='running'")).scalar()
    assert cnt == 10


@pytest.mark.asyncio
async def test_shutdown_all_kills_concurrently(mgr, repo, bus, cwd):
    """shutdown_all kills all running stations concurrently."""
    s1 = await mgr.spawn(_req(cwd, task_id="T-1"))
    s2 = await mgr.spawn(_req(cwd, task_id="T-2"))
    s3 = await mgr.spawn(_req(cwd, task_id="T-3"))
    await mgr.shutdown_all(timeout=1.0)
    for s in (s1, s2, s3):
        row = repo.fetch(s.id)
        assert row["status"] == "killed"


def test_is_allowed_cwd_helper(tmp_path):
    assert is_allowed_cwd(str(tmp_path), allowed_roots=(str(tmp_path),)) is True
    assert is_allowed_cwd("/etc", allowed_roots=(str(tmp_path),)) is False
    assert is_allowed_cwd(str(tmp_path / "sub"), allowed_roots=(str(tmp_path),)) is True

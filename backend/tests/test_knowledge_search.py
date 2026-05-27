"""Tests for the new semantic/cross-project/people-graph endpoints in knowledge_search router."""
import json
import subprocess
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

_PATCH_TARGET = "app.routers.knowledge_search._get_search_module"

# ---------------------------------------------------------------------------
# Fake search module returned by _get_search_module
# ---------------------------------------------------------------------------

FAKE_SEARCH_RESULTS = [
    {"gid": "gid-001", "title": "Alpha Protocol", "score": 0.95, "mode": "fts"},
    {"gid": "gid-002", "title": "Beta Process", "score": 0.88, "mode": "semantic"},
]

FAKE_CROSS_PROJECT_RESULTS = [
    {"gid": "gid-001", "title": "Alpha Protocol", "projects": ["proj-a", "proj-b"], "score": 0.9},
    {"gid": "gid-003", "title": "Gamma Entity", "projects": ["proj-c"], "score": 0.7},
]

FAKE_PEOPLE_GRAPH = [
    {"gid": "person-001", "name": "Alice", "projects": ["proj-a"], "connections": 5},
    {"gid": "person-002", "name": "Bob", "projects": ["proj-a", "proj-b"], "connections": 3},
]


def _make_fake_search_module():
    """Create a mock module with search(), cross_project_search(), get_people_graph()."""
    mod = MagicMock()
    mod.search = MagicMock(return_value=FAKE_SEARCH_RESULTS)
    mod.cross_project_search = MagicMock(return_value=FAKE_CROSS_PROJECT_RESULTS)
    mod.get_people_graph = MagicMock(return_value=FAKE_PEOPLE_GRAPH)
    return mod


def _make_test_app() -> FastAPI:
    """Lightweight FastAPI app with only the knowledge_search router — no lifespan overhead."""
    app = FastAPI()
    from app.routers.knowledge_search import router
    app.include_router(router)
    return app


def _client_with(mock_return):
    """Context manager: patch _get_search_module and yield a TestClient.

    Also clears the module-level semantic cache to avoid cross-test pollution.
    """

    class _Ctx:
        def __enter__(self_ctx):
            # Clear the semantic result cache so tests are isolated
            import app.routers.knowledge_search as _ks
            _ks._semantic_cache.clear()

            self_ctx._patcher = patch(_PATCH_TARGET, return_value=mock_return)
            self_ctx._patcher.start()
            self_ctx._app = _make_test_app()
            self_ctx._tc = TestClient(self_ctx._app, raise_server_exceptions=False)
            self_ctx._tc.__enter__()
            return self_ctx._tc

        def __exit__(self_ctx, *exc):
            self_ctx._tc.__exit__(*exc)
            self_ctx._patcher.stop()

    return _Ctx()


# ---------------------------------------------------------------------------
# GET /api/knowledge/semantic
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    def test_returns_items_with_mode(self):
        with _client_with(_make_fake_search_module()) as c:
            resp = c.get("/api/knowledge/semantic?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert data["mode"] == "semantic_rrf"
            assert data["total"] == len(FAKE_SEARCH_RESULTS)
            assert len(data["items"]) == len(FAKE_SEARCH_RESULTS)

    def test_passes_query_params(self):
        """Verify that query, project, and limit are forwarded to search()."""
        fake_mod = _make_fake_search_module()
        with _client_with(fake_mod) as c:
            c.get("/api/knowledge/semantic?q=hello&project=proj-a&limit=5")
            fake_mod.search.assert_called_once_with("hello", project="proj-a", limit=5)

    def test_requires_query(self):
        with _client_with(_make_fake_search_module()) as c:
            resp = c.get("/api/knowledge/semantic")
            assert resp.status_code == 422  # validation error — q is required

    def test_module_unavailable(self):
        with _client_with(None) as c:
            resp = c.get("/api/knowledge/semantic?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert "error" in data

    def test_search_exception_handled(self):
        """If search() raises, the endpoint returns an error gracefully."""
        failing_mod = MagicMock()
        failing_mod.search = MagicMock(side_effect=RuntimeError("search failed"))
        with _client_with(failing_mod) as c:
            resp = c.get("/api/knowledge/semantic?q=boom")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/knowledge/cross-project
# ---------------------------------------------------------------------------

class TestCrossProjectSearch:
    def test_returns_items_with_projects(self):
        with _client_with(_make_fake_search_module()) as c:
            resp = c.get("/api/knowledge/cross-project?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert data["total"] == len(FAKE_CROSS_PROJECT_RESULTS)
            for item in data["items"]:
                assert "projects" in item

    def test_requires_query(self):
        with _client_with(_make_fake_search_module()) as c:
            resp = c.get("/api/knowledge/cross-project")
            assert resp.status_code == 422

    def test_module_unavailable(self):
        with _client_with(None) as c:
            resp = c.get("/api/knowledge/cross-project?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert "error" in data

    def test_passes_limit(self):
        fake_mod = _make_fake_search_module()
        with _client_with(fake_mod) as c:
            c.get("/api/knowledge/cross-project?q=hello&limit=15")
            fake_mod.cross_project_search.assert_called_once_with("hello", limit=15)

    def test_exception_handled(self):
        failing_mod = MagicMock()
        failing_mod.cross_project_search = MagicMock(side_effect=ValueError("oops"))
        with _client_with(failing_mod) as c:
            resp = c.get("/api/knowledge/cross-project?q=boom")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/knowledge/people-graph
# ---------------------------------------------------------------------------
# The people_graph endpoint queries the knowledge.db directly via
# _get_knowledge_db() (raw SQL against global_entities / project_entity_links /
# cross_project_connections). The tests therefore seed an in-memory sqlite
# fixture and patch _get_knowledge_db to return it.

import sqlite3 as _sqlite3


class _FakeConn:
    """Thin sqlite3.Connection wrapper that mimics the _ROConn surface
    used by the people_graph endpoint: ``execute(sql, params).fetchall()``
    / ``fetchone()`` and ``close()``."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def _seed_people_db(rows):
    """Build an in-memory sqlite with the minimal people-graph schema and
    seed it with the provided person rows. Each row is a tuple of
    ``(gid, canonical_name, importance_score, projects, connections)``
    where ``projects`` is a list of project_slug strings and ``connections``
    is the desired count of cross_project_connections rows for that gid."""
    conn = _sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(
        """CREATE TABLE global_entities (
            gid TEXT PRIMARY KEY,
            canonical_name TEXT,
            type TEXT,
            importance_score REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE project_entity_links (
            gid TEXT,
            project_slug TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cross_project_connections (
            source_gid TEXT,
            target_gid TEXT
        )"""
    )
    for gid, name, importance, projects, connections in rows:
        conn.execute(
            "INSERT INTO global_entities (gid, canonical_name, type, importance_score) VALUES (?, ?, 'person', ?)",
            (gid, name, importance),
        )
        for slug in projects:
            conn.execute(
                "INSERT INTO project_entity_links (gid, project_slug) VALUES (?, ?)",
                (gid, slug),
            )
        for i in range(connections):
            conn.execute(
                "INSERT INTO cross_project_connections (source_gid, target_gid) VALUES (?, ?)",
                (gid, f"other-{gid}-{i}"),
            )
    conn.commit()
    return conn


def _people_client(fake_conn_or_none):
    """Patch _get_knowledge_db to return ``fake_conn_or_none`` (None simulates
    a missing knowledge.db) and yield a TestClient on a lightweight app."""

    class _Ctx:
        def __enter__(self_ctx):
            self_ctx._patcher = patch(
                "app.routers.knowledge_search._get_knowledge_db",
                return_value=fake_conn_or_none,
            )
            self_ctx._patcher.start()
            self_ctx._app = _make_test_app()
            self_ctx._tc = TestClient(self_ctx._app, raise_server_exceptions=False)
            self_ctx._tc.__enter__()
            return self_ctx._tc

        def __exit__(self_ctx, *exc):
            self_ctx._tc.__exit__(*exc)
            self_ctx._patcher.stop()

    return _Ctx()


class TestPeopleGraph:
    def test_returns_items(self):
        """Seeded DB with 2 valid person rows should return 2 items."""
        # Names must satisfy _is_likely_person (2-4 capitalized words, 5-40 chars,
        # no noise words). "Alice Anderson" / "Bob Brown" pass the heuristic.
        seed = [
            ("person-001", "Alice Anderson", 0.9, ["proj-a"], 5),
            ("person-002", "Bob Brown", 0.7, ["proj-a", "proj-b"], 3),
        ]
        raw = _seed_people_db(seed)
        with _people_client(_FakeConn(raw)) as c:
            resp = c.get("/api/knowledge/people-graph")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert data["total"] == 2
            assert len(data["items"]) == 2
            names = {item["canonical_name"] for item in data["items"]}
            assert names == {"Alice Anderson", "Bob Brown"}

    def test_module_unavailable(self):
        """When _get_knowledge_db returns None (no knowledge.db), endpoint
        returns an empty payload with total=0 (no error key in this branch)."""
        with _people_client(None) as c:
            resp = c.get("/api/knowledge/people-graph")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["total"] == 0

    def test_exception_handled(self):
        """If the underlying execute() raises, the endpoint surfaces an error
        key and returns an empty payload (does not 500)."""
        bad = MagicMock()
        bad.execute = MagicMock(side_effect=RuntimeError("db locked"))
        bad.close = MagicMock()
        with _people_client(bad) as c:
            resp = c.get("/api/knowledge/people-graph")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/knowledge/media
# ---------------------------------------------------------------------------

_VENV_PYTHON_PATCH = "app.routers.knowledge_search._MEDIA_MEMORY_VENV_PYTHON"
_SEARCH_SCRIPT_PATCH = "app.routers.knowledge_search._MEDIA_MEMORY_SEARCH_SCRIPT"
_SUBPROCESS_RUN_PATCH = "subprocess.run"

FAKE_MEDIA_RESULTS = [
    {
        "id": "media-001",
        "description": "Architecture diagram",
        "filename": "arch.png",
        "original_path": "/tmp/arch.png",
        "asset_path": "/assets/arch.png",
        "type": "image",
        "source": "upload",
        "tags": '["architecture", "diagram"]',
        "timestamp": "2026-04-12T10:00:00Z",
        "semantic_distance": 0.25,
    },
]


def _make_media_test_app() -> FastAPI:
    """Lightweight FastAPI app with only the knowledge_search router for media tests."""
    app = FastAPI()
    from app.routers.knowledge_search import router
    app.include_router(router)
    return app


def _make_existing_path():
    """Return a MagicMock Path that reports exists() == True."""
    p = MagicMock()
    p.exists.return_value = True
    p.__str__ = lambda self: "/fake/path"
    p.parent = MagicMock()
    p.parent.__str__ = lambda self: "/fake"
    return p


def _make_missing_path():
    """Return a MagicMock Path that reports exists() == False."""
    p = MagicMock()
    p.exists.return_value = False
    p.__str__ = lambda self: "/missing/path"
    return p


class TestMediaSearch:
    def test_returns_items_when_available(self):
        """Successful subprocess returns parsed media items."""
        import app.routers.knowledge_search as _ks
        _ks._media_cache.clear()

        proc_result = MagicMock()
        proc_result.returncode = 0
        proc_result.stdout = json.dumps(FAKE_MEDIA_RESULTS)

        with (
            patch(_VENV_PYTHON_PATCH, _make_existing_path()),
            patch(_SEARCH_SCRIPT_PATCH, _make_existing_path()),
            patch(_SUBPROCESS_RUN_PATCH, return_value=proc_result),
        ):
            app = _make_media_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/knowledge/media?q=architecture")
                assert resp.status_code == 200
                data = resp.json()
                assert data["available"] is True
                assert data["total"] == 1
                assert len(data["items"]) == 1
                item = data["items"][0]
                assert item["id"] == "media-001"
                assert item["media_type"] == "image"
                assert isinstance(item["tags"], list)

    def test_returns_available_false_when_venv_missing(self):
        """When the media-memory venv doesn't exist, available should be False."""
        import app.routers.knowledge_search as _ks
        _ks._media_cache.clear()

        with (
            patch(_VENV_PYTHON_PATCH, _make_missing_path()),
            patch(_SEARCH_SCRIPT_PATCH, _make_existing_path()),
        ):
            app = _make_media_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/knowledge/media?q=test")
                assert resp.status_code == 200
                data = resp.json()
                assert data["available"] is False
                assert data["items"] == []

    def test_requires_query_param(self):
        """Missing q parameter should return 422."""
        import app.routers.knowledge_search as _ks
        _ks._media_cache.clear()

        with (
            patch(_VENV_PYTHON_PATCH, _make_existing_path()),
            patch(_SEARCH_SCRIPT_PATCH, _make_existing_path()),
        ):
            app = _make_media_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/knowledge/media")
                assert resp.status_code == 422

    def test_handles_subprocess_timeout(self):
        """TimeoutExpired should be caught and return a graceful error."""
        import app.routers.knowledge_search as _ks
        _ks._media_cache.clear()

        with (
            patch(_VENV_PYTHON_PATCH, _make_existing_path()),
            patch(_SEARCH_SCRIPT_PATCH, _make_existing_path()),
            patch(
                _SUBPROCESS_RUN_PATCH,
                side_effect=subprocess.TimeoutExpired(cmd="search", timeout=30),
            ),
        ):
            app = _make_media_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/knowledge/media?q=slow")
                assert resp.status_code == 200
                data = resp.json()
                assert data["items"] == []
                assert "error" in data
                assert "timed out" in data["error"].lower()

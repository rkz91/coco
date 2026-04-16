"""Tests for the attention router (app.routers.attention)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

_PATCH_TARGET = "app.routers.attention.attention_tracker"

# ---------------------------------------------------------------------------
# Fake data returned by the mocked attention_tracker
# ---------------------------------------------------------------------------

FAKE_SCORES = [
    {"project_slug": "alpha", "score": 4.2, "view_count": 10, "last_viewed_at": "2026-04-12T10:00:00Z"},
    {"project_slug": "beta", "score": 1.1, "view_count": 3, "last_viewed_at": "2026-04-10T08:00:00Z"},
]

FAKE_GAPS = [
    {"project_slug": "gamma", "score": 0.0, "view_count": 0, "last_viewed_at": None},
]

FAKE_VIEW_RESULT = {
    "project_slug": "alpha",
    "source": "knowledge",
    "viewed_at": "2026-04-13T12:00:00Z",
}


def _make_mock_tracker():
    """Create a mock attention_tracker with get_all_scores, get_attention_gaps, record_view."""
    tracker = MagicMock()
    tracker.get_all_scores = MagicMock(return_value=FAKE_SCORES)
    tracker.get_attention_gaps = MagicMock(return_value=FAKE_GAPS)
    tracker.record_view = MagicMock(return_value=FAKE_VIEW_RESULT)
    return tracker


def _make_test_app() -> FastAPI:
    """Lightweight FastAPI app with only the attention router."""
    app = FastAPI()
    from app.routers.attention import router
    app.include_router(router)
    return app


@pytest.fixture()
def client():
    """TestClient with attention_tracker patched."""
    mock_tracker = _make_mock_tracker()
    with patch(_PATCH_TARGET, mock_tracker):
        app = _make_test_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture()
def mock_tracker():
    """Standalone mock tracker for call-assertion tests."""
    return _make_mock_tracker()


# ---------------------------------------------------------------------------
# GET /api/attention/scores
# ---------------------------------------------------------------------------

class TestAttentionScores:
    def test_returns_list(self, client):
        resp = client.get("/api/attention/scores")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(FAKE_SCORES)
        assert len(data["items"]) == len(FAKE_SCORES)


# ---------------------------------------------------------------------------
# GET /api/attention/gaps
# ---------------------------------------------------------------------------

class TestAttentionGaps:
    def test_returns_list_with_days_param(self, client):
        resp = client.get("/api/attention/gaps?days=14")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(FAKE_GAPS)
        assert len(data["items"]) == len(FAKE_GAPS)

    def test_passes_days_to_tracker(self):
        mock_tracker = _make_mock_tracker()
        with patch(_PATCH_TARGET, mock_tracker):
            app = _make_test_app()
            with TestClient(app, raise_server_exceptions=False) as c:
                c.get("/api/attention/gaps?days=30")
                mock_tracker.get_attention_gaps.assert_called_once_with(days=30)


# ---------------------------------------------------------------------------
# POST /api/attention/view
# ---------------------------------------------------------------------------

class TestLogViewEvent:
    def test_accepts_post_and_returns_success(self, client):
        resp = client.post(
            "/api/attention/view",
            json={"project_slug": "alpha", "source": "knowledge"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_slug"] == "alpha"
        assert "viewed_at" in data

    def test_rejects_missing_project_slug(self, client):
        resp = client.post(
            "/api/attention/view",
            json={"source": "knowledge"},
        )
        assert resp.status_code == 422  # validation error — project_slug is required

"""Wave 0.1 write-path regression tests (Track 0 foundation remediation).

These assert that rows ACTUALLY LAND — the class of bug the audit found across
the write plane (success-shaped responses that persist nothing because an
exception was swallowed or a column/CHECK mismatched).

Covers:
  #1  cost_ledger source vocabulary (widened CHECK accepts the real writers)
  #2  auto_classifier persistence (upsert kwargs) + content classify idempotency
  #3  content-to-action staging + approve (staged_actions column alignment)
  #11 chat SDK path records cost once, not twice
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.db.session import get_db


def _count(table: str, where: str = "", params: tuple = ()) -> int:
    with get_db() as db:
        return db.exec_driver_sql(
            f"SELECT COUNT(*) AS c FROM {table} {where}", params
        ).fetchone()._mapping["c"]


def _seed_hub_content(cid: str, body: str, title: str = "Note") -> None:
    with get_db() as db:
        db.exec_driver_sql(
            "INSERT INTO hub_content (id, title, raw_text) VALUES (?, ?, ?)",
            (cid, title, body),
        )


# ---------------------------------------------------------------------------
# #2 — auto_classifier persistence
# ---------------------------------------------------------------------------

def test_apply_classification_persists_row(fresh_db):
    from app.services import auto_classifier as ac
    ac._apply_classification("hub-1", "proj-1", 0.91, "looks like proj-1", auto=True)
    assert _count("content_classifications", "WHERE hub_content_id = ?", ("hub-1",)) == 1


def test_save_suggestion_persists_row(fresh_db):
    from app.services import auto_classifier as ac
    ac._save_suggestion("hub-2", "proj-2", 0.66, "maybe proj-2")
    assert _count("content_classifications", "WHERE hub_content_id = ?", ("hub-2",)) == 1


def test_apply_classification_is_idempotent_on_hub_content_id(fresh_db):
    from app.services import auto_classifier as ac
    ac._apply_classification("hub-3", "proj-a", 0.5, "first", auto=True)
    ac._apply_classification("hub-3", "proj-b", 0.9, "second", auto=True)
    # upsert on hub_content_id -> still one row, updated in place
    assert _count("content_classifications", "WHERE hub_content_id = ?", ("hub-3",)) == 1
    with get_db() as db:
        row = db.exec_driver_sql(
            "SELECT classified_project_id FROM content_classifications WHERE hub_content_id = ?",
            ("hub-3",),
        ).fetchone()
    assert row._mapping["classified_project_id"] == "proj-b"


# ---------------------------------------------------------------------------
# #2b — content router classify/dismiss idempotency (conflict target fix)
# ---------------------------------------------------------------------------

def test_classify_content_endpoint_idempotent(fresh_db):
    from app.routers.content import classify_content, ClassifyContentBody
    _seed_hub_content("c-1", "TODO: nothing here")
    classify_content("c-1", ClassifyContentBody(project_id="p1"))
    # Second classify of the SAME content must update in place, not 500.
    classify_content("c-1", ClassifyContentBody(project_id="p2"))
    assert _count("content_classifications", "WHERE hub_content_id = ?", ("c-1",)) == 1


# ---------------------------------------------------------------------------
# #3 — content-to-action staging + approve
# ---------------------------------------------------------------------------

def test_process_content_stages_action(fresh_db):
    from app.services import action_pipeline as ap
    _seed_hub_content("c-2", "Meeting recap.\nTODO: send the contract to Aude\nThanks")
    staged = ap.process_content("c-2", mode="regex")
    assert len(staged) >= 1
    assert _count("staged_actions", "WHERE content_id = ?", ("c-2",)) >= 1


def test_approve_action_creates_todo(fresh_db):
    from app.services import action_pipeline as ap
    _seed_hub_content("c-3", "TODO: file the report")
    staged = ap.process_content("c-3", mode="regex")
    action_id = staged[0]["id"]
    result = ap.approve_action(action_id)
    assert result is not None and result["status"] == "approved"
    assert result.get("created_todo_id")
    with get_db() as db:
        row = db.exec_driver_sql(
            "SELECT status, created_todo_id FROM staged_actions WHERE id = ?",
            (action_id,),
        ).fetchone()
    assert row._mapping["status"] == "approved"
    assert row._mapping["created_todo_id"]


# ---------------------------------------------------------------------------
# #1 — cost_ledger source vocabulary (widened CHECK)
# ---------------------------------------------------------------------------

REAL_SOURCES = ["station", "chat", "think", "kh_pipeline", "agent", "classifier", "brain", "api_token"]


@pytest.mark.parametrize("source", REAL_SOURCES)
def test_cost_ledger_accepts_real_sources(fresh_db, source):
    from app.services.agent_sdk_client import record_sdk_cost
    record_sdk_cost(model="claude-haiku-4-5-20251001", input_tokens=10, output_tokens=5, source=source)
    assert _count("cost_ledger", "WHERE source = ?", (source,)) == 1


def test_cost_ledger_rejects_unknown_source(fresh_db):
    """The widened CHECK still rejects garbage (proves it is enforced, not absent)."""
    import sqlalchemy
    from app.db.tables import cost_ledger
    with pytest.raises((sqlalchemy.exc.IntegrityError, sqlalchemy.exc.OperationalError)):
        with get_db() as db:
            db.execute(
                cost_ledger.insert().values(
                    id=uuid.uuid4().hex, model="m", input_tokens=1, output_tokens=1,
                    cost_usd=0.0, source="totally-bogus-source", created_at="2026-06-01",
                )
            )


# ---------------------------------------------------------------------------
# #11 — chat SDK path records cost exactly once
# ---------------------------------------------------------------------------

def test_sdk_chat_generator_does_not_record_cost_itself(fresh_db, monkeypatch):
    """stream_chat already records via _record_dual; the generator must NOT
    record again (that was the 2x cost-inflation bug)."""
    import app.routers.chat as chat
    from app.services import agent_sdk_client as sdk

    calls = {"n": 0}
    monkeypatch.setattr(sdk, "record_sdk_cost", lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    # Isolate from persistence side-effects.
    monkeypatch.setattr(chat, "_save_message", lambda *a, **k: None)
    monkeypatch.setattr(chat, "_update_session_after_message", lambda *a, **k: None)

    async def fake_stream(*a, **k):
        yield {"type": "token", "content": "hi"}
        yield {"type": "usage", "input_tokens": 12, "output_tokens": 7, "model": "claude-sonnet-4-6"}
        yield {"type": "done", "content": "hi"}

    monkeypatch.setattr(sdk.agent_sdk, "stream_chat", fake_stream)

    async def drive():
        async for _ in chat._sdk_chat_event_generator("hello", "sonnet", "sys", session_id=None):
            pass

    asyncio.run(drive())
    # The generator must not call record_sdk_cost; stream_chat owns recording.
    assert calls["n"] == 0

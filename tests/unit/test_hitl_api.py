"""
Unit tests for HITL API endpoints:
  GET  /api/sessions/{id}/hitl
  POST /api/sessions/{id}/answer
  POST /api/sessions/{id}/resume
  hitl_enabled round-trip in GET /api/sessions/{id} and GET /api/sessions
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _init_store(tmp_path: Path):
    from ai_research_engineer.server.run_store import RunStore

    db = tmp_path / "test.db"
    RunStore.init(db_path=db)
    RunStore.DATA_DIR = tmp_path
    return RunStore


def _make_session(store, session_id: str = "sess-001", status: str = "running", hitl_enabled: int = 1) -> str:
    store.save_session(
        {
            "session_id": session_id,
            "status": status,
            "title": "Test",
            "topic": "test topic",
            "agent_type": "adk",
            "hitl_enabled": hitl_enabled,
            "started_at": datetime.now().isoformat(),
        }
    )
    return session_id


@pytest.fixture()
def client(tmp_path):
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    _original_data_dir = RunStore.DATA_DIR
    store = _init_store(tmp_path)

    yield TestClient(app, raise_server_exceptions=True), store, tmp_path

    RunStore.DATA_DIR = _original_data_dir


# ---------------------------------------------------------------------------
# GET /hitl
# ---------------------------------------------------------------------------


class TestGetHITL:
    def test_404_when_session_unknown(self, client):
        c, _, _ = client
        r = c.get("/api/sessions/no-such/hitl")
        assert r.status_code == 404

    def test_no_pending_request(self, client):
        c, store, _ = client
        sid = _make_session(store)
        r = c.get(f"/api/sessions/{sid}/hitl")
        assert r.status_code == 200
        assert r.json()["pending"] is None

    def test_returns_pending_request(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-pend")
        from ai_research_engineer.server.run_store import RunStore
        RunStore.create_hitl_request(sid, "gate_plan", "Approve?")

        r = c.get(f"/api/sessions/{sid}/hitl")
        assert r.status_code == 200
        body = r.json()
        assert body["pending"] is not None
        assert body["pending"]["status"] == "pending"
        assert body["pending"]["question"] == "Approve?"


# ---------------------------------------------------------------------------
# POST /answer
# ---------------------------------------------------------------------------


class TestAnswerHITL:
    def test_404_when_session_unknown(self, client):
        c, _, _ = client
        r = c.post("/api/sessions/no-such/answer", json={"answer": "approve"})
        assert r.status_code == 404

    def test_409_when_no_pending_request(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-no-req")
        r = c.post(f"/api/sessions/{sid}/answer", json={"answer": "approve"})
        assert r.status_code == 409

    def test_422_when_answer_missing(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-no-ans")
        from ai_research_engineer.server.run_store import RunStore
        RunStore.create_hitl_request(sid, "gate_plan", "Q?")
        r = c.post(f"/api/sessions/{sid}/answer", json={})
        assert r.status_code == 422

    def test_stores_answer_and_resumes(self, client, monkeypatch):
        from ai_research_engineer.server import app as app_mod
        from ai_research_engineer.server.run_store import RunStore

        c, store, _ = client
        sid = _make_session(store, "sess-ans")
        RunStore.create_hitl_request(sid, "gate_plan", "Q?")

        # Patch _run_agent_resume so it does not actually run
        resume_calls = []

        async def fake_resume(*args, **kwargs):
            resume_calls.append(args)

        monkeypatch.setattr(app_mod, "_run_agent_resume", fake_resume)

        r = c.post(f"/api/sessions/{sid}/answer", json={"answer": "approve"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "resuming"

        # Answer must be recorded
        pending = RunStore.get_pending_hitl(sid)
        assert pending is None  # answered → no longer pending

    def test_409_on_double_answer(self, client, monkeypatch):
        from ai_research_engineer.server import app as app_mod
        from ai_research_engineer.server.run_store import RunStore

        c, store, _ = client
        sid = _make_session(store, "sess-dbl")
        req = RunStore.create_hitl_request(sid, "gate_plan", "Q?")

        # First answer it directly
        RunStore.answer_hitl_request(req["request_id"], "approve")

        r = c.post(f"/api/sessions/{sid}/answer", json={"answer": "reject"})
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /resume
# ---------------------------------------------------------------------------


class TestResumeSession:
    def test_404_when_session_unknown(self, client):
        c, _, _ = client
        r = c.post("/api/sessions/no-such/resume")
        assert r.status_code == 404

    def test_409_when_session_running(self, client):
        from ai_research_engineer.server.app import _active_sessions

        c, store, _ = client
        import asyncio
        sid = _make_session(store, "sess-running")
        # Fake an active session
        import asyncio
        _active_sessions[sid] = asyncio.Queue()
        try:
            r = c.post(f"/api/sessions/{sid}/resume")
            assert r.status_code == 409
        finally:
            _active_sessions.pop(sid, None)

    def test_409_when_no_checkpoint(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-no-cp", status="awaiting_input")
        r = c.post(f"/api/sessions/{sid}/resume")
        assert r.status_code == 409

    def test_resumes_with_checkpoint(self, client, monkeypatch):
        import json
        from ai_research_engineer.server import app as app_mod
        from ai_research_engineer.server.run_store import RunStore

        c, store, _ = client
        sid = _make_session(store, "sess-cp", status="awaiting_input")
        RunStore.save_checkpoint(sid, "gate_plan", json.dumps({"key": "val"}))

        resume_calls = []

        async def fake_resume(*args, **kwargs):
            resume_calls.append(args)

        monkeypatch.setattr(app_mod, "_run_agent_resume", fake_resume)

        r = c.post(f"/api/sessions/{sid}/resume")
        assert r.status_code == 200
        assert r.json()["status"] == "resuming"


# ---------------------------------------------------------------------------
# hitl_enabled round-trip
# ---------------------------------------------------------------------------


class TestHITLEnabledRoundTrip:
    def test_hitl_enabled_in_get_session(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-he", hitl_enabled=1)
        r = c.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        body = r.json()
        assert "hitl_enabled" in body
        assert body["hitl_enabled"] in (1, True)

    def test_hitl_disabled_in_get_session(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-hd", hitl_enabled=0)
        r = c.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        body = r.json()
        assert "hitl_enabled" in body
        assert body["hitl_enabled"] in (0, False)

    def test_hitl_enabled_in_list_sessions(self, client):
        c, store, _ = client
        _make_session(store, "sess-list-he", hitl_enabled=1)
        r = c.get("/api/sessions")
        assert r.status_code == 200
        sessions = r.json()
        target = next(s for s in sessions if s["session_id"] == "sess-list-he")
        assert target.get("hitl_enabled") in (1, True)

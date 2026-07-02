"""Unit tests for RunStore usage accounting and the /usage endpoint."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_store(tmp_path: Path):
    from ai_research_engineer.server.run_store import RunStore

    db = tmp_path / "test.db"
    RunStore.init(db_path=db)
    return RunStore


def _make_session(store, session_id: str = "test-sess-1"):
    from datetime import datetime

    store.save_session(
        {
            "session_id": session_id,
            "status": "running",
            "title": "Test",
            "topic": "test",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        }
    )
    return session_id


# ---------------------------------------------------------------------------
# RunStore.add_usage / get_usage unit tests
# ---------------------------------------------------------------------------


class TestRunStoreUsage:
    def test_get_usage_empty_returns_zero_totals(self, tmp_path):
        store = _init_store(tmp_path)
        sid = _make_session(store)
        result = store.get_usage(sid)
        assert result["totals"]["input_tokens"] == 0
        assert result["totals"]["output_tokens"] == 0
        assert result["totals"]["cost_usd"] == 0
        assert result["by_model"] == []

    def test_add_and_get_single_row(self, tmp_path):
        store = _init_store(tmp_path)
        sid = _make_session(store)
        store.add_usage(
            session_id=sid,
            seq=1,
            input_tokens=1000,
            output_tokens=500,
            cached_input_tokens=200,
            model="claude-sonnet-4-6",
            engine="adk",
            cost_usd=0.0075,
        )
        result = store.get_usage(sid)
        assert result["totals"]["input_tokens"] == 1000
        assert result["totals"]["output_tokens"] == 500
        assert result["totals"]["cached_input_tokens"] == 200
        assert abs(result["totals"]["cost_usd"] - 0.0075) < 1e-9

    def test_totals_accumulate_across_events(self, tmp_path):
        store = _init_store(tmp_path)
        sid = _make_session(store)
        for i in range(3):
            store.add_usage(
                session_id=sid,
                seq=i + 1,
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-6",
                engine="adk",
                cost_usd=0.001,
            )
        result = store.get_usage(sid)
        assert result["totals"]["input_tokens"] == 300
        assert result["totals"]["output_tokens"] == 150
        assert abs(result["totals"]["cost_usd"] - 0.003) < 1e-9

    def test_by_model_breakdown(self, tmp_path):
        store = _init_store(tmp_path)
        sid = _make_session(store)
        store.add_usage(
            session_id=sid,
            seq=1,
            input_tokens=1000,
            output_tokens=200,
            model="claude-sonnet-4-6",
            engine="adk",
            cost_usd=0.006,
        )
        store.add_usage(
            session_id=sid,
            seq=2,
            input_tokens=500,
            output_tokens=100,
            model="gemini-2.5-pro",
            engine="adk",
            cost_usd=0.002,
        )
        result = store.get_usage(sid)
        models = {row["model"]: row for row in result["by_model"]}
        assert "claude-sonnet-4-6" in models
        assert "gemini-2.5-pro" in models
        assert models["claude-sonnet-4-6"]["input_tokens"] == 1000
        assert models["gemini-2.5-pro"]["output_tokens"] == 100

    def test_session_isolation(self, tmp_path):
        store = _init_store(tmp_path)
        sid_a = _make_session(store, "sess-a")
        sid_b = _make_session(store, "sess-b")
        store.add_usage(session_id=sid_a, seq=1, input_tokens=999, output_tokens=1, model="m", cost_usd=0.0)
        result_b = store.get_usage(sid_b)
        assert result_b["totals"]["input_tokens"] == 0

    def test_null_model_stored_and_returned(self, tmp_path):
        store = _init_store(tmp_path)
        sid = _make_session(store)
        store.add_usage(session_id=sid, seq=1, input_tokens=10, output_tokens=5, model=None, cost_usd=0.0)
        result = store.get_usage(sid)
        assert result["totals"]["input_tokens"] == 10
        # by_model will have a None-model entry
        assert len(result["by_model"]) == 1


# ---------------------------------------------------------------------------
# /api/sessions/{id}/usage endpoint via TestClient
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Spin up a TestClient with RunStore pointing at a temp DB."""
    import ai_research_engineer.server.run_store as rs_module
    from ai_research_engineer.server.run_store import _DB_PATH, RunStore  # noqa: F401

    db = tmp_path / "app_test.db"
    RunStore.init(db_path=db)
    # Monkeypatch the module-level _DB_PATH so the app uses the test DB
    monkeypatch.setattr(rs_module, "_DB_PATH", db)

    from ai_research_engineer.server.app import app

    return TestClient(app, raise_server_exceptions=True)


class TestUsageEndpoint:
    def test_404_for_unknown_session(self, client):
        resp = client.get("/api/sessions/no-such-session/usage")
        assert resp.status_code == 404

    def test_returns_zero_totals_for_new_session(self, client, tmp_path):
        from datetime import datetime

        from ai_research_engineer.server.run_store import RunStore

        sid = "ep-sess-1"
        RunStore.save_session(
            {
                "session_id": sid,
                "status": "completed",
                "title": "T",
                "topic": "t",
                "agent_type": "adk",
                "started_at": datetime.now().isoformat(),
            }
        )
        resp = client.get(f"/api/sessions/{sid}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert "totals" in body
        assert "by_model" in body
        assert body["totals"]["cost_usd"] == 0

    def test_returns_accumulated_usage(self, client, tmp_path):
        from datetime import datetime

        from ai_research_engineer.server.run_store import RunStore

        sid = "ep-sess-2"
        RunStore.save_session(
            {
                "session_id": sid,
                "status": "completed",
                "title": "T",
                "topic": "t",
                "agent_type": "adk",
                "started_at": datetime.now().isoformat(),
            }
        )
        RunStore.add_usage(
            session_id=sid, seq=1, input_tokens=2000, output_tokens=300, model="claude-sonnet-4-6", cost_usd=0.01
        )
        resp = client.get(f"/api/sessions/{sid}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["totals"]["input_tokens"] == 2000
        assert body["totals"]["output_tokens"] == 300
        assert len(body["by_model"]) == 1

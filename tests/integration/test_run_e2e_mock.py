"""
Mocked end-to-end smoke tests through the FastAPI server.

Uses FastAPI TestClient + monkeypatching AIEngineer.run_async to yield a canned
event stream — no real model, no network, no API keys.

What this guards
----------------
- POST /api/sessions creates a session and starts _run_agent as a background task.
- _run_agent constructs AIEngineer (caught by test_graph_construction.py) then calls
  run_async and iterates events.  Monkeypatching run_async here lets us drive the
  full server-side persistence path without any LLM.
- Asserts:
    * session reaches status "completed"
    * session_events rows exist with monotonically increasing seq
    * a usage row was persisted with a cost_usd value
    * GET /events returns the stored events
    * GET /tree and /usage return 200
- Negative case: if the engine raises immediately the session must end "failed",
  not stuck "running" — guards the "crash on start" path (e.g. NameError before
  any yield).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _init_store(tmp_path: Path):
    from ai_research_engineer.server.run_store import RunStore

    RunStore.init(db_path=tmp_path / "test.db")
    RunStore.DATA_DIR = tmp_path
    return RunStore


def _api_headers(app_token: str | None = None) -> dict:
    import os
    token = app_token or os.environ.get("API_TOKEN")
    if token:
        return {"X-API-Token": token, "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Canned event stream (no LLM)
# ---------------------------------------------------------------------------

CANNED_EVENTS: list[Dict[str, Any]] = [
    {
        "type": "message",
        "content": "Starting research on the topic.",
        "timestamp": "00:00:01.000",
        "is_thought": False,
    },
    {
        "type": "function_call",
        "name": "read_file",
        "arguments": {"path": "notes.txt"},
        "timestamp": "00:00:02.000",
    },
    {
        "type": "function_response",
        "name": "read_file",
        "response": "File contents here.",
        "timestamp": "00:00:02.100",
    },
    {
        "type": "usage",
        "usage": {
            "input_tokens": 100,
            "cached_input_tokens": 10,
            "output_tokens": 50,
        },
        "model": "gemini-2.0-flash",
        "timestamp": "00:00:03.000",
    },
    {
        "type": "message",
        "content": "Research complete.",
        "timestamp": "00:00:04.000",
        "is_thought": False,
    },
    {
        "type": "completed",
        "duration": 4.0,
        "total_events": 5,
        "files_created": [],
        "files_count": 0,
        "timestamp": "00:00:04.000",
    },
]


async def _canned_stream(*_args, **_kwargs) -> AsyncGenerator[Dict[str, Any], None]:
    """Replacement for AIEngineer.run_async — returns a canned async generator, no LLM.

    Must be a regular coroutine (not an async generator) so that
    `gen = await engineer.run_async(...)` works: await resolves the coroutine
    and returns the generator for the caller to iterate.
    """
    async def _gen() -> AsyncGenerator[Dict[str, Any], None]:
        for event in CANNED_EVENTS:
            yield event
            await asyncio.sleep(0)  # yield control so background task can progress

    return _gen()


async def _crashing_stream(*_args, **_kwargs) -> AsyncGenerator[Dict[str, Any], None]:
    """Simulates an engine that raises before yielding any events (e.g. NameError).

    Raises at await-time so the server's except block marks the session failed.
    """
    raise RuntimeError("Simulated crash at startup — no events emitted")


# ---------------------------------------------------------------------------
# Fixture: client with isolated DB + monkeypatched engine
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_client(tmp_path, monkeypatch):
    """
    TestClient with:
    - RunStore pointed at tmp_path (isolated SQLite)
    - AIEngineer.run_async replaced with canned stream
    """
    import ai_research_engineer.core.api as api_mod
    import ai_research_engineer.server.app as app_mod
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    original_data_dir = RunStore.DATA_DIR
    _init_store(tmp_path)
    app_mod._rate_buckets.clear()  # reset per-IP buckets so tests never hit 429

    # Patch run_async on the class so every instance uses the mock
    monkeypatch.setattr(api_mod.AIEngineer, "run_async", _canned_stream)

    yield TestClient(app, raise_server_exceptions=True)

    RunStore.DATA_DIR = original_data_dir


@pytest.fixture()
def crash_client(tmp_path, monkeypatch):
    """Same as mock_client but engine crashes before yielding."""
    import ai_research_engineer.core.api as api_mod
    import ai_research_engineer.server.app as app_mod
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    original_data_dir = RunStore.DATA_DIR
    _init_store(tmp_path)
    app_mod._rate_buckets.clear()  # reset per-IP buckets so tests never hit 429

    monkeypatch.setattr(api_mod.AIEngineer, "run_async", _crashing_stream)

    yield TestClient(app, raise_server_exceptions=True)

    RunStore.DATA_DIR = original_data_dir


# ---------------------------------------------------------------------------
# Helper: wait for session to leave "running" state
# ---------------------------------------------------------------------------

def _wait_for_terminal(client: TestClient, session_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/sessions/{session_id}", headers=_api_headers())
        assert r.status_code == 200
        data = r.json()
        if data.get("status") not in ("running", None):
            return data
        time.sleep(0.05)
    raise TimeoutError(f"Session {session_id} never left 'running' within {timeout}s")


# ---------------------------------------------------------------------------
# Happy-path end-to-end
# ---------------------------------------------------------------------------

class TestMockedRunE2E:

    def test_post_sessions_creates_session(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert "session_id" in body
        assert "display_id" in body

    def test_session_reaches_completed(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        final = _wait_for_terminal(mock_client, session_id)
        assert final["status"] == "completed", f"Expected 'completed', got: {final['status']}"

    def test_events_persisted_with_monotonic_seq(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        ev_r = mock_client.get(
            f"/api/sessions/{session_id}/events?after_seq=0",
            headers=_api_headers(),
        )
        assert ev_r.status_code == 200
        events = ev_r.json()
        assert len(events) > 0, "Expected at least one persisted event"

        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs), f"seq values not monotonically increasing: {seqs}"
        assert len(seqs) == len(set(seqs)), f"Duplicate seq values: {seqs}"

    def test_usage_row_persisted_with_cost(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        usage_r = mock_client.get(
            f"/api/sessions/{session_id}/usage",
            headers=_api_headers(),
        )
        assert usage_r.status_code == 200
        usage = usage_r.json()
        totals = usage.get("totals", {})
        # The canned stream emits a usage event with 100+50 tokens
        assert totals.get("input_tokens", 0) >= 0
        assert "cost_usd" in totals

    def test_get_events_returns_stored_events(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        ev_r = mock_client.get(
            f"/api/sessions/{session_id}/events?after_seq=0",
            headers=_api_headers(),
        )
        assert ev_r.status_code == 200
        types_seen = {e["type"] for e in ev_r.json()}
        assert "message" in types_seen
        assert "completed" in types_seen

    def test_get_tree_returns_200(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        tree_r = mock_client.get(
            f"/api/sessions/{session_id}/tree",
            headers=_api_headers(),
        )
        assert tree_r.status_code == 200

    def test_get_usage_returns_200(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        usage_r = mock_client.get(
            f"/api/sessions/{session_id}/usage",
            headers=_api_headers(),
        )
        assert usage_r.status_code == 200

    def test_canned_events_include_function_call(self, mock_client):
        r = mock_client.post(
            "/api/sessions",
            json={"topic": "test hypothesis", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(mock_client, session_id)

        ev_r = mock_client.get(
            f"/api/sessions/{session_id}/events?after_seq=0",
            headers=_api_headers(),
        )
        types_seen = {e["type"] for e in ev_r.json()}
        assert "function_call" in types_seen


# ---------------------------------------------------------------------------
# Negative case: crash before first event
# ---------------------------------------------------------------------------

class TestCrashOnStart:
    """
    Guards the 'crash on start' path: if the engine raises before yielding
    any events (e.g. NameError on the old broken import), the session must
    end in 'failed', never stuck in 'running'.
    """

    def test_session_ends_failed_not_running(self, crash_client):
        r = crash_client.post(
            "/api/sessions",
            json={"topic": "crashing run", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        assert r.status_code == 200
        session_id = r.json()["session_id"]
        final = _wait_for_terminal(crash_client, session_id)
        assert final["status"] == "failed", (
            f"Expected 'failed' after engine crash, got: {final['status']!r}"
        )

    def test_crash_emits_error_event(self, crash_client):
        r = crash_client.post(
            "/api/sessions",
            json={"topic": "crashing run", "agent_type": "adk", "domain": "aiml"},
            headers=_api_headers(),
        )
        session_id = r.json()["session_id"]
        _wait_for_terminal(crash_client, session_id)

        ev_r = crash_client.get(
            f"/api/sessions/{session_id}/events?after_seq=0",
            headers=_api_headers(),
        )
        assert ev_r.status_code == 200
        types_seen = {e["type"] for e in ev_r.json()}
        assert "error" in types_seen, f"Expected an error event, got types: {types_seen}"

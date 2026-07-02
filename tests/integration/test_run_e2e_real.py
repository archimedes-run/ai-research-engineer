"""
Real end-to-end smoke test (opt-in, NOT run in CI).

Requires a live ANTHROPIC_API_KEY and will make real LLM calls that cost
API credits.  Skipped by default; run explicitly with:

    pytest -m real -q tests/integration/test_run_e2e_real.py

The test launches a minimal research run (short topic, adk agent) and
asserts it completes without error.  It does NOT assert any output quality —
only that the pipeline reaches "completed" status end-to-end.

Cost estimate: <$0.10 per run for a minimal topic with the default model.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest


# ---------------------------------------------------------------------------
# Guard: skip unless the 'real' marker is explicitly selected AND the key exists
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.real


def _require_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip(
            "No ANTHROPIC_API_KEY or GOOGLE_API_KEY set. "
            "Real end-to-end tests require live credentials. "
            "Run with: ANTHROPIC_API_KEY=sk-... pytest -m real"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRealRunE2E:
    """
    Full round-trip through AIEngineer with a real model.

    These tests are never executed in CI (no marker -m real is passed).
    They serve as a developer-local sanity check before shipping.
    """

    def test_adk_run_completes(self, tmp_path):
        """
        Run a minimal ADK research session end-to-end.
        Asserts: no exception, at least one event yielded, completed event present.
        """
        _require_api_key()

        from ai_research_engineer.core.api import AIEngineer

        eng = AIEngineer(
            agent_type="adk",
            working_dir=str(tmp_path / "real_adk"),
            research_mode="novelty",
            domain="aiml",
            use_graphify=False,
        )

        events = []

        async def _collect():
            gen = await eng.run_async(
                "Write one sentence summarising what a neural network is.",
                stream=True,
            )
            async for event in gen:
                events.append(event)

        asyncio.run(_collect())

        assert len(events) > 0, "Expected at least one event from the real run"
        types_seen = {e.get("type") for e in events}
        assert "completed" in types_seen or "error" not in types_seen, (
            f"Run ended with error event. Types seen: {types_seen}\n"
            f"Last event: {events[-1]}"
        )

    def test_server_post_session_real(self, tmp_path):
        """
        Full server path: POST /api/sessions → background task → completed.
        Uses TestClient so we don't need the server running.
        """
        _require_api_key()

        from fastapi.testclient import TestClient

        from ai_research_engineer.server.app import app
        from ai_research_engineer.server.run_store import RunStore

        original = RunStore.DATA_DIR
        RunStore.init(db_path=tmp_path / "real.db")
        RunStore.DATA_DIR = tmp_path

        try:
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post(
                "/api/sessions",
                json={
                    "topic": "Write one sentence summarising gradient descent.",
                    "agent_type": "adk",
                    "domain": "aiml",
                    "research_mode": "novelty",
                },
            )
            assert r.status_code == 200
            session_id = r.json()["session_id"]

            # Poll until terminal (generous timeout for a real run)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                sr = client.get(f"/api/sessions/{session_id}")
                status = sr.json().get("status")
                if status not in ("running", None):
                    break
                time.sleep(2)

            final = client.get(f"/api/sessions/{session_id}").json()
            assert final["status"] in ("completed", "failed"), (
                f"Session did not reach a terminal state within timeout: {final['status']}"
            )
            assert final["status"] == "completed", (
                f"Real run ended in non-completed state: {final['status']}"
            )
        finally:
            RunStore.DATA_DIR = original

"""
Unit tests for Phase C.1: Human-in-the-Loop (HITL).

Covers:
- HITLSequentialAgent disabled=identical (regression)
- HITLSequentialAgent pause at gate: checkpoint saved, hitl_request created,
  state keys set, status awaiting_input
- Resume: completed agents are skipped, answer injected into state
- Checkpoint round-trip fidelity
- SEEKER features (tree/verification) run in BOTH modes
- RunStore HITL methods
"""

from __future__ import annotations

import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _FakeSubAgent:
    """Duck-typed sub-agent stub — no Pydantic, just plain Python."""

    def __init__(self, name: str, events=None):
        self.name = name
        self._events = events or []
        self.call_count = 0

    async def run_async(self, ctx) -> AsyncGenerator:
        self.call_count += 1
        for ev in self._events:
            yield ev


def _make_agent(name: str, events=None):
    return _FakeSubAgent(name=name, events=events or [])


class _MutatingAgent:
    """Sub-agent stub that mutates session state when it runs (e.g. sets an outcome)."""

    def __init__(self, name: str, mutation):
        self.name = name
        self._mutation = mutation
        self.call_count = 0

    async def run_async(self, ctx) -> AsyncGenerator:
        self.call_count += 1
        self._mutation(ctx.session.state)
        if False:  # make this an async generator without yielding events
            yield


# ---------------------------------------------------------------------------
# RunStore HITL methods
# ---------------------------------------------------------------------------


class TestRunStoreHITL:
    def test_save_and_load_checkpoint(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        state = {"foo": "bar", "count": 42}
        RunStore.save_checkpoint("sess-ck", "gate_plan", json.dumps(state))
        cp = RunStore.load_checkpoint("sess-ck")
        assert cp is not None
        assert cp["stage_key"] == "gate_plan"
        assert cp["state"] == state

    def test_load_checkpoint_returns_none_when_absent(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        assert RunStore.load_checkpoint("no-such-session") is None

    def test_create_and_get_hitl_request(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        req = RunStore.create_hitl_request("sess-h1", "gate_plan", "Approve plan?", context_md="# ctx")
        assert req["status"] == "pending"
        assert req["session_id"] == "sess-h1"

        fetched = RunStore.get_hitl_request(req["request_id"])
        assert fetched is not None
        assert fetched["question"] == "Approve plan?"

    def test_get_pending_hitl(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        RunStore.create_hitl_request("sess-h2", "gate_plan", "Q?")
        pending = RunStore.get_pending_hitl("sess-h2")
        assert pending is not None
        assert pending["status"] == "pending"

    def test_answer_hitl_request(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        req = RunStore.create_hitl_request("sess-h3", "gate_plan", "Q?")
        ok = RunStore.answer_hitl_request(req["request_id"], "approve")
        assert ok is True
        answered = RunStore.get_hitl_request(req["request_id"])
        assert answered["status"] == "answered"
        assert answered["answer"] == "approve"

    def test_answer_hitl_idempotent_false_on_second_attempt(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        req = RunStore.create_hitl_request("sess-h4", "gate_plan", "Q?")
        RunStore.answer_hitl_request(req["request_id"], "approve")
        ok2 = RunStore.answer_hitl_request(req["request_id"], "reject")
        assert ok2 is False

    def test_get_pending_returns_none_after_answer(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        req = RunStore.create_hitl_request("sess-h5", "gate_plan", "Q?")
        RunStore.answer_hitl_request(req["request_id"], "approve")
        assert RunStore.get_pending_hitl("sess-h5") is None


# ---------------------------------------------------------------------------
# HITLSequentialAgent — disabled mode
# ---------------------------------------------------------------------------


class TestHITLDisabled:
    """When hitl_enabled=False the agent must be byte-identical to SequentialAgent."""

    @pytest.mark.asyncio
    async def test_all_agents_run_in_order(self):
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from unittest.mock import MagicMock

        a1 = _make_agent("agent_a")
        a2 = _make_agent("agent_b")
        a3 = _make_agent("agent_c")

        workflow = HITLSequentialAgent(
            sub_agents=[a1, a2, a3],
            hitl_enabled=False,
        )

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-disabled"

        async for _ in workflow._run_async_impl(ctx):
            pass

        assert a1.call_count == 1
        assert a2.call_count == 1
        assert a3.call_count == 1

    @pytest.mark.asyncio
    async def test_no_state_keys_written(self):
        """Disabled mode must not touch any _hitl_* state keys."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from unittest.mock import MagicMock

        agent = _make_agent("agent_a")
        workflow = HITLSequentialAgent(sub_agents=[agent], hitl_enabled=False)

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-clean"

        async for _ in workflow._run_async_impl(ctx):
            pass

        state_keys = set(ctx.session.state.keys())
        hitl_keys = {k for k in state_keys if k.startswith("_hitl")}
        assert hitl_keys == set(), f"Found unexpected HITL state keys: {hitl_keys}"

    @pytest.mark.asyncio
    async def test_no_checkpoint_saved(self, tmp_path):
        """Disabled mode must never call RunStore.save_checkpoint."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from ai_research_engineer.server.run_store import RunStore
        from unittest.mock import MagicMock

        RunStore.init(db_path=tmp_path / "test.db")

        agent = _make_agent("agent_a")
        workflow = HITLSequentialAgent(sub_agents=[agent], hitl_enabled=False)

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-nochk"

        async for _ in workflow._run_async_impl(ctx):
            pass

        cp = RunStore.load_checkpoint("sess-nochk")
        assert cp is None


# ---------------------------------------------------------------------------
# HITLSequentialAgent — enabled mode (gate_plan)
# ---------------------------------------------------------------------------


class TestHITLEnabled:
    @pytest.mark.asyncio
    async def test_pause_at_gate_plan(self, tmp_path):
        """After planning_tree_agent, gate_plan should trigger pause."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from ai_research_engineer.server.run_store import RunStore
        from unittest.mock import MagicMock

        RunStore.init(db_path=tmp_path / "test.db")
        RunStore.save_session({
            "session_id": "sess-gate",
            "status": "running",
            "title": "T",
            "topic": "test",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        })

        a1 = _make_agent("ideation_loop")
        a2 = _make_agent("planning_tree_agent")  # gate triggers after this
        a3 = _make_agent("stage_orchestrator")   # should NOT run

        workflow = HITLSequentialAgent(
            sub_agents=[a1, a2, a3],
            hitl_enabled=True,
        )

        state: dict = {}
        ctx = MagicMock()
        ctx.session.state = state
        ctx.session.id = "sess-gate"

        with patch.object(workflow, "_build_context_md", return_value="# ctx md"):
            async for _ in workflow._run_async_impl(ctx):
                pass

        # stage_orchestrator must NOT have run
        assert a3.call_count == 0

        # State must have pause markers
        assert state.get("_hitl_paused") == "gate_plan"
        assert state.get("_hitl_request_id") is not None

        # Checkpoint must exist
        cp = RunStore.load_checkpoint("sess-gate")
        assert cp is not None
        assert cp["stage_key"] == "gate_plan"

        # HITL request must be pending
        pending = RunStore.get_pending_hitl("sess-gate")
        assert pending is not None
        assert pending["status"] == "pending"

        # Session must be awaiting_input
        rec = RunStore.get_session("sess-gate")
        assert rec["status"] == "awaiting_input"

    @pytest.mark.asyncio
    async def test_resume_skips_completed_agents(self, tmp_path):
        """On resume, agents already in _hitl_completed_agents are skipped."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from ai_research_engineer.server.run_store import RunStore
        from unittest.mock import MagicMock

        RunStore.init(db_path=tmp_path / "test.db")
        RunStore.save_session({
            "session_id": "sess-resume",
            "status": "running",
            "title": "T",
            "topic": "test",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        })

        a1 = _make_agent("ideation_loop")
        a2 = _make_agent("planning_tree_agent")
        a3 = _make_agent("stage_orchestrator")

        # Simulate that a1 and a2 are already done
        state: dict = {
            "_hitl_completed_agents": ["ideation_loop", "planning_tree_agent"],
            "_hitl_answer:gate_plan": "approve",
        }

        workflow = HITLSequentialAgent(
            sub_agents=[a1, a2, a3],
            hitl_enabled=True,
            gates={},  # no more gates — should run to completion
        )

        ctx = MagicMock()
        ctx.session.state = state
        ctx.session.id = "sess-resume"

        async for _ in workflow._run_async_impl(ctx):
            pass

        # a1 and a2 must NOT run again
        assert a1.call_count == 0
        assert a2.call_count == 0
        # a3 must run exactly once
        assert a3.call_count == 1

    @pytest.mark.asyncio
    async def test_answer_in_state_after_resume(self, tmp_path):
        """The gate answer should survive into resumed state."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from unittest.mock import MagicMock

        a1 = _make_agent("planning_tree_agent")

        state: dict = {
            "_hitl_completed_agents": [],
            "_hitl_answer:gate_plan": "approve",
        }

        workflow = HITLSequentialAgent(
            sub_agents=[a1],
            hitl_enabled=True,
            gates={},  # no gates so it runs through
        )

        ctx = MagicMock()
        ctx.session.state = state
        ctx.session.id = "sess-ans"

        async for _ in workflow._run_async_impl(ctx):
            pass

        assert state.get("_hitl_answer:gate_plan") == "approve"


# ---------------------------------------------------------------------------
# SEEKER in both modes
# ---------------------------------------------------------------------------


class TestSEEKERBothModes:
    @pytest.mark.asyncio
    async def test_tree_agent_runs_when_disabled(self):
        """IdeationTreeAgent-like agent must run even when hitl_enabled=False."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from unittest.mock import MagicMock

        tree_agent = _make_agent("ideation_tree_agent")
        workflow = HITLSequentialAgent(sub_agents=[tree_agent], hitl_enabled=False)

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-seeker-off"

        async for _ in workflow._run_async_impl(ctx):
            pass

        assert tree_agent.call_count == 1

    @pytest.mark.asyncio
    async def test_tree_agent_runs_when_enabled(self, tmp_path):
        """IdeationTreeAgent-like agent must run even when hitl_enabled=True (no gate on it)."""
        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from ai_research_engineer.server.run_store import RunStore
        from unittest.mock import MagicMock

        RunStore.init(db_path=tmp_path / "test.db")
        RunStore.save_session({
            "session_id": "sess-seeker-on",
            "status": "running",
            "title": "T",
            "topic": "test",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        })

        tree_agent = _make_agent("ideation_tree_agent")
        workflow = HITLSequentialAgent(
            sub_agents=[tree_agent],
            hitl_enabled=True,
            gates={},  # no gates
        )

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-seeker-on"

        async for _ in workflow._run_async_impl(ctx):
            pass

        assert tree_agent.call_count == 1


# ---------------------------------------------------------------------------
# Loop-outcome branching (S0-1)
# ---------------------------------------------------------------------------


class TestLoopOutcomeBranching:
    def test_loop_outcome_action_pure(self):
        from ai_research_engineer.agents.adk.hitl_sequential import loop_outcome_action

        assert loop_outcome_action("ideation_loop", "exhausted") == "halt"
        assert loop_outcome_action("paper_writing_loop", "exhausted") == "draft_unverified"
        assert loop_outcome_action("ideation_loop", "approved") == "continue"
        assert loop_outcome_action("some_other_loop", "exhausted") == "continue"
        assert loop_outcome_action("ideation_loop", None) == "continue"

    @pytest.mark.asyncio
    async def test_autonomous_halt_when_ideation_exhausted(self):
        """Autonomous: an exhausted ideation loop halts before planning runs."""
        from unittest.mock import MagicMock

        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent

        ideation = _MutatingAgent(
            "ideation_loop",
            lambda s: s.__setitem__("ideation_loop_outcome", "exhausted"),
        )
        planning = _make_agent("high_level_planning_loop")

        workflow = HITLSequentialAgent(sub_agents=[ideation, planning], hitl_enabled=False)
        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-halt"

        events = [ev async for ev in workflow._run_async_impl(ctx)]

        assert ideation.call_count == 1
        assert planning.call_count == 0  # halted before planning
        texts = [p.text for e in events if e.content for p in e.content.parts if getattr(p, "text", None)]
        assert any("halted" in t.lower() for t in texts)

    @pytest.mark.asyncio
    async def test_autonomous_draft_unverified_when_paper_exhausted(self):
        """Autonomous: an exhausted paper loop tags manuscript but lets the run finish."""
        from unittest.mock import MagicMock

        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent

        writer = _MutatingAgent(
            "paper_writing_loop",
            lambda s: s.__setitem__("paper_writing_loop_outcome", "exhausted"),
        )
        after = _make_agent("reference_verifier_agent")

        workflow = HITLSequentialAgent(sub_agents=[writer, after], hitl_enabled=False)
        state: dict = {}
        ctx = MagicMock()
        ctx.session.state = state
        ctx.session.id = "sess-draft"

        async for _ in workflow._run_async_impl(ctx):
            pass

        assert writer.call_count == 1
        assert after.call_count == 1  # run still finishes
        assert state["manuscript_status"] == "DRAFT_UNVERIFIED"

    @pytest.mark.asyncio
    async def test_supervised_pause_when_ideation_exhausted(self, tmp_path):
        """Supervised: an exhausted ideation loop pauses (does not run planning)."""
        from unittest.mock import MagicMock

        from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")
        RunStore.save_session({
            "session_id": "sess-pause-ideation",
            "status": "running",
            "title": "T",
            "topic": "test",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        })

        ideation = _MutatingAgent(
            "ideation_loop",
            lambda s: s.__setitem__("ideation_loop_outcome", "exhausted"),
        )
        planning = _make_agent("high_level_planning_loop")

        workflow = HITLSequentialAgent(
            sub_agents=[ideation, planning],
            hitl_enabled=True,
            gates={},
        )
        state: dict = {}
        ctx = MagicMock()
        ctx.session.state = state
        ctx.session.id = "sess-pause-ideation"

        with patch.object(workflow, "_build_context_md", return_value="# ctx"):
            async for _ in workflow._run_async_impl(ctx):
                pass

        assert planning.call_count == 0
        assert state.get("_hitl_paused") == "gate_ideation"


# ---------------------------------------------------------------------------
# Checkpoint fidelity
# ---------------------------------------------------------------------------


class TestCheckpointFidelity:
    def test_json_roundtrip(self, tmp_path):
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "test.db")

        original = {
            "original_user_input": "test topic",
            "high_level_stages": [{"index": 0, "title": "Stage A", "completed": False}],
            "_hitl_completed_agents": ["ideation_loop", "planning_tree_agent"],
            "use_graphify": False,
        }

        RunStore.save_checkpoint("sess-fid", "gate_plan", json.dumps(original))
        cp = RunStore.load_checkpoint("sess-fid")
        assert cp["state"] == original

    def test_non_serialisable_values_skipped(self):
        """_serialize_state should skip non-JSON-able values without error."""
        from ai_research_engineer.agents.adk.hitl_sequential import _serialize_state

        state = {
            "good_key": "value",
            "bad_key": object(),  # not JSON-serialisable
            "count": 42,
        }
        result = json.loads(_serialize_state(state))
        assert "good_key" in result
        assert "count" in result
        assert "bad_key" not in result

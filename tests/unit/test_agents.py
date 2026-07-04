"""Unit tests for agent implementations."""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import MagicMock, patch

from google.adk.events import Event
from google.genai import types

from ai_research_engineer.agents.adk.loop_detection import LoopDetectionAgent
from ai_research_engineer.agents.adk.stage_orchestrator import StageOrchestratorAgent
from ai_research_engineer.agents.claude_code.agent import ClaudeCodeAgent, setup_working_directory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_event(author: str, text: str, turn_complete: bool = False) -> Event:
    return Event(
        author=author,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        turn_complete=turn_complete,
    )


class _FakeCtx:
    def __init__(self, state=None):
        self.session = MagicMock()
        self.session.state = state or {}
        self.end_invocation = False


async def _drain(gen) -> List[Event]:
    events = []
    async for e in gen:
        events.append(e)
    return events


# ---------------------------------------------------------------------------
# LoopDetectionAgent._detect_pattern_repetition
# ---------------------------------------------------------------------------


class TestLoopDetectionPattern:
    """Pure-function tests for _detect_pattern_repetition."""

    def _make_agent(self):
        return LoopDetectionAgent(
            name="test_loop",
            description="test",
            model="gemini-2.5-pro",
            min_pattern_length=200,
            repetition_threshold=5,
        )

    def test_repeated_long_block_detected(self):
        agent = self._make_agent()
        pattern = "A" * 200
        # 5 consecutive repetitions — must be caught
        text = pattern * 5
        detected, _ = agent._detect_pattern_repetition(text)
        assert detected is True

    def test_varied_text_not_detected(self):
        agent = self._make_agent()
        text = " ".join(f"word_{i}" for i in range(300))
        detected, _ = agent._detect_pattern_repetition(text)
        assert detected is False

    def test_repeated_short_path_not_detected(self):
        """A realistic number of short path repetitions must NOT trigger detection.

        Individual paths are << min_pattern_length (200 chars).  With a small
        number of repetitions (15) the total text length stays well below
        min_pattern_length * repetition_threshold, so the early-exit guard
        returns False without scanning.
        """
        agent = self._make_agent()
        # 15 paths × ~13 chars each ≈ 195 chars < 200 * 5 = 1000 → early exit
        short = "/tmp/file.py\n" * 15
        detected, _ = agent._detect_pattern_repetition(short)
        assert detected is False

    def test_text_below_minimum_threshold_not_detected(self):
        agent = self._make_agent()
        # Not enough text to even form one pattern * threshold copies
        tiny = "x" * 50
        detected, _ = agent._detect_pattern_repetition(tiny)
        assert detected is False


# ---------------------------------------------------------------------------
# StageOrchestratorAgent control flow
# ---------------------------------------------------------------------------


class _FakeSubAgent:
    """Sub-agent that yields canned events and optionally mutates state."""

    def __init__(self, name: str, events=None, state_mutation=None):
        self.name = name
        self._events = events or []
        self._mutation = state_mutation  # callable(state) -> None

    async def run_async(self, ctx) -> AsyncGenerator[Event, None]:
        if self._mutation:
            self._mutation(ctx.session.state)
        for e in self._events:
            yield e


def _criteria_met_state():
    return {
        "high_level_stages": [{"index": 0, "title": "Stage 0", "description": "desc", "completed": False}],
        "high_level_success_criteria": [{"index": 0, "criteria": "done", "met": True}],
        "stage_implementations": [],
    }


def _no_stages_state():
    return {
        "high_level_stages": [{"index": 0, "title": "Stage 0", "description": "desc", "completed": True}],
        "high_level_success_criteria": [{"index": 0, "criteria": "done", "met": False}],
        "stage_implementations": [],
    }


class TestStageOrchestrator:
    def _make_orchestrator(self, impl_mut=None, checker_mut=None, reflector_mut=None):
        impl = _FakeSubAgent("impl", state_mutation=impl_mut)
        checker = _FakeSubAgent("checker", state_mutation=checker_mut)
        reflector = _FakeSubAgent("reflector", state_mutation=reflector_mut)
        return StageOrchestratorAgent(
            implementation_loop=impl,
            criteria_checker=checker,
            stage_reflector=reflector,
        )

    def test_exits_immediately_when_all_criteria_met(self):
        """If all criteria are already met, the orchestrator should exit without
        running the implementation loop."""
        orch = self._make_orchestrator()
        ctx = _FakeCtx(state=_criteria_met_state())

        events = asyncio.run(_drain(orch._run_async_impl(ctx)))
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("success criteria" in t.lower() or "criteria" in t.lower() for t in texts)

    def test_exits_when_no_stages_remain_after_reflector(self):
        """When all stages are marked completed but criteria are not met, the
        orchestrator runs the reflector; if it still can't find stages it exits."""
        # reflector doesn't add any new stages
        orch = self._make_orchestrator()
        ctx = _FakeCtx(state=_no_stages_state())

        events = asyncio.run(_drain(orch._run_async_impl(ctx)))
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        # Should emit a warning about no remaining stages
        assert any(
            "no remaining stages" in t.lower() or "not all" in t.lower() or "summary" in t.lower() for t in texts
        )


class TestClaudeCodeAgent:
    """Test ClaudeCodeAgent."""

    def test_initialization_default(self):
        """Test ClaudeCodeAgent default initialization."""
        agent = ClaudeCodeAgent()
        assert agent.name == "claude_coding_agent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent._output_key == "implementation_summary"

    def test_initialization_custom(self):
        """Test ClaudeCodeAgent custom initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ClaudeCodeAgent(
                name="custom_agent",
                description="Custom description",
                working_dir=tmpdir,
                output_key="custom_output",
            )
            assert agent.name == "custom_agent"
            assert agent.description == "Custom description"
            assert agent._working_dir == tmpdir
            assert agent._output_key == "custom_output"
            assert agent.model == "claude-sonnet-4-5-20250929"

    def test_truncate_summary_short(self):
        """Test summary truncation with short text."""
        agent = ClaudeCodeAgent()
        short_text = "Short summary"
        truncated = agent._truncate_summary(short_text)
        assert truncated == short_text

    def test_truncate_summary_long(self):
        """Test summary truncation with long text."""
        agent = ClaudeCodeAgent()
        long_text = "x" * 50000  # 50k characters
        truncated = agent._truncate_summary(long_text)
        assert len(truncated) <= 41000  # Should be around 40k + truncation message
        assert "middle section truncated" in truncated


class TestSetupWorkingDirectory:
    """Test setup_working_directory function."""

    def test_create_directory_structure(self):
        """Test that working directory is created with proper structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir) / "test_session"
            setup_working_directory(str(working_dir))

            assert working_dir.exists()
            assert (working_dir / "user_data").exists()
            assert (working_dir / "workflow").exists()
            assert (working_dir / "results").exists()
            assert (working_dir / "pyproject.toml").exists()
            assert (working_dir / "README.md").exists()

    def test_pyproject_content(self):
        """Test that pyproject.toml is created with proper content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir) / "test_session"
            setup_working_directory(str(working_dir))

            pyproject_content = (working_dir / "pyproject.toml").read_text()
            assert "[project]" in pyproject_content
            assert "python" in pyproject_content.lower()

    def test_readme_content(self):
        """Test that README.md is created with proper content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir) / "test_session"
            setup_working_directory(str(working_dir))

            readme_content = (working_dir / "README.md").read_text()
            assert "AI Research Engineer Session" in readme_content
            assert "user_data/" in readme_content
            assert "workflow/" in readme_content
            assert "results/" in readme_content

    def test_idempotent(self):
        """Test that setup is idempotent (can be called multiple times)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir) / "test_session"

            # Call setup twice
            setup_working_directory(str(working_dir))
            setup_working_directory(str(working_dir))

            # Should still have correct structure
            assert (working_dir / "user_data").exists()
            assert (working_dir / "pyproject.toml").exists()


# ---------------------------------------------------------------------------
# Helpers shared by tree tests
# ---------------------------------------------------------------------------


def _full_run_state():
    """State with one stage and one criterion — simulates a full run."""
    return {
        "original_user_input": "Test research topic",
        "high_level_stages": [{"index": 0, "title": "Stage 0", "description": "Do experiments", "completed": False}],
        "high_level_success_criteria": [{"index": 0, "criteria": "accuracy > 0.9", "met": False}],
        "stage_implementations": [],
    }


def _make_ctx(state: dict, session_id: str = "test-session-tree") -> "_FakeCtx":
    ctx = _FakeCtx(state=state)
    ctx.session.id = session_id
    return ctx


def _make_full_orch(checker_met=False):
    """Orchestrator that completes one stage and (optionally) marks criteria met."""

    def impl_mutation(state):
        state["implementation_summary"] = "Implemented successfully"

    def checker_mutation(state):
        for c in state.get("high_level_success_criteria", []):
            c["met"] = checker_met

    impl = _FakeSubAgent("impl", state_mutation=impl_mutation)
    checker = _FakeSubAgent("checker", state_mutation=checker_mutation)
    reflector = _FakeSubAgent("reflector")
    return StageOrchestratorAgent(
        implementation_loop=impl,
        criteria_checker=checker,
        stage_reflector=reflector,
    )


# ---------------------------------------------------------------------------
# Orchestrator dual-write tests
# ---------------------------------------------------------------------------


class TestOrchestratorTreeDualWrite:
    """Verify that the orchestrator dual-writes an argument tree without changing control flow."""

    def test_tree_seeded_after_run(self, tmp_path):
        """After a run, the tree contains a root, an experiment per stage, and claims per criterion."""
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "orch_tree.db"
        # Point TreeBuilder at our temp DB by patching the default
        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            orch = _make_full_orch(checker_met=True)
            ctx = _make_ctx(_full_run_state(), session_id="orch-run-1")
            asyncio.run(_drain(orch._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="orch-run-1", db_path=db)
        try:
            root = tree.get_root()
            assert root is not None
            assert "Test research topic" in root["label"]

            experiments = tree.get_nodes_by_type("experiment")
            assert len(experiments) == 1
            assert experiments[0]["metadata"]["stage_index"] == 0

            claims = tree.get_nodes_by_type("claim")
            assert len(claims) == 1
        finally:
            tree.close()

    def test_claim_status_flips_to_supported(self, tmp_path):
        """When a criterion is marked met, the corresponding claim becomes 'supported'."""
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "orch_claim.db"
        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            orch = _make_full_orch(checker_met=True)
            ctx = _make_ctx(_full_run_state(), session_id="orch-run-2")
            asyncio.run(_drain(orch._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="orch-run-2", db_path=db)
        try:
            claims = tree.get_nodes_by_type("claim")
            assert len(claims) == 1
            assert claims[0]["status"] == "supported"
        finally:
            tree.close()

    def test_experiment_node_marked_completed(self, tmp_path):
        """After a stage completes, its experiment node status is 'completed'."""
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "orch_exp.db"
        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            orch = _make_full_orch(checker_met=True)
            ctx = _make_ctx(_full_run_state(), session_id="orch-run-3")
            asyncio.run(_drain(orch._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="orch-run-3", db_path=db)
        try:
            experiments = tree.get_nodes_by_type("experiment")
            assert len(experiments) == 1
            assert experiments[0]["status"] == "completed"
        finally:
            tree.close()

    def test_result_node_created_per_stage(self, tmp_path):
        """After the implementation loop, a result node is added under the experiment."""
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "orch_result.db"
        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            orch = _make_full_orch(checker_met=True)
            ctx = _make_ctx(_full_run_state(), session_id="orch-run-4")
            asyncio.run(_drain(orch._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="orch-run-4", db_path=db)
        try:
            results = tree.get_nodes_by_type("result")
            assert len(results) == 1
            assert results[0]["content"] == "Implemented successfully"
        finally:
            tree.close()


# ---------------------------------------------------------------------------
# Honest stage status (S0-2)
# ---------------------------------------------------------------------------


class TestStageStatusHonesty:
    """The stage dict must record 'completed' vs 'completed_unverified' honestly."""

    def test_pure_status_derivation(self):
        from ai_research_engineer.agents.adk.stage_orchestrator import (
            derive_stage_status,
            stage_completed_flag,
        )

        assert derive_stage_status("approved") == "completed"
        assert derive_stage_status("exhausted") == "completed_unverified"
        assert derive_stage_status(None) == "completed_unverified"
        # Both terminal statuses mean the stage cycle finished (back-compat bool).
        assert stage_completed_flag("completed") is True
        assert stage_completed_flag("completed_unverified") is True
        assert stage_completed_flag("pending") is False

    def test_stage_unverified_when_impl_loop_not_approved(self):
        """No implementation_loop_outcome -> stage 'completed_unverified', completed=True."""
        orch = _make_full_orch(checker_met=True)
        state = _full_run_state()
        ctx = _make_ctx(state, session_id="orch-status-unverified")
        asyncio.run(_drain(orch._run_async_impl(ctx)))

        stage = state["high_level_stages"][0]
        assert stage["status"] == "completed_unverified"
        assert stage["completed"] is True  # legacy bool retained, derived

    def test_stage_completed_when_impl_loop_approved(self):
        """implementation_loop_outcome == 'approved' -> stage 'completed'."""

        def impl_mutation(state):
            state["implementation_summary"] = "Implemented successfully"
            state["implementation_loop_outcome"] = "approved"

        def checker_mutation(state):
            for c in state.get("high_level_success_criteria", []):
                c["met"] = True

        orch = StageOrchestratorAgent(
            implementation_loop=_FakeSubAgent("impl", state_mutation=impl_mutation),
            criteria_checker=_FakeSubAgent("checker", state_mutation=checker_mutation),
            stage_reflector=_FakeSubAgent("reflector"),
        )
        state = _full_run_state()
        ctx = _make_ctx(state, session_id="orch-status-approved")
        asyncio.run(_drain(orch._run_async_impl(ctx)))

        stage = state["high_level_stages"][0]
        assert stage["status"] == "completed"
        assert stage["completed"] is True


# ---------------------------------------------------------------------------
# No-progress guard (S0-3)
# ---------------------------------------------------------------------------


class TestNoProgressGuard:
    """A stuck orchestration (no disk/criteria change) must force reflection on
    the 2nd identical iteration and terminate with partial results on the 3rd."""

    def test_forces_reflection_then_terminates(self, tmp_path):
        from ai_research_engineer.agents.adk.stage_orchestrator import (
            FORCED_REFLECTION_INSTRUCTION,
            StageOrchestratorAgent,
        )

        # Empty workflow/ and results/ -> the file signature is stable across iters.
        (tmp_path / "workflow").mkdir()
        (tmp_path / "results").mkdir()

        def reopen(state):
            # The reflector never accepts the stage as done, so remaining stages
            # never empty and the status vector stays identical -> no progress.
            for s in state.get("high_level_stages", []):
                s["completed"] = False
                s["status"] = "pending"

        orch = StageOrchestratorAgent(
            implementation_loop=_FakeSubAgent("impl"),  # writes nothing, sets no outcome
            criteria_checker=_FakeSubAgent("checker"),  # criteria stay not-met
            stage_reflector=_FakeSubAgent("reflector", state_mutation=reopen),
            working_dir=str(tmp_path),
        )

        state = {
            "high_level_stages": [{"index": 0, "title": "S0", "description": "d", "completed": False}],
            "high_level_success_criteria": [{"index": 0, "criteria": "acc>0.9", "met": False}],
            "stage_implementations": [],
        }
        ctx = _make_ctx(state, session_id="orch-no-progress")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", tmp_path / "pipeline.db"):
            events = asyncio.run(_drain(orch._run_async_impl(ctx)))

        # progress_hash emitted each iteration; run stops at iteration 3 (not max).
        hashes = state["_progress_hashes"]
        assert [h["iteration"] for h in hashes] == [1, 2, 3]
        assert len({h["hash"] for h in hashes}) == 1  # all identical -> no progress

        # Forcing instruction injected on the 2nd identical iteration.
        assert state["stage_reflector_forced_instruction"] == FORCED_REFLECTION_INSTRUCTION

        # Gate events, in order: forced reflection (iter 2) then termination (iter 3).
        outcomes = [g["outcome"] for g in state["_gate_decisions"] if g["loop"] == "stage_orchestrator"]
        assert outcomes == ["no_progress_forced_reflection", "no_progress_terminated"]

        # Emitted events carry the progress_hash and the partial-results termination.
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("progress_hash" in t for t in texts)
        assert any("No-progress termination" in t for t in texts)
        assert any("partial results" in t.lower() for t in texts)

    def test_reflector_action_resets_counter(self, tmp_path):
        """A forced reflection that actually modifies the plan resets the counter,
        so the run does NOT terminate next iteration — only if it gets stuck again."""
        from ai_research_engineer.agents.adk.stage_orchestrator import StageOrchestratorAgent

        (tmp_path / "workflow").mkdir()
        (tmp_path / "results").mkdir()

        acted = {"done": False}

        def reflector(state):
            # Always re-open the stage (stuck), BUT the FIRST time it is run under
            # a forcing instruction, actually act: modify a stage description and
            # report a non-empty stage_modifications. Subsequent forced runs report
            # nothing, so the run eventually terminates.
            for s in state.get("high_level_stages", []):
                s["completed"] = False
                s["status"] = "pending"
            forced = bool(state.get("stage_reflector_forced_instruction"))
            if forced and not acted["done"]:
                state["high_level_stages"][0]["description"] += " [revised]"
                state["stage_reflector_output"] = {"stage_modifications": [{"index": 0}], "new_stages": []}
                acted["done"] = True
            else:
                state["stage_reflector_output"] = {"stage_modifications": [], "new_stages": []}

        orch = StageOrchestratorAgent(
            implementation_loop=_FakeSubAgent("impl"),
            criteria_checker=_FakeSubAgent("checker"),
            stage_reflector=_FakeSubAgent("reflector", state_mutation=reflector),
            working_dir=str(tmp_path),
        )

        state = {
            "high_level_stages": [{"index": 0, "title": "S0", "description": "d", "completed": False}],
            "high_level_success_criteria": [{"index": 0, "criteria": "acc>0.9", "met": False}],
            "stage_implementations": [],
        }
        ctx = _make_ctx(state, session_id="orch-reset")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", tmp_path / "pipeline.db"):
            asyncio.run(_drain(orch._run_async_impl(ctx)))

        iters = [h["iteration"] for h in state["_progress_hashes"]]
        outcomes = [g["outcome"] for g in state["_gate_decisions"] if g["loop"] == "stage_orchestrator"]

        # The reflector acted (modified the description).
        assert acted["done"] is True
        assert "[revised]" in state["high_level_stages"][0]["description"]

        # Force fires at iter 2 (acts -> reset), so the run does NOT terminate at
        # iter 3. It gets stuck again, forces at iter 4 (no action), and only then
        # terminates at iter 5.
        assert iters == [1, 2, 3, 4, 5]
        assert outcomes == [
            "no_progress_forced_reflection",  # iter 2 — acted, counter reset
            "no_progress_forced_reflection",  # iter 4 — no action
            "no_progress_terminated",  # iter 5
        ]

    def test_no_progress_pauses_when_hitl(self, tmp_path):
        """With hitl_enabled=True, the 3rd identical hash must PAUSE (set the same
        state key HITLSequentialAgent uses) and must NOT emit the autonomous
        partial-results terminal event."""
        from ai_research_engineer.agents.adk.stage_orchestrator import StageOrchestratorAgent

        (tmp_path / "workflow").mkdir()
        (tmp_path / "results").mkdir()

        def reopen(state):
            for s in state.get("high_level_stages", []):
                s["completed"] = False
                s["status"] = "pending"

        orch = StageOrchestratorAgent(
            implementation_loop=_FakeSubAgent("impl"),
            criteria_checker=_FakeSubAgent("checker"),
            stage_reflector=_FakeSubAgent("reflector", state_mutation=reopen),
            working_dir=str(tmp_path),
            hitl_enabled=True,
        )

        state = {
            "high_level_stages": [{"index": 0, "title": "S0", "description": "d", "completed": False}],
            "high_level_success_criteria": [{"index": 0, "criteria": "acc>0.9", "met": False}],
            "stage_implementations": [],
        }
        ctx = _make_ctx(state, session_id="orch-hitl-no-progress")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", tmp_path / "pipeline.db"):
            events = asyncio.run(_drain(orch._run_async_impl(ctx)))

        # Stopped on the 3rd identical hash.
        assert [h["iteration"] for h in state["_progress_hashes"]] == [1, 2, 3]
        outcomes = [g["outcome"] for g in state["_gate_decisions"] if g["loop"] == "stage_orchestrator"]
        assert outcomes[-1] == "no_progress_terminated"

        # Paused via the exact mechanism HITLSequentialAgent / api.py rely on.
        assert state["_hitl_paused"] == "gate_no_progress"
        assert state.get("_hitl_question")

        # Must NOT emit the autonomous partial-results terminal event.
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert not any("No-progress termination" in t for t in texts)
        assert not any("partial results" in t.lower() for t in texts)
        # A pause event is emitted instead.
        assert any("No-progress pause" in t for t in texts)


# ---------------------------------------------------------------------------
# Failure isolation: tree errors must not affect orchestrator output
# ---------------------------------------------------------------------------


class TestOrchestratorTreeFailureIsolation:
    def test_run_completes_when_treebuilder_raises_on_init(self, tmp_path):
        """If TreeBuilder.__init__ raises, the orchestrator still completes normally.

        The import is done inside _run_async_impl, so we patch the class in its
        source module (ai_research_engineer.core.argument_tree).
        """
        orch = _make_full_orch(checker_met=True)
        ctx = _make_ctx(_full_run_state(), session_id="orch-run-fail")

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder.__init__",
            side_effect=RuntimeError("DB unavailable"),
        ):
            events = asyncio.run(_drain(orch._run_async_impl(ctx)))

        # Should still get the normal completion event
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("criteria" in t.lower() or "summary" in t.lower() or "stage" in t.lower() for t in texts)
        assert len(events) > 0

    def test_run_completes_when_tree_write_raises(self, tmp_path):
        """If add_root raises after init, _tree_safe swallows it and the run completes."""
        from ai_research_engineer.core.argument_tree import TreeBuilder as RealTreeBuilder

        db = tmp_path / "fail_write.db"

        class _BrokenTree(RealTreeBuilder):
            def add_root(self, *a, **kw):
                raise RuntimeError("write failed")

        orch = _make_full_orch(checker_met=True)
        ctx = _make_ctx(_full_run_state(), session_id="orch-run-fail2")

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder",
            lambda run_id, **kw: _BrokenTree(run_id, db_path=db),
        ):
            events = asyncio.run(_drain(orch._run_async_impl(ctx)))

        assert len(events) > 0


# ---------------------------------------------------------------------------
# IdeationTreeAgent
# ---------------------------------------------------------------------------


class TestIdeationTreeAgent:
    def test_hypothesis_node_written(self, tmp_path):
        from ai_research_engineer.agents.adk.tree_seed_agents import IdeationTreeAgent
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "idea.db"
        agent = IdeationTreeAgent(working_dir="")
        state = {
            "generated_ideas": "Use contrastive learning for self-supervised pretraining.",
            "original_user_input": "Novel SSL method",
        }
        ctx = _make_ctx(state, session_id="idea-run-1")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            asyncio.run(_drain(agent._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="idea-run-1", db_path=db)
        try:
            hyps = tree.get_nodes_by_type("hypothesis")
            assert len(hyps) == 1
            assert "contrastive learning" in hyps[0]["label"]
            root = tree.get_root()
            assert root is not None
            assert "Novel SSL method" in root["label"]
        finally:
            tree.close()

    def test_idempotent_no_duplicate_hypotheses(self, tmp_path):
        from ai_research_engineer.agents.adk.tree_seed_agents import IdeationTreeAgent
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "idea2.db"
        agent = IdeationTreeAgent(working_dir="")
        state = {"generated_ideas": "SSL method idea", "original_user_input": "SSL topic"}
        ctx = _make_ctx(state, session_id="idea-run-2")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            asyncio.run(_drain(agent._run_async_impl(ctx)))
            asyncio.run(_drain(agent._run_async_impl(ctx)))  # second call — must be idempotent

        tree = TreeBuilder(run_id="idea-run-2", db_path=db)
        try:
            assert len(tree.get_nodes_by_type("hypothesis")) == 1
            assert len(tree.get_nodes_by_type("root")) == 1
        finally:
            tree.close()

    def test_failure_does_not_crash(self):
        from ai_research_engineer.agents.adk.tree_seed_agents import IdeationTreeAgent

        agent = IdeationTreeAgent(working_dir="")
        state = {"generated_ideas": "idea", "original_user_input": "topic"}
        ctx = _make_ctx(state, session_id="idea-run-fail")

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder.__init__",
            side_effect=RuntimeError("DB unavailable"),
        ):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))

        assert len(events) > 0  # status event still emitted


# ---------------------------------------------------------------------------
# PlanningTreeAgent
# ---------------------------------------------------------------------------


class TestPlanningTreeAgent:
    def _plan_state(self, n_stages: int = 2, n_criteria: int = 2):
        return {
            "original_user_input": "Novel SSL research",
            "high_level_stages": [
                {"index": i, "title": f"Stage {i}", "description": f"desc {i}", "completed": False}
                for i in range(n_stages)
            ],
            "high_level_success_criteria": [
                {"index": i, "criteria": f"Criterion {i}", "met": False}
                for i in range(n_criteria)
            ],
        }

    def test_experiments_and_claims_written(self, tmp_path):
        from ai_research_engineer.agents.adk.tree_seed_agents import PlanningTreeAgent
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "plan.db"
        agent = PlanningTreeAgent(working_dir="")
        ctx = _make_ctx(self._plan_state(n_stages=2, n_criteria=3), session_id="plan-run-1")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            asyncio.run(_drain(agent._run_async_impl(ctx)))

        tree = TreeBuilder(run_id="plan-run-1", db_path=db)
        try:
            assert len(tree.get_nodes_by_type("experiment")) == 2
            assert len(tree.get_nodes_by_type("claim")) == 3
            root = tree.get_root()
            assert root is not None
            assert "Novel SSL research" in root["label"]
        finally:
            tree.close()

    def test_no_duplicates_on_second_run(self, tmp_path):
        """Stage_index and criterion_index de-dup prevents doubles on retry."""
        from ai_research_engineer.agents.adk.tree_seed_agents import PlanningTreeAgent
        from ai_research_engineer.core.argument_tree import TreeBuilder

        db = tmp_path / "plan2.db"
        agent = PlanningTreeAgent(working_dir="")
        ctx = _make_ctx(self._plan_state(n_stages=1, n_criteria=1), session_id="plan-run-2")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            asyncio.run(_drain(agent._run_async_impl(ctx)))
            asyncio.run(_drain(agent._run_async_impl(ctx)))  # second call

        tree = TreeBuilder(run_id="plan-run-2", db_path=db)
        try:
            stats = tree.get_stats()
            assert stats["by_type"].get("experiment", 0) == 1
            assert stats["by_type"].get("claim", 0) == 1
            assert stats["by_type"].get("root", 0) == 1
        finally:
            tree.close()

    def test_no_stages_emits_skip_event(self, tmp_path):
        from ai_research_engineer.agents.adk.tree_seed_agents import PlanningTreeAgent

        db = tmp_path / "plan3.db"
        agent = PlanningTreeAgent(working_dir="")
        ctx = _make_ctx({"original_user_input": "topic"}, session_id="plan-run-empty")

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))

        assert len(events) == 1
        assert "skipped" in events[0].content.parts[0].text.lower()

    def test_failure_does_not_crash(self):
        from ai_research_engineer.agents.adk.tree_seed_agents import PlanningTreeAgent

        agent = PlanningTreeAgent(working_dir="")
        ctx = _make_ctx(self._plan_state(), session_id="plan-run-fail")

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder.__init__",
            side_effect=RuntimeError("DB unavailable"),
        ):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))

        assert len(events) > 0

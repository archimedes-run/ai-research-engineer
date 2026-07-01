"""Unit tests for agent implementations."""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import MagicMock

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

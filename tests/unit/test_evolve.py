"""
Unit tests for the evolutionary loop and evolve-related infrastructure.

No network calls are made; the Database uses a tmp_path and all LLM
sub-agents are replaced with no-op fakes.
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import MagicMock, patch

import pytest

from ai_research_engineer.agents.adk.evolution_loop import (
    PROGRAM_FILENAME,
    EvolutionLoopAgent,
)
from ai_research_engineer.evolve.utils.structures import Node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeCtx:
    """Minimal InvocationContext substitute."""

    def __init__(self):
        self.session = MagicMock()
        self.session.state = {}


async def _drain(gen) -> List:
    events = []
    async for e in gen:
        events.append(e)
    return events


# ---------------------------------------------------------------------------
# 1.2 — working_dir state key is populated
# ---------------------------------------------------------------------------


class TestWorkingDirState:
    def test_build_initial_state_contains_working_dir(self, tmp_path):
        """_build_initial_state must include working_dir equal to self.working_dir."""
        from ai_research_engineer.core.api import AIEngineer

        eng = AIEngineer(agent_type="adk", working_dir=str(tmp_path))
        state = eng._build_initial_state("hello")
        assert "working_dir" in state
        assert Path(state["working_dir"]) == tmp_path.resolve() or Path(state["working_dir"]) == tmp_path


# ---------------------------------------------------------------------------
# 1.3 — parent code materialised before coding agent runs
# ---------------------------------------------------------------------------


class _FakeCodingAgent:
    """Records whether parent code existed on disk before it was 'called'."""

    name = "fake_coder"

    def __init__(self, program_path: Path):
        self._program_path = program_path
        self.code_on_disk_before_call: str | None = None

    async def run_async(self, ctx) -> AsyncGenerator:
        # Capture what is on disk at call time
        if self._program_path.exists():
            self.code_on_disk_before_call = self._program_path.read_text()
        else:
            self.code_on_disk_before_call = None
        # yield nothing — we just need to verify the side-effect
        return
        yield  # make this a generator


class _FakeAnalyzerAgent:
    name = "fake_analyzer"

    async def run_async(self, ctx) -> AsyncGenerator:
        return
        yield


class _FakeDatabase:
    def __init__(self, nodes):
        self._nodes = nodes

    def __len__(self):
        return len(self._nodes)

    def sample(self, n=1):
        return self._nodes[:n]

    def add(self, node):
        node.id = len(self._nodes)
        self._nodes.append(node)
        return node.id

    def get_all(self):
        return list(self._nodes)


class _FakeBestSnapshot:
    def __init__(self):
        self.best_dir = None

    def update_if_better(self, node, step_name, source_dir=None):
        return False


class TestParentMaterialisation:
    def test_parent_code_written_before_coding_agent(self, tmp_path):
        """
        Given a DB with one parent node that has code, the coding agent must
        see that code on disk at workflow/initial_program.py before it runs.
        """
        parent_code = "# parent program\nprint('hello')\n"
        parent = Node(name="Gen_0", code=parent_code, score=0.5)
        parent.id = 0

        db = _FakeDatabase([parent])
        snapshot = _FakeBestSnapshot()

        workflow_dir = tmp_path / "workflow"
        workflow_dir.mkdir()
        program_path = workflow_dir / PROGRAM_FILENAME

        coder = _FakeCodingAgent(program_path=program_path)
        analyzer = _FakeAnalyzerAgent()

        agent = EvolutionLoopAgent(
            coding_agent=coder,
            analyzer_agent=analyzer,
            database=db,
            best_snapshot=snapshot,
            max_generations=1,
        )

        ctx = _FakeCtx()
        ctx.session.state["working_dir"] = str(tmp_path)
        # Seed the workflow dir with a fake results.json
        (workflow_dir / "results.json").write_text('{"score": 0.5}')
        # Pre-write a different file so we can verify it was overwritten
        program_path.write_text("# old content")

        asyncio.run(_drain(agent._run_async_impl(ctx)))

        assert coder.code_on_disk_before_call == parent_code


# ---------------------------------------------------------------------------
# Evolve sampling smoke test (all algorithms)
# ---------------------------------------------------------------------------


class TestDatabaseSampling:
    """
    Smoke test: Database.add() + Database.sample() works for every algorithm.
    Uses a real Database instance backed by tmp_path (avoids network calls
    because the embedding service is monkey-patched).
    """

    @pytest.mark.parametrize("algorithm", ["ucb1", "random", "greedy", "island"])
    def test_sample_returns_node(self, tmp_path, algorithm):
        """Database.sample(n=1) must return a node for every algorithm."""
        # Patch the embedding service and FAISS to avoid model downloads.
        with (
            patch("ai_research_engineer.evolve.database.database.EmbeddingService") as mock_emb,
            patch("ai_research_engineer.evolve.database.database.FAISSIndex") as mock_faiss,
        ):
            mock_emb.return_value.encode.return_value = [0.0] * 384
            mock_faiss.return_value.add.return_value = None
            mock_faiss.return_value.search.return_value = []
            mock_faiss.return_value.save.return_value = None

            from ai_research_engineer.evolve.database.database import Database

            db = Database(storage_dir=tmp_path / algorithm, sampling_algorithm=algorithm)
            node = Node(name="test", code="x=1", score=1.0)
            db.add(node)

            sampled = db.sample(n=1)
            assert len(sampled) == 1
            assert sampled[0].name == "test"

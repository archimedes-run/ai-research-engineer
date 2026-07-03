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


# ---------------------------------------------------------------------------
# Sealed evaluation (S0-4)
# ---------------------------------------------------------------------------


class TestNoneScoreDatabase:
    """Database must accept score=None nodes and samplers must skip them (S0-4)."""

    def test_add_none_score_and_sample_skips_it(self, tmp_path):
        with (
            patch("ai_research_engineer.evolve.database.database.EmbeddingService") as mock_emb,
            patch("ai_research_engineer.evolve.database.database.FAISSIndex") as mock_faiss,
        ):
            mock_emb.return_value.encode.return_value = [0.0] * 384
            mock_faiss.return_value.add.return_value = None
            mock_faiss.return_value.search.return_value = []
            mock_faiss.return_value.save.return_value = None

            from ai_research_engineer.evolve.database.database import Database

            db = Database(storage_dir=tmp_path / "none_score", sampling_algorithm="ucb1")
            scored = Node(name="scored", code="x=1", score=1.0, status="success")
            failed = Node(name="failed", code="y=2", score=None, status="failed")
            db.add(scored)  # accepted
            db.add(failed)  # accepted, but must never be sampled

            assert len(db.get_all()) == 2
            for _ in range(5):
                sampled = db.sample(n=1)
                assert sampled and sampled[0].name == "scored"


class TestSealedEvaluation:
    """The orchestrator runs eval.sh itself; the committed score comes only from
    a results.json that eval.sh (re)wrote after the eval started (S0-4)."""

    def test_happy_path_real_eval_writes_score(self, tmp_path):
        workflow = tmp_path / "workflow"
        workflow.mkdir()
        (workflow / PROGRAM_FILENAME).write_text("# baseline program\n")
        (workflow / "results.json").write_text('{"score": 0.5}')  # baseline seed score

        # A real, tiny eval.sh that writes a fresh score to results.json.
        eval_sh = workflow / "eval.sh"
        eval_sh.write_text("#!/usr/bin/env bash\necho '{\"score\": 0.9}' > results.json\n")
        eval_sh.chmod(0o755)

        db = _FakeDatabase([])
        agent = EvolutionLoopAgent(
            coding_agent=_FakeAnalyzerAgent(),  # no-op: never touches results.json
            analyzer_agent=_FakeAnalyzerAgent(),
            database=db,
            best_snapshot=_FakeBestSnapshot(),
            max_generations=1,
        )

        ctx = _FakeCtx()
        ctx.session.id = "sealed-happy"
        ctx.session.state["working_dir"] = str(tmp_path)

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", tmp_path / "pipeline.db"):
            asyncio.run(_drain(agent._run_async_impl(ctx)))

        # The mutation node was committed with the sealed score + status.
        gen_nodes = [n for n in db.get_all() if n.name == "Generation_1"]
        assert len(gen_nodes) == 1
        assert gen_nodes[0].score == 0.9
        assert gen_nodes[0].status == "success"

        # eval_result recorded per generation (gen 0 sealed baseline + gen 1);
        # the gen-1 mutation carries a real (positive) duration.
        evals = ctx.session.state["_eval_results"]
        gen1_evals = [e for e in evals if e["gen"] == 1]
        assert len(gen1_evals) == 1
        gen1 = gen1_evals[0]
        assert gen1["score"] == 0.9
        assert gen1["status"] == "success"
        assert gen1["duration_s"] > 0

        # It serializes as an eval_result event carrying the duration.
        from ai_research_engineer.core.events import create_event, event_to_dict

        payload = event_to_dict(create_event("eval_result", **gen1))
        assert payload["type"] == "eval_result"
        assert payload["score"] == 0.9
        assert payload["duration_s"] > 0

    def test_mutation_results_deleted_before_eval_tamper_proof(self, tmp_path):
        """The mutation writes results.json{score:999} and eval.sh writes nothing
        -> failed/None. Uses a FORGED future mtime so the score would pass a bare
        `mtime > started` fence; the pre-eval deletion makes it tamper-proof
        (a surviving results.json is proof eval.sh produced it)."""
        import os
        import time as _time

        workflow = tmp_path / "workflow"
        workflow.mkdir()
        results = workflow / "results.json"
        results.write_text('{"score": 999}')
        # Forge a mtime one hour in the future — this defeats a naive mtime fence.
        future = _time.time() + 3600
        os.utime(results, (future, future))
        # eval.sh runs cleanly (exit 0) but writes nothing.
        eval_sh = workflow / "eval.sh"
        eval_sh.write_text("#!/usr/bin/env bash\ntrue\n")
        eval_sh.chmod(0o755)

        agent = EvolutionLoopAgent(
            coding_agent=_FakeAnalyzerAgent(),
            analyzer_agent=_FakeAnalyzerAgent(),
            database=_FakeDatabase([]),
            best_snapshot=_FakeBestSnapshot(),
            max_generations=1,
        )
        score, status, _duration = agent._evaluate(tmp_path)

        assert score is None, "a forged future-dated results.json must not be trusted"
        assert status == "failed"
        assert not results.exists(), "the pre-existing results.json must be deleted before eval.sh runs"


class TestSealedBootstrap:
    """Generation 0 must be scored by the orchestrator's own sealed _evaluate(),
    never by a self-reported results.json on disk (S0-4)."""

    def _run_bootstrap_only(self, tmp_path, eval_body: str):
        """Run the evolve loop with 0 mutation generations (bootstrap only)."""
        workflow = tmp_path / "workflow"
        workflow.mkdir()
        (workflow / PROGRAM_FILENAME).write_text("# baseline program\n")
        # A stale, inflated, self-reported score already on disk.
        (workflow / "results.json").write_text('{"score": 0.99}')
        eval_sh = workflow / "eval.sh"
        eval_sh.write_text(f"#!/usr/bin/env bash\n{eval_body}\n")
        eval_sh.chmod(0o755)

        db = _FakeDatabase([])
        agent = EvolutionLoopAgent(
            coding_agent=_FakeAnalyzerAgent(),
            analyzer_agent=_FakeAnalyzerAgent(),
            database=db,
            best_snapshot=_FakeBestSnapshot(),
            max_generations=0,  # bootstrap only — no mutation generations
        )
        ctx = _FakeCtx()
        ctx.session.id = "sealed-bootstrap"
        ctx.session.state["working_dir"] = str(tmp_path)

        with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", tmp_path / "pipeline.db"):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))
        return db, ctx.session.state, events

    def test_bootstrap_score_comes_from_sealed_eval_not_disk(self, tmp_path):
        # eval.sh actually produces 0.42; disk results.json says 0.99.
        db, state, _ = self._run_bootstrap_only(tmp_path, eval_body="echo '{\"score\": 0.42}' > results.json")

        node0 = [n for n in db.get_all() if n.name == "Generation_0_Baseline"]
        assert len(node0) == 1
        assert node0[0].score == 0.42, "Node 0 must take the sealed eval score, not the disk 0.99"
        assert node0[0].status == "success"

        # gen-0 eval_result recorded with the sealed score.
        assert any(e["gen"] == 0 and e["score"] == 0.42 and e["status"] == "success" for e in state["_eval_results"])

    def test_bootstrap_eval_failure_is_loud_and_unscored(self, tmp_path):
        # eval.sh runs but does NOT (re)write results.json -> the 0.99 is stale.
        db, state, events = self._run_bootstrap_only(tmp_path, eval_body="true")

        node0 = [n for n in db.get_all() if n.name == "Generation_0_Baseline"][0]
        assert node0.score is None, "a failed baseline must NOT inherit the disk score"
        assert node0.status == "failed"

        assert any(e["gen"] == 0 and e["status"] == "failed" for e in state["_eval_results"])

        # The failure is surfaced loudly, not silent.
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("Baseline evaluation failed" in t for t in texts)

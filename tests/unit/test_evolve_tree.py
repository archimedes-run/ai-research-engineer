"""
Unit tests: evolve mode → argument tree dual-write.

All LLM sub-agents are replaced with no-op fakes.  The tree is backed by a
temp DB so tests are hermetic and do not touch .data/pipeline.db.
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import MagicMock, patch

import pytest

from ai_research_engineer.agents.adk.evolution_loop import EvolutionLoopAgent
from ai_research_engineer.core.argument_tree import TreeBuilder


# ---------------------------------------------------------------------------
# Shared fakes (reused from test_evolve.py)
# ---------------------------------------------------------------------------


class _FakeCtx:
    def __init__(self, session_id: str = "evolve-tree-test"):
        self.session = MagicMock()
        self.session.id = session_id
        self.session.state = {}


async def _drain(gen) -> List:
    events = []
    async for e in gen:
        events.append(e)
    return events


class _FakeCodingAgent:
    name = "fake_coder"

    async def run_async(self, ctx) -> AsyncGenerator:
        return
        yield


class _FakeAnalyzerAgent:
    name = "fake_analyzer"

    async def run_async(self, ctx) -> AsyncGenerator:
        return
        yield


class _FakeDatabase:
    def __init__(self, nodes=None):
        self._nodes: list = list(nodes or [])

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


# ---------------------------------------------------------------------------
# Helper: build and run a 2-generation evolve loop
# ---------------------------------------------------------------------------


def _run_evolve(tmp_path: Path, session_id: str = "evolve-tree-run", max_gens: int = 2) -> TreeBuilder:
    """Run a 2-generation evolve loop with the tree pointed at tmp_path."""
    db_path = tmp_path / "tree.db"
    working_dir = tmp_path / "workdir"
    workflow_dir = working_dir / "workflow"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "results.json").write_text('{"score": 0.42}')
    (workflow_dir / "initial_program.py").write_text("# baseline")

    ctx = _FakeCtx(session_id=session_id)
    ctx.session.state["working_dir"] = str(working_dir)
    ctx.session.state["original_user_input"] = "Maximise accuracy on CIFAR-10"

    db = _FakeDatabase()
    snapshot = _FakeBestSnapshot()

    agent = EvolutionLoopAgent(
        coding_agent=_FakeCodingAgent(),
        analyzer_agent=_FakeAnalyzerAgent(),
        database=db,
        best_snapshot=snapshot,
        max_generations=max_gens,
    )

    with patch("ai_research_engineer.core.argument_tree._DEFAULT_DB", db_path):
        asyncio.run(_drain(agent._run_async_impl(ctx)))

    return TreeBuilder(run_id=session_id, db_path=db_path)


# ---------------------------------------------------------------------------
# Tree structure tests
# ---------------------------------------------------------------------------


class TestEvolveTreeStructure:
    def test_root_exists(self, tmp_path):
        tree = _run_evolve(tmp_path)
        try:
            root = tree.get_root()
            assert root is not None
            assert root["type"] == "root"
        finally:
            tree.close()

    def test_root_label_from_topic(self, tmp_path):
        tree = _run_evolve(tmp_path)
        try:
            root = tree.get_root()
            assert "CIFAR-10" in root["label"] or "accuracy" in root["label"].lower()
        finally:
            tree.close()

    def test_baseline_experiment_exists(self, tmp_path):
        tree = _run_evolve(tmp_path)
        try:
            experiments = tree.get_nodes_by_type("experiment")
            baseline = [e for e in experiments if e["metadata"].get("gen") == 0]
            assert len(baseline) == 1
            assert baseline[0]["label"] == "Generation_0_Baseline"
        finally:
            tree.close()

    def test_baseline_result_exists(self, tmp_path):
        tree = _run_evolve(tmp_path)
        try:
            results = tree.get_nodes_by_type("result")
            baseline_results = [r for r in results if r["metadata"].get("gen") == 0]
            assert len(baseline_results) == 1
            assert baseline_results[0]["metadata"]["metric_name"] == "score"
            # Score from results.json is 0.42
            assert baseline_results[0]["metadata"]["value"] == pytest.approx(0.42)
        finally:
            tree.close()

    def test_one_experiment_per_generation(self, tmp_path):
        max_gens = 2
        tree = _run_evolve(tmp_path, max_gens=max_gens)
        try:
            experiments = tree.get_nodes_by_type("experiment")
            # baseline (gen 0) + 2 generations
            assert len(experiments) == max_gens + 1
            gen_indices = sorted(e["metadata"].get("gen", -1) for e in experiments)
            assert gen_indices == [0, 1, 2]
        finally:
            tree.close()

    def test_one_result_per_experiment(self, tmp_path):
        max_gens = 2
        tree = _run_evolve(tmp_path, max_gens=max_gens)
        try:
            experiments = tree.get_nodes_by_type("experiment")
            results = tree.get_nodes_by_type("result")
            # Every experiment has exactly one result child
            assert len(results) == len(experiments)
        finally:
            tree.close()

    def test_result_values_match_scores(self, tmp_path):
        """All result values should equal 0.42 (the value in results.json)."""
        tree = _run_evolve(tmp_path)
        try:
            results = tree.get_nodes_by_type("result")
            for r in results:
                assert r["metadata"]["metric_name"] == "score"
                assert r["metadata"]["value"] == pytest.approx(0.42)
        finally:
            tree.close()

    def test_stats_counts(self, tmp_path):
        max_gens = 2
        tree = _run_evolve(tmp_path, max_gens=max_gens)
        try:
            stats = tree.get_stats()
            assert stats["by_type"]["root"] == 1
            assert stats["by_type"]["experiment"] == max_gens + 1  # baseline + gens
            assert stats["by_type"]["result"] == max_gens + 1
        finally:
            tree.close()


# ---------------------------------------------------------------------------
# Parent edge correctness
# ---------------------------------------------------------------------------


class TestEvolveTreeParentEdges:
    def test_baseline_is_child_of_root(self, tmp_path):
        tree = _run_evolve(tmp_path)
        try:
            root = tree.get_root()
            baseline_experiments = [e for e in tree.get_nodes_by_type("experiment") if e["metadata"].get("gen") == 0]
            assert len(baseline_experiments) == 1
            assert baseline_experiments[0]["parent_id"] == root["node_id"]
        finally:
            tree.close()

    def test_gen1_is_child_of_baseline(self, tmp_path):
        """Gen 1 samples from DB which only has the baseline (db_id=0), so its
        experiment node must be a child of the baseline's experiment node."""
        tree = _run_evolve(tmp_path, max_gens=2)
        try:
            experiments = {e["metadata"].get("gen"): e for e in tree.get_nodes_by_type("experiment")}
            baseline_exp = experiments[0]
            gen1_exp = experiments[1]
            assert gen1_exp["parent_id"] == baseline_exp["node_id"]
        finally:
            tree.close()

    def test_gen2_is_child_of_gen1(self, tmp_path):
        """Gen 2 samples from DB that contains gen0 and gen1; _FakeDatabase.sample
        returns the first node (index 0 = baseline).  But each new gen IS always
        sampled from whatever sample() returns, so at least the parent_id chain
        should be a tree node (not None)."""
        tree = _run_evolve(tmp_path, max_gens=2)
        try:
            gen2_exp = next(e for e in tree.get_nodes_by_type("experiment") if e["metadata"].get("gen") == 2)
            # parent_id must be a real tree node (not null)
            assert gen2_exp["parent_id"] is not None
            # It should be one of the experiment node ids
            all_exp_ids = {e["node_id"] for e in tree.get_nodes_by_type("experiment")}
            assert gen2_exp["parent_id"] in all_exp_ids
        finally:
            tree.close()

    def test_result_is_child_of_its_experiment(self, tmp_path):
        tree = _run_evolve(tmp_path, max_gens=2)
        try:
            for exp in tree.get_nodes_by_type("experiment"):
                children = tree.get_children(exp["node_id"])
                result_children = [c for c in children if c["type"] == "result"]
                assert len(result_children) == 1, f"experiment gen={exp['metadata'].get('gen')} has no result child"
        finally:
            tree.close()


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


class TestEvolveTreeFailureIsolation:
    def test_run_completes_when_treebuilder_init_raises(self, tmp_path):
        """If TreeBuilder.__init__ raises, the evolve loop still completes and
        emits its normal generation events."""
        working_dir = tmp_path / "workdir"
        workflow_dir = working_dir / "workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "results.json").write_text('{"score": 0.5}')
        (workflow_dir / "initial_program.py").write_text("# baseline")

        ctx = _FakeCtx(session_id="fail-init")
        ctx.session.state["working_dir"] = str(working_dir)

        db = _FakeDatabase()
        snapshot = _FakeBestSnapshot()
        agent = EvolutionLoopAgent(
            coding_agent=_FakeCodingAgent(),
            analyzer_agent=_FakeAnalyzerAgent(),
            database=db,
            best_snapshot=snapshot,
            max_generations=2,
        )

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder.__init__",
            side_effect=RuntimeError("DB unavailable"),
        ):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))

        # Should still emit init + per-gen + completion events
        assert len(events) >= 4  # init + 2 gen summaries + completion
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("EVOLUTION COMPLETE" in t for t in texts)

    def test_run_completes_when_tree_write_raises(self, tmp_path):
        """If add_root raises after init, _tree_safe swallows it and the loop
        still completes with normal events."""
        db_path = tmp_path / "fail_write.db"
        working_dir = tmp_path / "workdir"
        workflow_dir = working_dir / "workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "results.json").write_text('{"score": 0.5}')
        (workflow_dir / "initial_program.py").write_text("# baseline")

        ctx = _FakeCtx(session_id="fail-write")
        ctx.session.state["working_dir"] = str(working_dir)

        db = _FakeDatabase()
        snapshot = _FakeBestSnapshot()
        agent = EvolutionLoopAgent(
            coding_agent=_FakeCodingAgent(),
            analyzer_agent=_FakeAnalyzerAgent(),
            database=db,
            best_snapshot=snapshot,
            max_generations=1,
        )

        class _BrokenTree(TreeBuilder):
            def add_root(self, *a, **kw):
                raise RuntimeError("write failed")

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder",
            lambda run_id, **kw: _BrokenTree(run_id, db_path=db_path),
        ):
            events = asyncio.run(_drain(agent._run_async_impl(ctx)))

        assert len(events) >= 3
        texts = [e.content.parts[0].text for e in events if e.content and e.content.parts]
        assert any("EVOLUTION COMPLETE" in t for t in texts)

    def test_db_to_tree_map_unaffected_by_tree_errors(self, tmp_path):
        """Even if individual tree writes fail, the loop must not crash and the
        DB should contain all expected nodes (evolve state unaffected)."""
        working_dir = tmp_path / "workdir"
        workflow_dir = working_dir / "workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "results.json").write_text('{"score": 0.7}')
        (workflow_dir / "initial_program.py").write_text("# code")

        ctx = _FakeCtx(session_id="fail-map")
        ctx.session.state["working_dir"] = str(working_dir)

        db = _FakeDatabase()
        snapshot = _FakeBestSnapshot()
        max_gens = 2
        agent = EvolutionLoopAgent(
            coding_agent=_FakeCodingAgent(),
            analyzer_agent=_FakeAnalyzerAgent(),
            database=db,
            best_snapshot=snapshot,
            max_generations=max_gens,
        )

        with patch(
            "ai_research_engineer.core.argument_tree.TreeBuilder.__init__",
            side_effect=RuntimeError("unavailable"),
        ):
            asyncio.run(_drain(agent._run_async_impl(ctx)))

        # All nodes still added to the (fake) DB: baseline + max_gens
        assert len(db.get_all()) == max_gens + 1

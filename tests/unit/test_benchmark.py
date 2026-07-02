"""
Unit tests for the cost benchmark harness.

All tests are offline — no network calls, no API keys required.
The mock engine (_FakeEngine) is used throughout.
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

import pytest

from ai_research_engineer.core.pricing import cost_usd
from benchmarks.cost.report import write_csv, write_markdown
from benchmarks.cost.run_benchmark import (
    BenchmarkCell,
    RunResult,
    _FakeEngine,
    _mode_to_agent,
    expand_matrix,
    load_suite,
    run_all,
    run_cell,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_TASK_SUITE = {
    "tasks": [
        {"id": "t1", "topic": "test topic one", "mode": "novel", "domain": "aiml"},
        {"id": "t2", "topic": "test topic two", "mode": "replication", "domain": "aiml"},
    ],
    "defaults": {"repetitions": 1},
}

_THREE_TASK_SUITE = {
    "tasks": [
        {"id": "t1", "topic": "topic1", "mode": "novel", "domain": "aiml"},
        {"id": "t2", "topic": "topic2", "mode": "replication", "domain": "aiml"},
        {"id": "t3", "topic": "topic3", "mode": "evolve", "domain": "aiml"},
    ],
    "defaults": {"repetitions": 1},
}


# ---------------------------------------------------------------------------
# Mode mapping
# ---------------------------------------------------------------------------


class TestModeMapping:
    def test_novel_maps_correctly(self):
        agent_type, research_mode = _mode_to_agent("novel")
        assert agent_type == "adk"
        assert research_mode == "novelty"

    def test_replication_maps_correctly(self):
        agent_type, research_mode = _mode_to_agent("replication")
        assert agent_type == "adk"
        assert research_mode == "replication"

    def test_evolve_maps_correctly(self):
        agent_type, research_mode = _mode_to_agent("evolve")
        assert agent_type == "evolve"
        assert research_mode == "evolve"

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown task mode"):
            _mode_to_agent("imaginary_mode")


# ---------------------------------------------------------------------------
# Matrix expansion
# ---------------------------------------------------------------------------


class TestMatrixExpansion:
    def test_two_tasks_one_rep_default_engine(self):
        cells = expand_matrix(_TWO_TASK_SUITE)
        assert len(cells) == 2
        assert {c.task_id for c in cells} == {"t1", "t2"}
        assert all(c.engine == "default" for c in cells)
        assert all(c.graphify is False for c in cells)
        assert all(c.rep == 1 for c in cells)

    def test_two_tasks_two_reps(self):
        suite = dict(_TWO_TASK_SUITE)
        suite["defaults"] = {"repetitions": 2}
        cells = expand_matrix(suite)
        assert len(cells) == 4
        t1_reps = {c.rep for c in cells if c.task_id == "t1"}
        assert t1_reps == {1, 2}

    def test_mock_engine_in_matrix(self):
        cells = expand_matrix(_TWO_TASK_SUITE, engines=["mock"])
        assert len(cells) == 2
        assert all(c.engine == "mock" for c in cells)

    def test_graphify_on_and_off_both_produce_cells(self):
        cells = expand_matrix(_TWO_TASK_SUITE, graphify_values=[False, True])
        # Both graphify values are available → 2 tasks × 2 graphify = 4 cells
        graphify_vals = {c.graphify for c in cells}
        assert True in graphify_vals
        assert False in graphify_vals
        assert len(cells) == 4

    def test_unknown_engine_is_skipped(self):
        cells = expand_matrix(_TWO_TASK_SUITE, engines=["default", "graphify_engine_v2"])
        # "graphify_engine_v2" is not in AVAILABLE_ENGINES → skipped
        assert all(c.engine == "default" for c in cells)
        assert len(cells) == 2

    def test_both_graphify_flags_produce_double_cells(self):
        cells = expand_matrix(_THREE_TASK_SUITE, graphify_values=[True, False])
        # Both values active → 3 tasks × 2 graphify values = 6 cells
        assert len(cells) == 6
        graphify_vals = {c.graphify for c in cells}
        assert graphify_vals == {True, False}

    def test_cell_agent_type_derived_from_mode(self):
        cells = expand_matrix(_THREE_TASK_SUITE, engines=["mock"])
        by_task = {c.task_id: c for c in cells}
        assert by_task["t1"].agent_type == "adk"
        assert by_task["t1"].research_mode == "novelty"
        assert by_task["t2"].agent_type == "adk"
        assert by_task["t2"].research_mode == "replication"
        assert by_task["t3"].agent_type == "evolve"
        assert by_task["t3"].research_mode == "evolve"

    def test_empty_suite_produces_no_cells(self):
        cells = expand_matrix({"tasks": [], "defaults": {}})
        assert cells == []


# ---------------------------------------------------------------------------
# Fake engine behaviour
# ---------------------------------------------------------------------------


class TestFakeEngine:
    async def _collect(self, topic="test topic"):
        engine = _FakeEngine()
        gen = await engine.run_async(topic, stream=True)
        return [e async for e in gen]

    def test_yields_usage_event(self):
        events = asyncio.run(self._collect())
        types = [e["type"] for e in events]
        assert "usage" in types
        assert "completed" in types

    def test_usage_event_has_expected_fields(self):
        events = asyncio.run(self._collect("x"))
        usage_events = [e for e in events if e.get("type") == "usage"]
        assert len(usage_events) == 1
        u = usage_events[0]["usage"]
        assert u["input_tokens"] == _FakeEngine._INPUT_TOKENS
        assert u["cached_input_tokens"] == _FakeEngine._CACHED_TOKENS
        assert u["output_tokens"] == _FakeEngine._OUTPUT_TOKENS
        assert usage_events[0]["model"] == _FakeEngine._MODEL

    def test_known_cost_from_fake_engine(self):
        # Verify that the FakeEngine's canned tokens yield a known cost.
        model = _FakeEngine._MODEL
        inp = _FakeEngine._INPUT_TOKENS
        cac = _FakeEngine._CACHED_TOKENS
        out = _FakeEngine._OUTPUT_TOKENS
        c = cost_usd(model, inp, out, cac)
        assert c > 0.0

        # Cross-check arithmetic: claude-sonnet-4-6 $3/MTok input, $0.30 cached, $15 output
        non_cached = inp - cac  # 900
        expected = non_cached / 1_000_000 * 3.0 + cac / 1_000_000 * 0.30 + out / 1_000_000 * 15.0
        assert abs(c - expected) < 1e-9


# ---------------------------------------------------------------------------
# run_cell
# ---------------------------------------------------------------------------


class TestRunCell:
    def _make_cell(self, task_id="t1", rep=1) -> BenchmarkCell:
        return BenchmarkCell(
            task_id=task_id,
            topic="test topic",
            mode="novel",
            domain="aiml",
            engine="mock",
            graphify=False,
            rep=rep,
            agent_type="adk",
            research_mode="novelty",
        )

    def test_run_cell_returns_result(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        assert isinstance(result, RunResult)

    def test_llm_calls_counted(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        assert result.llm_calls == 1

    def test_token_counts_match_fake_engine(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        assert result.input_tokens == _FakeEngine._INPUT_TOKENS
        assert result.cached_tokens == _FakeEngine._CACHED_TOKENS
        assert result.output_tokens == _FakeEngine._OUTPUT_TOKENS

    def test_cost_computed_via_pricing(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        expected = cost_usd(
            _FakeEngine._MODEL,
            _FakeEngine._INPUT_TOKENS,
            _FakeEngine._OUTPUT_TOKENS,
            _FakeEngine._CACHED_TOKENS,
        )
        assert abs(result.cost_usd - expected) < 1e-9

    def test_success_from_completed_event(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        # FakeEngine yields files_created=["mock_output.txt"]
        assert result.success is True

    def test_model_captured(self, tmp_path):
        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _FakeEngine, tmp_path))
        assert result.model == _FakeEngine._MODEL

    def test_cell_failure_is_isolated(self, tmp_path):
        class _BrokenEngine:
            def __init__(self, **kw):
                pass

            async def run_async(self, topic, stream=True):
                async def _gen():
                    raise RuntimeError("boom")
                    yield  # unreachable but marks as async generator

                return _gen()

        cell = self._make_cell()
        result = asyncio.run(run_cell(cell, _BrokenEngine, tmp_path))
        assert result.success is False
        assert "boom" in result.notes


# ---------------------------------------------------------------------------
# run_all with guards
# ---------------------------------------------------------------------------


class TestRunAllGuards:
    def _cells(self, n: int = 3) -> list:
        suite = {
            "tasks": [{"id": f"t{i}", "topic": f"topic{i}", "mode": "novel", "domain": "aiml"} for i in range(n)],
            "defaults": {"repetitions": 1},
        }
        return expand_matrix(suite, engines=["mock"])

    def test_runs_all_cells_by_default(self, tmp_path):
        cells = self._cells(3)
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path))
        assert len(results) == 3

    def test_max_runs_caps_execution(self, tmp_path):
        cells = self._cells(4)
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path, max_runs=2))
        assert len(results) == 2

    def test_max_runs_zero_produces_no_results(self, tmp_path):
        cells = self._cells(3)
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path, max_runs=0))
        assert results == []

    def test_budget_stops_before_exceeding(self, tmp_path):
        # Guard semantics: budget is checked BEFORE each run using the accumulated
        # cost from prior runs.  After the first run total == 1×cell_cost.
        # Setting budget to 0.5× means the second run is blocked (1× >= 0.5×).
        one_cell_cost = cost_usd(
            _FakeEngine._MODEL,
            _FakeEngine._INPUT_TOKENS,
            _FakeEngine._OUTPUT_TOKENS,
            _FakeEngine._CACHED_TOKENS,
        )
        cells = self._cells(4)
        budget = one_cell_cost * 0.5  # less than 1 full run's cost
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path, budget_usd=budget))
        assert len(results) == 1

    def test_budget_larger_than_total_allows_all(self, tmp_path):
        one_cell_cost = cost_usd(
            _FakeEngine._MODEL,
            _FakeEngine._INPUT_TOKENS,
            _FakeEngine._OUTPUT_TOKENS,
            _FakeEngine._CACHED_TOKENS,
        )
        cells = self._cells(2)
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path, budget_usd=one_cell_cost * 10))
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Dry-run end-to-end: CSV + Markdown produced, totals correct
# ---------------------------------------------------------------------------


class TestDryRunEndToEnd:
    def _run_suite(self, tmp_path: Path, n_tasks: int = 2, n_reps: int = 1):
        suite = {
            "tasks": [
                {"id": f"t{i}", "topic": f"topic {i}", "mode": "novel", "domain": "aiml"} for i in range(n_tasks)
            ],
            "defaults": {"repetitions": n_reps},
        }
        cells = expand_matrix(suite, engines=["mock"])
        results = asyncio.run(run_all(cells, _FakeEngine, tmp_path))
        return results

    def test_csv_is_created(self, tmp_path):
        results = self._run_suite(tmp_path)
        csv_path = tmp_path / "raw.csv"
        write_csv(results, csv_path)
        assert csv_path.exists()

    def test_csv_has_correct_row_count(self, tmp_path):
        results = self._run_suite(tmp_path, n_tasks=2, n_reps=1)
        csv_path = tmp_path / "raw.csv"
        write_csv(results, csv_path)
        with csv_path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_csv_contains_expected_task_ids(self, tmp_path):
        results = self._run_suite(tmp_path, n_tasks=2)
        csv_path = tmp_path / "raw.csv"
        write_csv(results, csv_path)
        content = csv_path.read_text()
        assert "t0" in content
        assert "t1" in content

    def test_markdown_is_created(self, tmp_path):
        results = self._run_suite(tmp_path)
        md_path = tmp_path / "report.md"
        write_markdown(results, md_path)
        assert md_path.exists()

    def test_markdown_contains_cost_header(self, tmp_path):
        results = self._run_suite(tmp_path)
        md_path = tmp_path / "report.md"
        write_markdown(results, md_path)
        content = md_path.read_text()
        assert "Cost Benchmark Report" in content
        assert "cost_usd" in content

    def test_total_cost_is_sum_of_cell_costs(self, tmp_path):
        results = self._run_suite(tmp_path, n_tasks=3)
        per_cell = cost_usd(
            _FakeEngine._MODEL,
            _FakeEngine._INPUT_TOKENS,
            _FakeEngine._OUTPUT_TOKENS,
            _FakeEngine._CACHED_TOKENS,
        )
        total = sum(r.cost_usd for r in results)
        assert abs(total - per_cell * 3) < 1e-9

    def test_repetitions_scale_total_cost(self, tmp_path):
        results_1 = self._run_suite(tmp_path / "r1", n_tasks=1, n_reps=1)
        results_3 = self._run_suite(tmp_path / "r3", n_tasks=1, n_reps=3)
        total_1 = sum(r.cost_usd for r in results_1)
        total_3 = sum(r.cost_usd for r in results_3)
        assert abs(total_3 - total_1 * 3) < 1e-9


# ---------------------------------------------------------------------------
# Suite loading from disk
# ---------------------------------------------------------------------------


class TestSuiteLoading:
    def test_loads_builtin_suite(self):
        from benchmarks.cost.run_benchmark import _DEFAULT_SUITE

        suite = load_suite(_DEFAULT_SUITE)
        assert "tasks" in suite
        assert len(suite["tasks"]) >= 1

    def test_builtin_suite_has_required_fields(self):
        from benchmarks.cost.run_benchmark import _DEFAULT_SUITE

        suite = load_suite(_DEFAULT_SUITE)
        for t in suite["tasks"]:
            assert "id" in t
            assert "topic" in t
            assert "mode" in t

    def test_invalid_suite_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not_a_dict: true\n")
        with pytest.raises(ValueError, match="Invalid suite file"):
            load_suite(bad)

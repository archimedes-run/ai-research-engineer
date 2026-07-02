"""
Cost benchmark harness for AI Research Engineer.

Building and testing this module requires NO API spend — use --dry-run.
Real sweeps are guarded by --max-runs / --budget-usd and require --yes.

Usage:
    # Offline smoke test (no API keys needed):
    python benchmarks/cost/run_benchmark.py --dry-run --yes

    # Real sweep (consumes API credits — requires --yes):
    python benchmarks/cost/run_benchmark.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List, Optional, Tuple


# Ensure the repo root is on sys.path so this script can be run directly
# (uv run python benchmarks/cost/run_benchmark.py) as well as imported.
_repo_root = str(Path(__file__).parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import yaml  # noqa: E402


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]
_DEFAULT_SUITE = Path(__file__).parent / "suite.yaml"
_DEFAULT_OUT_DIR = Path(__file__).parent / "out"

# Engine names that are implemented today.
_AVAILABLE_ENGINES: frozenset[str] = frozenset({"default", "mock"})
# Graphify values that are implemented today.
_AVAILABLE_GRAPHIFY: frozenset[bool] = frozenset({False, True})


# ---------------------------------------------------------------------------
# Mode → agent mapping
# ---------------------------------------------------------------------------

_MODE_MAP: Dict[str, Tuple[str, str]] = {
    "novel": ("adk", "novelty"),
    "replication": ("adk", "replication"),
    "evolve": ("evolve", "evolve"),
}


def _mode_to_agent(mode: str) -> Tuple[str, str]:
    """Return (agent_type, research_mode) for a task mode string."""
    if mode not in _MODE_MAP:
        raise ValueError(f"Unknown task mode {mode!r}. Valid: {sorted(_MODE_MAP)}")
    return _MODE_MAP[mode]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TaskSpec:
    id: str
    topic: str
    mode: str
    domain: str = "aiml"


@dataclass
class BenchmarkCell:
    task_id: str
    topic: str
    mode: str
    domain: str
    engine: str
    graphify: bool
    rep: int
    agent_type: str
    research_mode: str


@dataclass
class RunResult:
    task_id: str
    mode: str
    engine: str
    model: Optional[str]
    graphify: bool
    rep: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    cost_usd: float
    llm_calls: int
    wall_seconds: float
    success: Optional[bool]
    notes: str = ""

    def as_dict(self) -> Dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# ---------------------------------------------------------------------------
# Suite loading
# ---------------------------------------------------------------------------


def load_suite(path: Path = _DEFAULT_SUITE) -> dict:
    """Load and parse a YAML task suite file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "tasks" not in data:
        raise ValueError(f"Invalid suite file: {path}")
    return data


def _parse_tasks(suite: dict) -> List[TaskSpec]:
    tasks = []
    for t in suite.get("tasks", []):
        tasks.append(
            TaskSpec(
                id=t["id"],
                topic=str(t["topic"]).strip(),
                mode=t["mode"],
                domain=t.get("domain", "aiml"),
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Matrix expansion
# ---------------------------------------------------------------------------


def expand_matrix(
    suite: dict,
    graphify_values: Optional[List[bool]] = None,
    engines: Optional[List[str]] = None,
) -> List[BenchmarkCell]:
    """
    Expand the task suite into a flat list of BenchmarkCells.

    Cells for unavailable engines or graphify values are silently skipped
    (a WARNING is logged) so the harness never crashes on reserved dimensions.

    Parameters
    ----------
    suite:
        Parsed suite dict (output of load_suite()).
    graphify_values:
        List of graphify flags to include. Defaults to [False].
        True is reserved for Phase H-Graphify; those cells are skipped today.
    engines:
        List of engine names to include. Defaults to ["default"].
        Unknown engine names are skipped; "mock" is always available.
    """
    if graphify_values is None:
        graphify_values = [False]
    if engines is None:
        engines = ["default"]

    defaults = suite.get("defaults", {})
    repetitions = int(defaults.get("repetitions", 1))

    tasks = _parse_tasks(suite)
    cells: List[BenchmarkCell] = []

    for graphify in graphify_values:
        if graphify not in _AVAILABLE_GRAPHIFY:
            logger.warning("graphify=%r is not yet available — skipping those cells.", graphify)
            continue

        for engine in engines:
            if engine not in _AVAILABLE_ENGINES:
                logger.warning("engine=%r is not yet available — skipping those cells.", engine)
                continue

            for task in tasks:
                agent_type, research_mode = _mode_to_agent(task.mode)
                for rep in range(1, repetitions + 1):
                    cells.append(
                        BenchmarkCell(
                            task_id=task.id,
                            topic=task.topic,
                            mode=task.mode,
                            domain=task.domain,
                            engine=engine,
                            graphify=graphify,
                            rep=rep,
                            agent_type=agent_type,
                            research_mode=research_mode,
                        )
                    )

    return cells


# ---------------------------------------------------------------------------
# Fake / mock engine (used for --dry-run and tests)
# ---------------------------------------------------------------------------


class _FakeEngine:
    """
    Drop-in replacement for AIEngineer that yields a canned event stream.

    No network calls are made; all token counts are deterministic so tests
    can assert exact cost values using core.pricing.
    """

    # Canned usage: claude-sonnet-4-6 @ 1 000 input / 100 cached / 200 output
    _MODEL = "claude-sonnet-4-6"
    _INPUT_TOKENS = 1_000
    _CACHED_TOKENS = 100
    _OUTPUT_TOKENS = 200

    def __init__(
        self,
        agent_type: str = "adk",
        working_dir: str = ".",
        research_mode: str = "novelty",
        domain: str = "aiml",
        use_graphify: bool = False,
        **_kw,
    ):
        self._working_dir = Path(working_dir)

    async def run_async(self, topic: str, stream: bool = True) -> AsyncGenerator[dict, None]:
        """Return an async generator that yields canned events — mirrors AIEngineer.run_async."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        model = self._MODEL
        inp = self._INPUT_TOKENS
        cac = self._CACHED_TOKENS
        out = self._OUTPUT_TOKENS

        async def _gen() -> AsyncGenerator[dict, None]:
            yield {
                "type": "message",
                "content": f"[mock] Processing: {topic[:60]}",
                "author": "mock_agent",
                "timestamp": ts,
            }
            yield {
                "type": "usage",
                "model": model,
                "usage": {
                    "input_tokens": inp,
                    "cached_input_tokens": cac,
                    "output_tokens": out,
                },
                "timestamp": ts,
            }
            yield {
                "type": "completed",
                "session_id": "mock-session",
                "duration": 0.01,
                "total_events": 2,
                "files_created": ["mock_output.txt"],
                "files_count": 1,
                "timestamp": ts,
            }

        return _gen()


def _engine_factory(engine_name: str) -> Callable:
    """Return the engine class for a given engine name."""
    if engine_name == "mock":
        return _FakeEngine
    if engine_name == "default":
        from ai_research_engineer.core.api import AIEngineer  # noqa: PLC0415

        return AIEngineer
    raise ValueError(f"Unknown engine: {engine_name!r}")


# ---------------------------------------------------------------------------
# Cell runner
# ---------------------------------------------------------------------------


async def run_cell(cell: BenchmarkCell, engine_class: Callable, work_base: Path) -> RunResult:
    """Run a single benchmark cell and return its result."""
    from ai_research_engineer.core.pricing import cost_usd as _cost_usd  # noqa: PLC0415

    work_dir = work_base / f"{cell.task_id}_rep{cell.rep}"
    work_dir.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    input_tokens = cached_tokens = output_tokens = llm_calls = 0
    total_cost = 0.0
    model_seen: Optional[str] = None
    success: Optional[bool] = None
    notes = ""

    try:
        engine = engine_class(
            agent_type=cell.agent_type,
            working_dir=str(work_dir),
            research_mode=cell.research_mode,
            domain=cell.domain,
            use_graphify=cell.graphify,
        )
        gen = await engine.run_async(cell.topic, stream=True)
        async for event in gen:
            etype = event.get("type")
            if etype == "usage":
                llm_calls += 1
                model = event.get("model")
                if model and model_seen is None:
                    model_seen = model
                u = event.get("usage", {})
                inp = int(u.get("input_tokens", 0) or 0)
                cac = int(u.get("cached_input_tokens", 0) or 0)
                out = int(u.get("output_tokens", 0) or 0)
                input_tokens += inp
                cached_tokens += cac
                output_tokens += out
                total_cost += _cost_usd(model, inp, out, cac)

            elif etype == "completed":
                files = event.get("files_created", [])
                success = bool(files)

            elif etype == "error":
                notes = event.get("content", "unknown error")
                success = False

    except Exception as exc:
        notes = f"{type(exc).__name__}: {exc}"
        success = False
        logger.error("Cell %s rep=%d failed: %s", cell.task_id, cell.rep, exc)

    wall_seconds = time.monotonic() - start

    return RunResult(
        task_id=cell.task_id,
        mode=cell.mode,
        engine=cell.engine,
        model=model_seen,
        graphify=cell.graphify,
        rep=cell.rep,
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_usd=total_cost,
        llm_calls=llm_calls,
        wall_seconds=wall_seconds,
        success=success,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Batch runner with guards
# ---------------------------------------------------------------------------


async def run_all(
    cells: List[BenchmarkCell],
    engine_class: Callable,
    work_base: Path,
    max_runs: Optional[int] = None,
    budget_usd: Optional[float] = None,
) -> List[RunResult]:
    """
    Execute *cells* sequentially, respecting max_runs and budget_usd guards.

    Guards are checked BEFORE each run:
    - max_runs: hard cap on number of cells executed.
    - budget_usd: stop if accumulated cost has already reached/exceeded the
      budget (so the guard fires before the NEXT run would push over the limit).
    """
    results: List[RunResult] = []
    total_cost = 0.0

    for i, cell in enumerate(cells):
        if max_runs is not None and i >= max_runs:
            logger.info("--max-runs %d reached; %d remaining cell(s) skipped.", max_runs, len(cells) - i)
            break
        if budget_usd is not None and total_cost >= budget_usd:
            logger.info(
                "--budget-usd %.6f reached (accumulated %.6f); %d cell(s) skipped.",
                budget_usd,
                total_cost,
                len(cells) - i,
            )
            break

        logger.info(
            "[%d/%d] Running %s engine=%s graphify=%s rep=%d …",
            i + 1,
            len(cells),
            cell.task_id,
            cell.engine,
            cell.graphify,
            cell.rep,
        )
        result = await run_cell(cell, engine_class, work_base)
        results.append(result)
        total_cost += result.cost_usd
        logger.info(
            "  → cost=%.6f usd  input=%d  output=%d  llm_calls=%d  wall=%.1fs  success=%s",
            result.cost_usd,
            result.input_tokens,
            result.output_tokens,
            result.llm_calls,
            result.wall_seconds,
            result.success,
        )

    return results


# ---------------------------------------------------------------------------
# Cost estimate (pre-flight)
# ---------------------------------------------------------------------------


def _estimate_cost(cells: List[BenchmarkCell]) -> str:
    """Return a human-readable cost estimate string (very rough)."""
    # We have no prior data so we give a token-count-based estimate only if
    # the engine is real. For the default engine we can only say "unknown".
    real_cells = [c for c in cells if c.engine != "mock"]
    if not real_cells:
        return "0.00 (mock only)"
    n = len(real_cells)
    return f"unknown for {n} real cell(s) — depends on topic length and agent behaviour"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Cost benchmark harness for AI Research Engineer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--suite", type=Path, default=_DEFAULT_SUITE, help="Path to suite.yaml (default: built-in suite)")
    p.add_argument(
        "--engine",
        nargs="+",
        default=["default"],
        metavar="ENGINE",
        help="Engine(s) to benchmark. 'mock' uses a fake engine (no API). Default: default",
    )
    p.add_argument(
        "--graphify",
        nargs="+",
        type=lambda s: s.lower() == "on",
        default=[False],
        metavar="{off,on}",
        help="Graphify setting(s). 'on' is reserved (cells skipped). Default: off",
    )
    p.add_argument("--max-runs", type=int, default=None, help="Hard cap on cells executed.")
    p.add_argument("--budget-usd", type=float, default=None, help="Stop when accumulated cost reaches this value.")
    p.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR, help="Directory for CSV/Markdown output.")
    p.add_argument("--dry-run", action="store_true", help="Use mock engine; skip confirmation prompt.")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt for real runs.")
    return p


async def _async_main(argv: Optional[List[str]] = None) -> int:
    from benchmarks.cost.report import write_csv, write_markdown  # noqa: PLC0415

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = _build_parser()
    args = parser.parse_args(argv)

    # --dry-run implies mock engine
    engines = args.engine
    if args.dry_run:
        engines = ["mock"]
        logger.info("--dry-run: forcing engine=mock")

    suite = load_suite(args.suite)
    cells = expand_matrix(suite, graphify_values=args.graphify, engines=engines)

    if not cells:
        logger.error("No cells to run — check suite and engine/graphify settings.")
        return 1

    print(f"\nBenchmark matrix: {len(cells)} cell(s)")
    for c in cells:
        print(f"  {c.task_id}  engine={c.engine}  graphify={c.graphify}  rep={c.rep}")

    if not args.dry_run:
        estimate = _estimate_cost(cells)
        print(f"\nEstimated cost: {estimate}")
        if not args.yes:
            reply = input("\nProceed with real API calls? [y/N] ").strip().lower()
            if reply != "y":
                print("Aborted.")
                return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_base = args.out_dir / f"runs_{ts}"
    work_base.mkdir(parents=True, exist_ok=True)

    # Build engine factory
    if args.dry_run or engines == ["mock"]:
        engine_class = _FakeEngine
    else:
        engine_class = _engine_factory(engines[0]) if len(engines) == 1 else _engine_factory("default")

    results = await run_all(
        cells,
        engine_class,
        work_base,
        max_runs=args.max_runs,
        budget_usd=args.budget_usd,
    )

    if not results:
        logger.warning("No results collected.")
        return 1

    csv_path = args.out_dir / f"raw_{ts}.csv"
    md_path = args.out_dir / f"report_{ts}.md"

    write_csv(results, csv_path)
    write_markdown(results, md_path)

    total_cost = sum(r.cost_usd for r in results)
    print(f"\n{'=' * 60}")
    print(f"Completed {len(results)} run(s).")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"CSV:        {csv_path}")
    print(f"Report:     {md_path}")

    return 0


def main(argv: Optional[List[str]] = None) -> None:
    sys.exit(asyncio.run(_async_main(argv)))


if __name__ == "__main__":
    main()

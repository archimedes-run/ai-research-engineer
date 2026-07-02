"""
Graphify integration — optional token-reduction layer.

All public functions are fail-soft: errors are logged at WARNING level and
never propagate to callers. The graphify package (pip: graphifyy) is optional;
import it only when graphify_available() returns True.
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

_TIMEOUT_BUILD = 120  # seconds — code-only, no LLM
_TIMEOUT_QUERY = 30   # seconds — subprocess query


def graphify_available() -> bool:
    """Return True if the graphify package is importable."""
    return importlib.util.find_spec("graphify") is not None


def ensure_graph(working_dir: Path, update: bool = True) -> Optional[Path]:  # noqa: ARG001
    """
    Build (or refresh) a code-structure graph for working_dir.

    Calls graphify.watch._rebuild_code — code-only, no LLM passes.
    Writes working_dir/graphify-out/graph.json.

    Returns the Path to graph.json on success, None on any failure.
    The `update` parameter is accepted for API symmetry but ignored
    (rebuild always starts from scratch).
    """
    if not graphify_available():
        logger.warning("[graphify] package not installed — skipping ensure_graph")
        return None
    try:
        import inspect

        from graphify.watch import _rebuild_code  # type: ignore[import-not-found]

        working_dir = Path(working_dir)
        result = _rebuild_code(working_dir)
        # _rebuild_code may be sync or async depending on the installed version
        if inspect.iscoroutine(result):
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(result)
            finally:
                loop.close()

        graph_path = working_dir / "graphify-out" / "graph.json"
        if graph_path.exists():
            logger.info("[graphify] Graph built at %s", graph_path)
            return graph_path
        logger.warning("[graphify] ensure_graph: graph.json not found after build at %s", graph_path)
        return None
    except Exception as exc:
        logger.warning("[graphify] ensure_graph failed: %s", exc)
        return None


def query_graph(working_dir: Path, question: str, budget: int = 1500) -> Optional[str]:
    """
    Query the code-structure graph via the graphify CLI.

    Runs `python -m graphify query <question> --graph <path> --budget <n>`
    in a subprocess. Returns stdout on success, None on any failure.
    """
    if not graphify_available():
        logger.warning("[graphify] package not installed — skipping query_graph")
        return None
    try:
        working_dir = Path(working_dir)
        graph_path = working_dir / "graphify-out" / "graph.json"
        if not graph_path.exists():
            logger.warning("[graphify] query_graph: no graph at %s — call ensure_graph first", graph_path)
            return None

        proc = subprocess.run(
            [
                "python", "-m", "graphify", "query",
                question,
                "--graph", str(graph_path),
                "--budget", str(budget),
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_QUERY,
        )
        if proc.returncode != 0:
            logger.warning(
                "[graphify] query failed (exit %d): %s",
                proc.returncode,
                proc.stderr[:500],
            )
            return None
        return proc.stdout.strip() or None
    except Exception as exc:
        logger.warning("[graphify] query_graph failed: %s", exc)
        return None

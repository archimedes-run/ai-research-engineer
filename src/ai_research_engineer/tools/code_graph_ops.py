"""
Code Graph operations for the AI Research Engineer using Graphify.

Builds and queries a codebase knowledge graph for large token reduction and
semantic structure. The graph is built through the graphify Python API
(``core.graphify.ensure_graph`` → ``graphify.watch._rebuild_code``) and queried
through the ``graphify`` CLI invoked as ``python -m graphify`` so it works
regardless of whether the console script is on PATH.

All functions are fail-soft: if graphify is unavailable or errors, they return a
short, non-blocking note telling the agent to fall back to Read/Grep — they never
raise, so a missing graph can never deadlock the review/coding loop.
"""

import logging
import subprocess
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

_QUERY_TIMEOUT = 45  # seconds


def _graph_json(repo_root: str) -> Path:
    return Path(repo_root) / "graphify-out" / "graph.json"


def _run_graphify(args: list[str], repo_root: str) -> subprocess.CompletedProcess:
    """Invoke graphify via `python -m graphify` (PATH-independent)."""
    return subprocess.run(
        [sys.executable, "-m", "graphify", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_QUERY_TIMEOUT,
    )


def build_knowledge_graph(repo_root: str) -> str:
    """
    Build or refresh the Graphify knowledge graph for the codebase.

    Run this at the start of a coding stage and again after writing/editing code
    so the graph reflects the latest structure. Uses the graphify Python API,
    which writes graphify-out/{graph.json,GRAPH_REPORT.md}.
    """
    logger.info("[Tool:build_knowledge_graph] Building graph for %s", repo_root)
    try:
        from ai_research_engineer.core.graphify import ensure_graph, graphify_available

        if not graphify_available():
            return (
                "Graphify is not installed in this environment, so no code graph is "
                "available. Proceed using the read_file / search_files tools instead."
            )

        graph_path = ensure_graph(Path(repo_root))
        if graph_path is None:
            return (
                "Could not build the code graph (empty workspace or build error). "
                "Proceed using read_file / search_files; retry build_knowledge_graph "
                "after more code has been written."
            )

        report = Path(repo_root) / "graphify-out" / "GRAPH_REPORT.md"
        if report.exists():
            return (
                "Graph built successfully. Read 'graphify-out/GRAPH_REPORT.md' with "
                "read_file for the high-level architecture overview, then use "
                "get_code_context / search_code_semantically to navigate."
            )
        return "Graph built successfully (graph.json written)."
    except Exception as e:  # fail-soft — never block the loop
        logger.warning("[Tool:build_knowledge_graph] failed: %s", e)
        return (
            f"Code graph unavailable ({e}). Proceed using read_file / search_files "
            "instead — this is non-blocking."
        )


def get_code_context(task: str, repo_root: str) -> str:
    """Use Graphify to explain a specific architecture, task, or module."""
    logger.info("[Tool:get_code_context] Task: %s", task)
    try:
        graph = _graph_json(repo_root)
        if not graph.exists():
            return "No code graph yet — run build_knowledge_graph first, or use read_file/search_files."
        result = _run_graphify(["explain", task, "--graph", str(graph)], repo_root)
        if result.returncode == 0:
            return result.stdout or "No matching nodes found."
        return f"Code graph explain unavailable (non-blocking): {result.stderr[:300]}. Use read_file/search_files."
    except Exception as e:
        logger.warning("[Tool:get_code_context] failed: %s", e)
        return f"Code graph unavailable ({e}). Use read_file/search_files — non-blocking."


def get_code_blast_radius(changed_files: list[str], repo_root: str) -> str:
    """Analyze the blast radius of specific files using Graphify's DFS trace."""
    logger.info("[Tool:get_code_blast_radius] Files: %s", changed_files)
    try:
        graph = _graph_json(repo_root)
        if not graph.exists():
            return "No code graph yet — run build_knowledge_graph first, or use read_file/search_files."
        target = changed_files[0] if isinstance(changed_files, list) and changed_files else str(changed_files)
        result = _run_graphify(
            ["query", f"what depends on or connects to {target}?", "--dfs", "--graph", str(graph)],
            repo_root,
        )
        if result.returncode == 0:
            output = result.stdout or "No matching nodes found."
            return output[:10000] + "\n\n...[TRUNCATED TO SAVE TOKENS]..." if len(output) > 10000 else output
        return f"Blast-radius query unavailable (non-blocking): {result.stderr[:300]}."
    except Exception as e:
        logger.warning("[Tool:get_code_blast_radius] failed: %s", e)
        return f"Code graph unavailable ({e}). Use read_file/search_files — non-blocking."


def query_code_structure(pattern: str, target: str, repo_root: str) -> str:
    """
    Find the structural relationship between nodes in the codebase.
    (e.g., pattern="Path between", target="ModuleA and ModuleB")
    """
    logger.info("[Tool:query_code_structure] Path trace for %s", target)
    try:
        graph = _graph_json(repo_root)
        if not graph.exists():
            return "No code graph yet — run build_knowledge_graph first, or use read_file/search_files."
        if " and " in target.lower():
            a, b = (s.strip() for s in target.lower().split(" and ", 1))
            args = ["path", a, b, "--graph", str(graph)]
        else:
            args = ["query", f"Show structure of {target}", "--graph", str(graph)]
        result = _run_graphify(args, repo_root)
        if result.returncode == 0:
            return result.stdout or "No matching nodes found."
        return f"Structure query unavailable (non-blocking): {result.stderr[:300]}."
    except Exception as e:
        logger.warning("[Tool:query_code_structure] failed: %s", e)
        return f"Code graph unavailable ({e}). Use read_file/search_files — non-blocking."


def search_code_semantically(query: str, repo_root: str) -> str:
    """Query the Graphify graph with natural language for structural/semantic relations."""
    logger.info("[Tool:search_code_semantically] Query: %s", query)
    try:
        graph = _graph_json(repo_root)
        if not graph.exists():
            return "No code graph yet — run build_knowledge_graph first, or use read_file/search_files."
        result = _run_graphify(["query", query, "--graph", str(graph)], repo_root)
        if result.returncode == 0:
            return result.stdout or "No matching nodes found."
        return f"Semantic code query unavailable (non-blocking): {result.stderr[:300]}."
    except Exception as e:
        logger.warning("[Tool:search_code_semantically] failed: %s", e)
        return f"Code graph unavailable ({e}). Use read_file/search_files — non-blocking."

"""
Code Graph operations for the AI Research Engineer.
Natively wraps the code-review-graph package for structural code intelligence,
allowing agents to understand blast radius, call graphs, and test gaps
without blowing up the token context window.
"""

import logging
from typing import Any, Optional
from pathlib import Path

# Natively import the powerful tools from code_review_graph
from code_review_graph.tools import (
    build_or_update_graph,
    get_minimal_context,
    get_impact_radius,
    query_graph,
    semantic_search_nodes,
    get_review_context,
    detect_changes_func,
    get_architecture_overview_func
)

logger = logging.getLogger(__name__)

def build_knowledge_graph(repo_root: str) -> str:
    """
    Builds or updates the SQLite knowledge graph for the codebase.
    The agent MUST run this before using any other code graph tools.
    """
    logger.info(f"[Tool:build_knowledge_graph] Building graph for {repo_root}")
    try:
        # We force a postprocess="minimal" for speed during autonomous loops
        result = build_or_update_graph(
            full_rebuild=False, 
            repo_root=repo_root, 
            postprocess="minimal"
        )
        return str(result.get("summary", "Graph built successfully."))
    except Exception as e:
        return f"Error building graph: {e}"

def get_code_context(task: str, repo_root: str) -> str:
    """
    Get an ultra-compact (~100 tokens) structural context for a task.
    Shows graph stats, risk score, and top communities.
    """
    logger.info(f"[Tool:get_code_context] Task: {task}")
    try:
        result = get_minimal_context(task=task, repo_root=repo_root)
        return str(result.get("summary", result))
    except Exception as e:
        return f"Error getting context: {e}"

def get_code_blast_radius(changed_files: list[str], repo_root: str) -> str:
    """
    Analyze the blast radius of specific files.
    Shows which functions, classes, and files are impacted by changes.
    """
    logger.info(f"[Tool:get_code_blast_radius] Files: {changed_files}")
    try:
        result = get_impact_radius(
            changed_files=changed_files, 
            max_depth=2, 
            repo_root=repo_root, 
            detail_level="minimal"
        )
        return str(result)
    except Exception as e:
        return f"Error calculating blast radius: {e}"

def query_code_structure(pattern: str, target: str, repo_root: str) -> str:
    """
    Run a predefined graph query to explore code relationships.
    Patterns: callers_of, callees_of, imports_of, importers_of, children_of, tests_for
    """
    logger.info(f"[Tool:query_code_structure] {pattern} for {target}")
    try:
        result = query_graph(
            pattern=pattern, 
            target=target, 
            repo_root=repo_root, 
            detail_level="standard"
        )
        # Extract just the essential info to save tokens
        if result.get("status") == "ok":
            return str(result.get("results", result.get("summary")))
        return str(result)
    except Exception as e:
        return f"Error querying graph: {e}"

def search_code_semantically(query: str, repo_root: str) -> str:
    """
    Search for code entities (functions, classes) by semantic similarity or keyword.
    """
    logger.info(f"[Tool:search_code_semantically] Query: {query}")
    try:
        result = semantic_search_nodes(
            query=query, 
            repo_root=repo_root, 
            limit=5, 
            detail_level="minimal"
        )
        return str(result.get("results", result))
    except Exception as e:
        return f"Error searching code: {e}"
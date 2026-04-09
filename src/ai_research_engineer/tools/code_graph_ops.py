"""
Code Graph operations for the AI Research Engineer using Graphify.
Executes CLI commands to build and query the codebase knowledge graph,
providing massive token reduction (71.5x) and semantic structure.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def build_knowledge_graph(repo_root: str) -> str:
    """
    Builds or updates the Graphify knowledge graph for the codebase.
    The agent MUST run this before using any other code graph tools.
    """
    logger.info(f"[Tool:build_knowledge_graph] Building graph for {repo_root}")
    try:
        # Run graphify CLI on the target directory
        # Using --no-viz to skip HTML generation and save processing time
        # Removed the '.' argument to prevent 'unknown command' CLI errors. 
        # It relies on cwd=repo_root to target the current directory automatically.
        cmd = ["graphify", "--no-viz"]
        result = subprocess.run(
            cmd, 
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            report_path = Path(repo_root) / "graphify-out" / "GRAPH_REPORT.md"
            if report_path.exists():
                return f"Graph built successfully. CRITICAL: You MUST use the read_file tool to read 'graphify-out/GRAPH_REPORT.md' for the high-level architecture overview before proceeding."
            return "Graph built successfully, but GRAPH_REPORT.md was not generated."
        else:
            return f"Error building graph. stderr: {result.stderr}"
    except Exception as e:
        return f"Exception building graph: {e}"

def get_code_context(task: str, repo_root: str) -> str:
    """
    Use Graphify to explain a specific architecture, task, or module.
    """
    logger.info(f"[Tool:get_code_context] Task: {task}")
    try:
        cmd = ["graphify", "explain", task]
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout
        return f"Error getting context: {result.stderr}"
    except Exception as e:
        return f"Exception getting context: {e}"

def get_code_blast_radius(changed_files: list[str], repo_root: str) -> str:
    """
    Analyze the blast radius of specific files using Graphify's DFS trace.
    """
    logger.info(f"[Tool:get_code_blast_radius] Files: {changed_files}")
    try:
        graph_path = Path(repo_root) / "graphify-out" / "graph.json"
        target = changed_files[0] if isinstance(changed_files, list) and changed_files else str(changed_files)
        
        query = f"what depends on or connects to {target}?"
        cmd = ["graphify", "query", query, "--dfs", "--graph", str(graph_path)]
        
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            output = result.stdout
            if len(output) > 10000:
                output = output[:10000] + "\n\n...[TRUNCATED TO SAVE TOKENS]..."
            return output
        return f"Error calculating blast radius: {result.stderr}"
    except Exception as e:
        return f"Exception calculating blast radius: {e}"

def query_code_structure(pattern: str, target: str, repo_root: str) -> str:
    """
    Find the exact path and structural relationship between two nodes in the codebase.
    (e.g., pattern="Path between", target="ModuleA and ModuleB")
    """
    logger.info(f"[Tool:query_code_structure] Path trace for {target}")
    try:
        # If target has two items separated by 'and', use the path command
        if " and " in target.lower():
            nodes = target.lower().split(" and ")
            cmd = ["graphify", "path", nodes[0].strip(), nodes[1].strip()]
        else:
            # Fallback to standard query
            graph_path = Path(repo_root) / "graphify-out" / "graph.json"
            cmd = ["graphify", "query", f"Show structure of {target}", "--graph", str(graph_path)]

        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout
        return f"Error querying structure: {result.stderr}"
    except Exception as e:
        return f"Exception querying structure: {e}"

def search_code_semantically(query: str, repo_root: str) -> str:
    """
    Query the Graphify knowledge graph using natural language to find structural 
    and semantic relationships.
    """
    logger.info(f"[Tool:search_code_semantically] Query: {query}")
    try:
        graph_path = Path(repo_root) / "graphify-out" / "graph.json"
        if not graph_path.exists():
            return "Error: graph.json not found. Run build_knowledge_graph first."
            
        cmd = ["graphify", "query", query, "--graph", str(graph_path)]
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            output = result.stdout
            # if len(output) > 10000:
            #     output = output[:10000] + "\n\n...[TRUNCATED TO SAVE TOKENS]..."
            return output
        return f"Error querying graph: {result.stderr}"
    except Exception as e:
        return f"Exception querying graph: {e}"
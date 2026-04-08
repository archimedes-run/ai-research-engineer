# Tools Configuration

This guide explains the specialized scientific toolsets available to the AI Research Engineer.

## Overview

The system bridges several advanced toolkits to give agents structural code intelligence, web access, and deep literature ingestion capabilities.

- **Ideation & Planning Agents**: Use Academic Research Tools (ArXiv, Semantic Scholar).
- **Review Agents**: Use AST Code Graph Tools (`code-review-graph`).
- **Coding Agent**: Uses Claude Code with access to 380+ scientific Skills.

## Academic Research Tools (`research_ops.py` & `semantic_scholar_ops.py`)

Available exclusively to the orchestration agents (Idea Generator, Novelty Scorer, Plan Maker, Summary Agent) to perform rigorous literature reviews.

### Semantic Scholar Tools

Used for impact-filtering and citation tracking.

- `semantic_search_papers`: Searches papers with citation count minimums.
- `get_paper_details`: Fetches TLDRs and abstract metadata.
- `get_paper_citations` / `get_paper_references`: Explores citation graphs.
- `export_bibtex`: Exports tracked papers directly into a `.bib` file for the final manuscript.

### ArXiv Tools

Used for full-text ingestion with automatic rate-limiting.

- `arxiv_search_papers`: Enforces arXiv's 3-second rate limit automatically.
- `download_paper`: Tries to pull the lightweight HTML version of a paper first. Falls back to PDF.
- `read_paper`: Parses downloaded HTML or uses `PyPDF2` to convert papers into token-friendly Markdown.

## Structural Code Intelligence (`code_graph_ops.py`)

Available to the Review Agent to verify complex neural networks without exhausting the 1M token context window.

- `build_knowledge_graph`: Parses the workspace Python files into an SQLite Abstract Syntax Tree (AST).
- `get_code_blast_radius`: Shows which downstream functions break if a base class is altered.
- `query_code_structure`: Runs AST queries (e.g., `callees_of`, `tests_for`) to verify architectural implementation without reading the raw source code.
- `search_code_semantically`: Finds specific ML layer implementations via semantic similarity.

## Claude Scientific Skills

The Coding Agent (Claude) has autonomous access to 380+ scientific Skills.

**Status:** Automatic - No configuration needed. Cloned dynamically to `.claude/skills/`.

**Available Capabilities:**
- Deep Learning: PyTorch, TensorFlow, Accelerate, Transformers.
- Scientific Packages: BioPython, RDKit, PyDESeq2, scanpy.
- Data Processing: pandas, numpy, scipy.

## Security Model

All ADK-level file operations are read-only and enforce working directory sandboxing:

- Agents can only access files within their assigned `working_dir`.
- The Planning Agents are deliberately restricted from modifying Python code directly to preserve the integrity of the workspace.
- The Coding Agent runs inside an isolated `uv` virtual environment, preventing system-level package conflicts.

## Environment Variables

### Required

- `OPENROUTER_API_KEY`: Required for orchestration and review agents.
- `ANTHROPIC_API_KEY`: Required for the Coding Agent.

### Highly Recommended

- `SEMANTIC_SCHOLAR_API_KEY`: Without this, the Ideation agents will hit severe HTTP 429 Rate Limit errors when searching the literature. Get one for free at Semantic Scholar.

### Optional

- `CONTEXT7_API_KEY`: For enabling Context7 MCP documentation retrieval for the Claude Agent.
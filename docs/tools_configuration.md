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
- `build_citation_graph`: Multi-seed citation graph (S1-4). Accepts a list of seed IDs, ranks each node's neighbors by influence and recency before truncation, optionally annotates nodes with similarity to a `query_text`, and persists to `knowledge_base/graphs/graph_<timestamp>.json`.
- `export_bibtex`: Exports tracked papers directly into a `.bib` file for the final manuscript.

### Multi-Source Search (`search_ops.py`, S1-3)

Additional literature/code discovery sources, each returning JSON (or a graceful message on empty results, rate limits, or HTTP errors):

- `openalex_search`: OpenAlex works (no key required); reconstructs inverted-index abstracts.
- `paperswithcode_search`: Papers with Code — papers plus their linked repositories.
- `github_search`: GitHub repository/code search; honors `GITHUB_TOKEN` for a higher rate limit and page size, degrades gracefully without one.
- `web_search`: Provider-pluggable general web search. Only added to the toolbelt when `search.web_provider` is set to a real provider **and** its credential is present (see Configuration below).

### Session Literature Index (`lit_ops.py` / `core/lit_index.py`, S1-5)

A per-session FAISS index + JSONL store at `<working_dir>/.data/lit_index/`. Every paper surfaced this run (Semantic Scholar, OpenAlex, Papers with Code, `get_paper_details`, and each ingested paper's abstract) is auto-upserted, deduped by id across sources.

- `search_session_literature(query, top_k=10)`: The first place agents look before hitting the network — returns previously-gathered papers by semantic similarity, with a relevance `score` per hit. The Idea Generator, Novelty Scorer, Plan Maker, and Summary prompts all query it first.

### ArXiv Tools

Used for full-text ingestion with automatic rate-limiting.

- `arxiv_search_papers`: Enforces arXiv's 3-second rate limit automatically.
- `download_paper`: Tries to pull the lightweight HTML version of a paper first. Falls back to PDF.
- `read_paper`: Parses downloaded HTML, or converts the PDF to token-friendly Markdown via the configured `ingestion.pdf_engine` (default `pymupdf4llm`).

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

## Configuration file (`config/archimedes.yaml`)

A single YAML file holds the tunable defaults. **Resolution order for every
setting is: environment variable > `config/archimedes.yaml` > built-in
default.** The file is optional — delete it and the system falls back to the
defaults shown below. Point at an alternate file with the `ARCHIMEDES_CONFIG`
environment variable.

```yaml
search:
  web_provider: none        # tavily | brave | searxng | none
embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
ingestion:
  pdf_engine: pymupdf4llm
```

| Setting | Env override | Default | Purpose |
| --- | --- | --- | --- |
| `search.web_provider` | `SEARCH_WEB_PROVIDER` | `none` | Selects the `web_search` backend. `web_search` is only added to the toolbelt when a real provider is chosen **and** its credential is set. |
| `embeddings.model` | `EMBEDDINGS_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | SentenceTransformers model for the shared embedding substrate (semantic search, citation-graph similarity, session literature index). |
| `ingestion.pdf_engine` | `INGESTION_PDF_ENGINE` | `pymupdf4llm` | PDF → Markdown engine for paper ingestion. |

Web-search provider credentials (set only the one you use):

- `TAVILY_API_KEY` — for `search.web_provider: tavily`
- `BRAVE_API_KEY` — for `search.web_provider: brave`
- `SEARXNG_URL` — self-hosted instance URL for `search.web_provider: searxng`

## Tool Registry (availability gating)

Tools register with a `requires` list; the registry resolves availability once at
agent construction and the toolbelt is built only from tools whose requirements
are all met. Requirement tokens:

- `network` — outbound network is enabled (not disabled via `DISABLE_NETWORK_ACCESS`).
- `key:ENV_NAME` — the named environment variable is set (e.g. `key:TAVILY_API_KEY`).
- `binary:NAME` — `NAME` is on `PATH` (e.g. `binary:pdflatex`).
- `config:search.web_provider` — a web-search provider is configured **and** keyed.

Example: `web_search` requires `["network", "config:search.web_provider"]`, so it
is absent from the toolbelt unless a provider is configured with its credential.
Prompt sections wrapped in `<!-- BEGIN:<tool> -->..<!-- END:<tool> -->` are
dropped when that tool is unavailable, so instructions never reference a tool the
agent cannot call.

## Environment Variables

### Required

- `OPENROUTER_API_KEY`: Required for orchestration and review agents.
- `ANTHROPIC_API_KEY`: Required for the Coding Agent.

### Highly Recommended

- `SEMANTIC_SCHOLAR_API_KEY`: Without this, the Ideation agents will hit severe HTTP 429 Rate Limit errors when searching the literature. Get one for free at Semantic Scholar.

### Optional

- `CONTEXT7_API_KEY`: For enabling Context7 MCP documentation retrieval for the Claude Agent.
- `GITHUB_TOKEN`: Raises `github_search` rate limits and page size; it degrades gracefully when unset.
- `TAVILY_API_KEY` / `BRAVE_API_KEY` / `SEARXNG_URL`: Credential for the selected `search.web_provider` (see Configuration file above).
- `ARCHIMEDES_CONFIG`: Path to an alternate config YAML (defaults to `config/archimedes.yaml`).
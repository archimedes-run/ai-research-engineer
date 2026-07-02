# Archimedes — Autonomous AI Research Framework

[![CI](https://github.com/archimedes-run/ai-research-engineer/actions/workflows/ci.yml/badge.svg)](https://github.com/archimedes-run/ai-research-engineer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/archimedes-run/ai-research-engineer/blob/main/CONTRIBUTING.md)

Archimedes is an open-source autonomous research framework. You give it a prompt and a mode — it runs a research loop end to end and produces a **reproducible trace you can verify**: literature map, experiment plan, working code, metrics, failures, and a draft write-up alongside the full session log.

> **Design principle:** Archimedes produces traces a human verifies, not finished papers. Transparency, steerability, and trustworthiness come first.

---

## The three modes

| Mode | What it does |
|------|-------------|
| **`orchestrated`** (novelty) | Generates a novel research idea, gates it against the citation graph, plans and implements experiments stage by stage, reflects on results, drafts a manuscript. |
| **`simple`** (replication) | Skips planning overhead — hands the prompt directly to the Claude Code agent. Best for narrow coding tasks or strict paper replication. |
| **`evolve`** | AlphaEvolve/FunSearch-style evolutionary search: samples a FAISS database of past code variants, mutates the best one, keeps what improves the empirical metric. |

---

## Quick start

### Prerequisites

1. **Claude Code CLI:**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **API keys** in `.env` (copy `.env.example`):
   ```bash
   ANTHROPIC_API_KEY="your_key"
   OPENROUTER_API_KEY="your_key"
   SEMANTIC_SCHOLAR_API_KEY="your_key"   # optional — raises rate limits
   ```

### Install

```bash
git clone https://github.com/archimedes-run/ai-research-engineer.git
cd ai-research-engineer
uv sync --extra dev
```

### Run

```bash
# Full multi-agent pipeline (novelty mode)
uv run ai-research-engineer "Investigate sparse mixture-of-experts routing in low-resource settings" \
  --mode orchestrated

# Simple / replication
uv run ai-research-engineer "Replicate the WaveletKAN benchmark" \
  --mode simple --research-mode replication

# Evolutionary search
uv run ai-research-engineer "Maximise accuracy on CIFAR-10 under 1M parameters" \
  --mode evolve
```

Output lands in `./agentic_output/` by default. Use `--working-dir <path>` to pin a custom location.

---

## Architecture

Archimedes is a graph of specialised LLM agents — each with a narrow job, a strict prompt, and a defined handoff — wired together into a workflow that mirrors how a research lab operates.

### Agent graph (orchestrated mode)

```
ai_research_engineer_workflow
├── ideation_loop
│   ├── idea_generator_agent        → proposes hypothesis
│   ├── novelty_scorer_agent        → checks against ArXiv / Semantic Scholar
│   └── [review → loop or advance]
├── high_level_planning_loop
│   ├── plan_maker_agent            → milestone-based experiment design
│   ├── plan_reviewer_agent         → critique + iterate
│   └── high_level_plan_parser      → machine-readable stage list
├── stage_orchestrator              → feeds one stage at a time
│   └── implementation_loop
│       ├── [Claude Code agent]     → writes & refines code
│       ├── success_criteria_checker → verifies empirical criteria
│       └── stage_reflector         → rewrites remaining stages from evidence
└── paper_writing_loop
    ├── paper_writer_agent          → synthesises knowledge base → manuscript
    └── paper_reviewer_agent        → review + iterate
```

### The Research Vault (output layout)

```
agentic_output/
├── knowledge_base/   — synthesised literature notes and architecture blueprints
├── literature/       — raw full-text sources (ArXiv, Semantic Scholar)
├── workflow/         — implementation code, training loops, model modules
├── results/          — metric logs, checkpoints, comparison plots
└── manuscript/       — LaTeX source and compiled PDF draft
```

### Evolve mode

`EvolutionLoopAgent` samples parent nodes from a FAISS vector database, mutates via Claude Code, runs the result, reads the score from `results.json`, and commits the new node back. `BestSnapshotManager` tracks the all-time best so regressions never overwrite it.

### Toolbelt

| Tool module | What it does |
|---|---|
| `research_ops` | Semantic Scholar impact-filtering, multi-source paper search, ArXiv full-text |
| `code_graph_ops` | Graphify-based AST-level codebase queries (claimed 71.5× token reduction vs. reading raw source) |
| `data_ops` | DuckDB SQL over Parquet — no in-memory dataset loading |
| `latex_ops` | Compile `.tex` → PDF, surface syntax errors |
| `file_ops` / `web_ops` | Sandboxed file I/O and HTTP fetch, path-validated to working directory |

### Context window management

Once a session exceeds **40 events**, LLM-based event compression summarises history into a single context event, keeping long runs comfortably under a 1 M-token window.

### Python API

```python
from ai_research_engineer import AIEngineer

engineer = AIEngineer(
    agent_type="adk",           # "adk" | "claude_code" | "evolve"
    research_mode="novelty",    # "novelty" | "replication"
    domain="aiml",
    working_dir="./my_run",
)

# Synchronous
result = engineer.run("Investigate sparse MoE routing")
print(result.response)

# Streaming (async)
async for event in engineer.run_async(prompt, stream=True):
    print(event)
```

---

## Research domains

`--domain` injects domain-specific planning and review heuristics into every agent:

| Flag | Domain |
|---|---|
| `aiml` | AI / Machine Learning |
| `finance` | Quantitative finance |
| `bioinformatics` | Computational biology |
| `algorithms` | Algorithm design & complexity |
| `physics` | Theoretical & computational physics |

---

## Local development

```bash
make install   # uv sync + npm install
make dev       # gateway :8001, frontend :3000, nginx :8080
# open http://localhost:8080
```

The landing page and docs are deployed to Vercel automatically on every push to `main`. Vercel builds only the `frontend/` directory, so backend changes and dev-tooling updates (`Makefile`, `scripts/`, `src/`) never affect the production frontend build.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan. Current focus: **Phase 0 (Foundation)** and **Phase 1 (Stabilise the core)**.

---

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), pick a [`good first issue`](https://github.com/archimedes-run/ai-research-engineer/labels/good%20first%20issue), and open a draft PR early. For bigger ideas, open a `design` issue first.

---

## License

MIT — see [LICENSE](LICENSE).

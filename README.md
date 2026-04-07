# AI Research Engineer

**An Autonomous Multi-Agent Framework for Rigorous Machine Learning Research**

AI Research Engineer is an open-source framework designed to automate the entire lifecycle of AI research—from novel hypothesis generation to high-quality code implementation and final academic manuscript drafting. Built on Google's Agent Development Kit (ADK) and the Claude Agent SDK, the system leverages structural code intelligence and deep literature integration to ensure scientific rigor and novelty.

## 🚀 Features

- **🧠 Autonomous Ideation Loop**: Brainstorms novel ML architectures and validates them against SOTA literature using Semantic Scholar and ArXiv.
- **📋 Rigorous Planning**: Architects detailed experimental plans including baselines, ablation studies, and empirical success criteria.
- **🔬 Surgical Implementation**: A Senior ML Engineering agent implements complex neural networks using `uv` for deterministic environment management.
- **🔍 Structural Code Intelligence**: Integrated `code-review-graph` allows agents to perform AST-based analysis, understand blast radius, and identify test gaps without reading entire files.
- **🔄 Adaptive Principal Investigator**: A Stage Reflector agent analyzes training logs and metrics to adapt the research plan in real-time based on empirical progress.
- **📝 Manuscript Generation**: A specialized Summary Agent synthesizes the "Research Vault" (methodology and results) into a publication-ready Markdown/LaTeX paper.

## 🛠️ Quick Start

### Prerequisites

1. **Claude Code CLI** installed:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **API Keys** in a `.env` file:
   ```bash
   ANTHROPIC_API_KEY="your_key"
   OPENROUTER_API_KEY="your_key"
   SEMANTIC_SCHOLAR_API_KEY="your_key" # Optional but recommended
   ```

### Installation

```bash
git clone https://github.com/ris3abh/ai-research-engineer.git
cd ai_research_engineer
uv sync --extra dev
```

### Basic Usage

**Important**: The `--mode orchestrated` flag initiates the full multi-agent research lifecycle.

```bash
# Start a full research project
uv run ai-research-engineer "Investigate Kolmogorov-Arnold Networks for weather forecasting" --mode orchestrated
```

## 🏗️ The Multi-Agent Workflow

1. **Ideation Phase**: Idea Generator and Novelty Scorer survey literature to find gaps and propose a unique hypothesis.
2. **Planning Phase**: Plan Maker translates the hypothesis into a milestone-based experimental design.
3. **Execution Phase**: The Implementation Loop (Coding + Review Agents) builds the architecture and runs benchmarks.
4. **Reflection Phase**: The PI agent reviews metrics and "reflects" to adapt the next stages of research.
5. **Synthesis Phase**: Summary Agent writes the final manuscript using the project's internal Knowledge Base.

## 📂 The Research Vault (Workspace Structure)

Every project creates a structured sandbox to maintain context amnesia protection:

- **`knowledge_base/`**: Synthesized research notes and architecture blueprints (`01_literature_review.md`, `02_methodology_specs.md`).
- **`literature/`**: Raw full-text PDFs and HTML sources from ArXiv.
- **`workflow/`**: Implementation scripts, training loops, and neural network modules.
- **`results/`**: Metric logs, model checkpoints (`.pt`), and comparative plots.

## 🧪 Technical Notes

### Context Window Management

The framework uses aggressive **LLM-based Event Compression**. When a training session exceeds 40 events, the system automatically summarizes the history and replaces it with a single context event, preserving the total window under 1M tokens even for complex, multi-day runs.

### Structural Intelligence

Unlike standard agents, the `review_agent` uses `code-review-graph` to perform **AST surgical inspection**. It identifies specific function signatures and dependency chains to verify mathematical correctness without exhausting the context window on raw code.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for style guidelines and the conventional commit protocol.

---

Copyright © 2026 AI Research Engineer Project. Licensed under MIT.

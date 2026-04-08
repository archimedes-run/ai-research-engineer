# CLI Reference

Complete command-line interface reference for the AI Research Engineer.

## Basic Usage

```bash
ai-research-engineer [OPTIONS] QUERY
```

## Required Options

### `--mode` (REQUIRED)

You must specify an execution mode for every query.

**Choices:**
- `orchestrated`: Full multi-agent research workflow (Ideation → Planning → Coding → Review → Manuscript). Highly recommended for ML research.
- `simple`: Direct coding mode without orchestration. Use for quick scripting.

**Examples:**

```bash
# Complex ML Research
ai-research-engineer "Investigate Kolmogorov-Arnold Networks for weather forecasting" --mode orchestrated

# Quick scripting task
ai-research-engineer "Write a PyTorch script to train a basic ViT on CIFAR-10" --mode simple
```

## Optional Options

### `--files, -f`

Upload datasets or existing papers to include in the analysis.

**Examples:**

```bash
# Provide a local dataset
ai-research-engineer "Propose a novel transformer for this data" --mode orchestrated --files dataset.csv
```

### `--working-dir, -w`

Specify a custom "Research Vault" directory.

**Default:** `./agentic_output/` in your current directory.

**Behavior:**
- The system automatically generates `knowledge_base/`, `literature/`, `workflow/`, and `results/` inside this directory.
- Files and model weights are preserved after completion.

### `--temp-dir`

Use a temporary directory in `/tmp` with automatic cleanup after completion. Useful for fast prototyping where you only want the final Markdown manuscript.

### `--verbose, -v`

Enable verbose logging for debugging. Shows detailed internal agent debates, AST parsing results, and Semantic Scholar queries.

## Execution Modes Deep Dive

### Orchestrated Mode (Recommended)

Full multi-agent workflow simulating an entire research lab.

**When to Use:**
- Deep Learning experiments
- Novel architecture proposals
- Tasks requiring literature review and academic rigor

**What Happens:**
1. Idea Generator & Novelty Scorer review SOTA literature.
2. Plan Maker writes mathematical blueprints.
3. Coding Agent implements PyTorch/JAX code.
4. Review Agent validates AST structure and metrics.
5. Summary Agent writes the final academic paper.

### Simple Mode

Direct execution by Claude Code.

**When to Use:**
- Quick utility scripts
- Code explanations
- Fast, throwaway plots

## Output and Logging

Logs are written to `.agentic_ds.log` in the working directory. To watch your AI Researcher think in real-time, open a separate terminal and run:

```bash
tail -f agentic_output/.agentic_ds.log
```
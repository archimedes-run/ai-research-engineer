# Architecture and Technical Design

This document explains the technical internals, design decisions, and implementation details of the AI Research Engineer.

## Agent Hierarchy

The ADK workflow consists of multiple specialized agents organized into a hierarchical, phase-based structure:

```
Workflow Root (SequentialAgent)
├── Ideation Loop (NonEscalatingLoopAgent)
│   ├── Idea Generator (LoopDetectionAgent)
│   ├── Novelty Scorer (LoopDetectionAgent)
│   └── Ideation Review Confirmation (LoopDetectionAgent)
├── Planning Loop (NonEscalatingLoopAgent)
│   ├── Plan Maker (LoopDetectionAgent)
│   ├── Plan Reviewer (LoopDetectionAgent)
│   └── Plan Review Confirmation (LoopDetectionAgent)
├── Plan Parser (LoopDetectionAgent)
├── Stage Orchestrator (Custom Agent)
│   └── For each stage:
│       ├── Implementation Loop (NonEscalatingLoopAgent)
│       │   ├── Coding Agent (ClaudeCodeAgent)
│       │   ├── Review Agent (LoopDetectionAgent)
│       │   └── Implementation Review Confirmation (LoopDetectionAgent)
│       ├── Criteria Checker (LoopDetectionAgent)
│       └── Stage Reflector (LoopDetectionAgent)
└── Summary Agent (LoopDetectionAgent)
```

## Workflow Design Rationale

### Why Separate Ideation from Planning?

**Problem:** A standard agent will immediately plan an experiment based on a user's prompt, often resulting in unoriginal or previously published work.

**Solution:** The Ideation Loop forces the system to query Semantic Scholar and ArXiv first. The Novelty Scorer acts as a peer reviewer, rejecting ideas that lack SOTA impact before a single line of code is planned.

### Why Separate Planning from Execution?

**Problem:** Direct implementation leads to mathematical errors and tensor shape mismatches.

**Solution:** The `knowledge_base/` paradigm. The Plan Maker documents rigorous mathematical blueprints into `02_methodology_specs.md`. The Coding Agent is strictly forbidden from writing code until it reads this blueprint.

### Why AST Code Graph Parsing?

**Problem:** Neural network scripts can easily exceed thousands of lines. If a Review Agent reads the raw text, it suffers from "context amnesia."

**Solution:** The `review_agent` uses `code-review-graph` to parse the Python AST. It surgically extracts classes, call graphs, and test gaps, allowing it to perform rigorous code reviews without blowing up its token limit.

## Context Window Management

The framework implements aggressive context management to handle multi-hour Deep Learning experiments.

### LLM-Based Event Compression System

1. **Threshold Detection**: Monitors event count after each agent turn (default: 40 events).
2. **Summary Generation**: When exceeded, a secondary LLM summarizes the oldest events.
3. **Event Replacement**: Old events are seamlessly replaced with a single summary event.
4. **Direct Assignment**: Uses `session.events = new_events` to ensure the orchestrator context is instantly updated.

Without this compression, compiling complex PyTorch models, running multiple training loops, and outputting epoch logs would inevitably breach the 1M token limit.

## Stage Orchestration & Adaptive Replanning

The `StageOrchestratorAgent` manages the execution. If an architecture fails to converge or metrics look terrible, the `Criteria Checker` flags the stage as failed. The `Stage Reflector` (acting as the Principal Investigator) dynamically analyzes the failure and injects new ablation or debugging stages into the queue, adapting the scientific process in real-time.
"""S2-4 (graph): the live ADK re-verdict loop mirrors the tested spec.

FalsifierReVerdictAgent drives the SAME shared falsifier_flow the unit tests
exercise: on a scorer APPROVE it re-invokes the falsifier and scorer LLM agents
within one iteration (up to 2 rounds), then hands the final verdict to the code
gate. Scorer call counts are asserted at the graph level (2 for finds->re-score,
1 for two-clean) — matching the pipeline tests. A grep guard enforces that the
control flow lives in exactly one module.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from ai_research_engineer.agents.adk.review_confirmation import (
    create_falsifier_reverdict_agent,
    create_ideation_gate_agent,
)
from ai_research_engineer.core.novelty.falsifier import REASON_CAPPED, REASON_TWO_CLEAN


def _row(work_id, severity):
    return {"work_id": work_id, "overlap_summary": "s", "differs_because": "d", "overlap_severity": severity}


def _scorer_json(severities, verdict="approve"):
    return json.dumps({"verdict": verdict, "differentiation_table": [_row(f"W{i}", s) for i, s in enumerate(severities)]})


def _found_json(work_id):
    return json.dumps({"found": True, "work": {"work_id": work_id, "title": work_id}, "why_core": "does the core"})


def _clean_json(*q):
    return json.dumps({"found": False, "searched": list(q)})


class FakeLlmAgent:
    """Stand-in for a scorer/falsifier LLM sub-agent: writes canned output to its
    output_key, counts invocations, and records what it 'saw'."""

    def __init__(self, output_key, outputs):
        self.output_key = output_key
        self._outputs = list(outputs)
        self.calls = 0
        self.seen_candidates = []

    async def run_async(self, ctx):
        self.calls += 1
        state = ctx.session.state
        self.seen_candidates.append(state.get("prefiltered_works"))
        state[self.output_key] = self._outputs[min(self.calls - 1, len(self._outputs) - 1)]
        return
        yield  # (unreachable) — marks this as an async generator


def _drain(agen):
    async def _run():
        return [e async for e in agen]
    return asyncio.run(_run())


def _new_ctx(initial_candidates):
    state = {"generated_ideas": "the idea", "prefiltered_works": json.dumps(initial_candidates)}
    return SimpleNamespace(session=SimpleNamespace(state=state)), state


def _run_initial_scorer(scorer, ctx):
    """Simulate the initial scorer sub-agent (runs once before the re-verdict agent)."""
    _drain(scorer.run_async(ctx))


# --------------------------------------------------------------------------- #
# approve -> falsifier finds -> re-score(injected) -> reject  (2 scorer calls)
# --------------------------------------------------------------------------- #
def test_graph_finds_then_rescore_reject_reaches_gate_with_killer():
    scorer = FakeLlmAgent("novelty_scorer_feedback",
                          [_scorer_json(["none", "partial"]),           # initial approve
                           _scorer_json(["none", "core"], )])           # re-score marks a core
    # make the re-score's core row BE the injected killer:
    scorer._outputs[1] = json.dumps({"verdict": "approve", "differentiation_table": [
        _row("C0", "none"), _row("KILLER", "core")]})
    falsifier = FakeLlmAgent("novelty_falsifier_feedback", [_found_json("KILLER")])

    ctx, state = _new_ctx([{"work_id": "C0"}])
    _run_initial_scorer(scorer, ctx)                          # scorer call #1
    _drain(create_falsifier_reverdict_agent(scorer, falsifier, k=2)._run_async_impl(ctx))

    assert scorer.calls == 2                                  # initial + one re-score
    assert "KILLER" in scorer.seen_candidates[-1]            # killer injected into re-score set
    assert state["novelty_verdict"]["approved"] is False

    # The final verdict reaches the code gate (NOT via outer regeneration).
    _drain(create_ideation_gate_agent(k=2)._run_async_impl(ctx))
    assert state["_gate_decisions"][-1]["outcome"] == "rejected"
    assert "KILLER" in state["_gate_decisions"][-1]["reason"]


# --------------------------------------------------------------------------- #
# approve -> two clean passes -> approve  (1 scorer call — no re-score)
# --------------------------------------------------------------------------- #
def test_graph_two_clean_passes_approve_one_scorer_call():
    scorer = FakeLlmAgent("novelty_scorer_feedback", [_scorer_json(["none", "partial"])])  # initial only
    falsifier = FakeLlmAgent("novelty_falsifier_feedback", [_clean_json("q1"), _clean_json("q2")])

    ctx, state = _new_ctx([{"work_id": "C0"}])
    _run_initial_scorer(scorer, ctx)                          # scorer call #1
    _drain(create_falsifier_reverdict_agent(scorer, falsifier, k=2)._run_async_impl(ctx))

    assert scorer.calls == 1                                  # NO re-score on clean passes
    assert falsifier.calls == 2                               # two clean falsifier passes
    assert state["novelty_verdict"]["approved"] is True
    assert state["novelty_verdict"]["reason"] == REASON_TWO_CLEAN

    events = _drain(create_ideation_gate_agent(k=2)._run_async_impl(ctx))
    assert events[0].actions.escalate is True                # gate approves


# --------------------------------------------------------------------------- #
# 2-round cap -> gate_decision at the inner layer, never a silent pass
# --------------------------------------------------------------------------- #
def test_graph_cap_emits_inner_gate_decision_no_silent_pass():
    scorer = FakeLlmAgent("novelty_scorer_feedback",
                          [_scorer_json(["none", "partial"])] * 3)  # initial + 2 re-scores all approve
    falsifier = FakeLlmAgent("novelty_falsifier_feedback", [_found_json("K1"), _found_json("K2")])

    ctx, state = _new_ctx([{"work_id": "C0"}])
    _run_initial_scorer(scorer, ctx)                          # #1
    _drain(create_falsifier_reverdict_agent(scorer, falsifier, k=2)._run_async_impl(ctx))

    assert scorer.calls == 3                                  # initial + 2 re-scores (found each round)
    assert state["novelty_verdict"]["approved"] is False      # never a silent pass
    assert state["novelty_verdict"]["reason"] == REASON_CAPPED

    _drain(create_ideation_gate_agent(k=2)._run_async_impl(ctx))
    # gate_decision emitted at the inner (ideation) layer — no outer loop entry.
    assert state["_gate_decisions"], "a gate_decision must be recorded (no silent pass)"
    assert all(d["loop"] == "ideation_novelty_gate" for d in state["_gate_decisions"])
    assert state["_gate_decisions"][-1]["outcome"] == "rejected"


# --------------------------------------------------------------------------- #
# One construction site for the falsifier control flow
# --------------------------------------------------------------------------- #
def test_falsifier_control_flow_lives_in_exactly_one_module():
    marker = "S2-4 FALSIFIER CONTROL FLOW — SINGLE CONSTRUCTION SITE"
    hits = [
        p for p in Path("src").rglob("*.py")
        if marker in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert len(hits) == 1, f"falsifier control flow must exist in exactly one module, found: {hits}"
    assert hits[0].name == "falsifier.py"

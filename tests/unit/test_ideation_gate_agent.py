"""S2-3 correction: the ideation novelty gate is code-only.

Exit is set purely by the code verdict (no confirmation LLM), and the change is
scoped to ideation — planning/paper/implementation confirmations keep their LLM.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from ai_research_engineer.agents.adk import review_confirmation as rc
from ai_research_engineer.agents.adk.review_confirmation import (
    create_ideation_gate_agent,
    create_review_confirmation_agent,
)


def _row(work_id, severity):
    return {
        "work_id": work_id,
        "overlap_summary": f"summary {work_id}",
        "differs_because": f"differs {work_id}",
        "overlap_severity": severity,
    }


def _scorer(severities, verdict="approve"):
    return json.dumps({"verdict": verdict, "differentiation_table": [_row(f"W{i}", s) for i, s in enumerate(severities)]})


def _run_gate(scorer_feedback, k=2):
    """Run the code-only gate against a state dict; return (events, state)."""
    state = {"novelty_scorer_feedback": scorer_feedback}
    ctx = SimpleNamespace(session=SimpleNamespace(state=state))
    agent = create_ideation_gate_agent(k=k)

    async def _collect():
        return [e async for e in agent._run_async_impl(ctx)]

    return asyncio.run(_collect()), state


# --------------------------------------------------------------------------- #
# Exit set purely by code
# --------------------------------------------------------------------------- #
def test_clean_approve_escalates_exit_true():
    events, state = _run_gate(_scorer(["none", "partial"]), k=2)
    assert len(events) == 1
    assert events[0].actions.escalate is True             # exit = True (approved)
    assert state["novelty_verdict"]["approved"] is True
    # Stage 0 gate_decision recorded for the audit trail.
    gd = state["_gate_decisions"][-1]
    assert gd["loop"] == "ideation_novelty_gate"
    assert gd["outcome"] == "approved"


def test_core_overlap_no_escalate_with_killing_work_verbatim():
    events, state = _run_gate(_scorer(["none", "core"]), k=2)
    assert events[0].actions.escalate is False            # exit = False (rejected)
    gd = state["_gate_decisions"][-1]
    assert gd["outcome"] == "rejected"
    # The killing work is carried verbatim into the audit reason.
    assert "W1" in gd["reason"]
    assert "core overlap" in gd["reason"]


def test_incomplete_table_reason_is_incomplete_differentiation():
    events, state = _run_gate(_scorer(["none"]), k=2)  # only 1 row, k=2
    assert events[0].actions.escalate is False
    assert state["_gate_decisions"][-1]["reason"] == "incomplete_differentiation"


# --------------------------------------------------------------------------- #
# No confirmation LLM is involved (spy) — and the change is code-driven
# --------------------------------------------------------------------------- #
def test_ideation_gate_is_code_only_no_llm():
    gate = create_ideation_gate_agent(k=2)
    # A pure BaseAgent: no LLM model and no sub-agents to spin one up.
    assert getattr(gate, "model", None) is None
    assert not getattr(gate, "sub_agents", None)

    # Spy: the exit is driven by the code decision function, invoked exactly once,
    # and no LLM path is touched while running the gate.
    with patch.object(rc, "ideation_gate_decision", wraps=rc.ideation_gate_decision) as spy:
        events, _state = _run_gate(_scorer(["none", "partial"]), k=2)
    assert spy.call_count == 1
    assert events[0].actions.escalate is True


def test_change_is_scoped_to_ideation_only():
    # Ideation confirmation is code-only (no model)...
    assert getattr(create_ideation_gate_agent(k=2), "model", None) is None
    # ...but planning/paper/implementation confirmations remain LLM agents.
    plan_conf = create_review_confirmation_agent(prompt_name="plan_review_confirmation")
    assert getattr(plan_conf, "model", None) is not None

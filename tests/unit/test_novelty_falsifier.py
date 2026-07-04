"""S2-4: adversarial falsifier rounds (orchestration with mocked agents)."""

from unittest.mock import MagicMock

from ai_research_engineer.core.novelty.falsifier import (
    REASON_CAPPED,
    REASON_TWO_CLEAN,
    parse_falsifier_output,
    run_falsifier_rounds,
)
from ai_research_engineer.core.novelty.gate import evaluate_novelty


IDEA = {"title": "learned sparse attention", "description": "per-head sparsity from input"}


def _row(work_id, severity):
    return {"work_id": work_id, "overlap_summary": f"s{work_id}",
            "differs_because": f"d{work_id}", "overlap_severity": severity}


def _scorer_out(severities, verdict="approve"):
    return {"verdict": verdict, "differentiation_table": [_row(f"W{i}", s) for i, s in enumerate(severities)]}


def _found(work_id="KILLER"):
    return {"found": True, "work": {"work_id": work_id, "title": work_id}, "why_core": "already does the core"}


def _clean(*queries):
    return {"found": False, "searched": list(queries)}


def _base_approve(k=2):
    return evaluate_novelty(_scorer_out(["none", "partial"]), k)


# --------------------------------------------------------------------------- #
# parse
# --------------------------------------------------------------------------- #
def test_parse_handles_json_string_and_dict_and_garbage():
    assert parse_falsifier_output('{"found": true, "work": {"title": "X"}}')["found"] is True
    assert parse_falsifier_output({"found": False, "searched": ["q"]})["searched"] == ["q"]
    assert parse_falsifier_output("not json")["found"] is False


# --------------------------------------------------------------------------- #
# Path 1: approve -> falsifier finds -> re-score with injected candidate -> reject
# --------------------------------------------------------------------------- #
def test_approve_falsifier_finds_rescore_rejects():
    falsify_fn = MagicMock(return_value=_found("KILLER"))
    # Re-score (with the killer injected) now returns a core row -> reject.
    score_fn = MagicMock(return_value=_scorer_out(["none", "core"]))

    result = run_falsifier_rounds(IDEA, _base_approve(), [{"work_id": "C0"}],
                                  score_fn=score_fn, falsify_fn=falsify_fn, k=2)

    assert result["approved"] is False and result["verdict"] == "reject"
    # The scorer re-ran exactly once (the injected-candidate re-score).
    score_fn.assert_called_once()
    injected = score_fn.call_args.args[1]
    assert any(c.get("work_id") == "KILLER" for c in injected)  # killer injected
    assert result["falsifier_rounds"] == 1


# --------------------------------------------------------------------------- #
# Path 2: approve -> two clean passes -> final approve
# --------------------------------------------------------------------------- #
def test_two_clean_passes_final_approve():
    falsify_fn = MagicMock(side_effect=[_clean("q1"), _clean("q2")])
    score_fn = MagicMock()  # must NOT be called (no killer found -> no re-score)

    result = run_falsifier_rounds(IDEA, _base_approve(), [{"work_id": "C0"}],
                                  score_fn=score_fn, falsify_fn=falsify_fn, k=2)

    assert result["approved"] is True and result["reason"] == REASON_TWO_CLEAN
    assert falsify_fn.call_count == 2
    score_fn.assert_not_called()


# --------------------------------------------------------------------------- #
# Path 3: max 2 rounds without two clean passes -> NOT a silent pass
# --------------------------------------------------------------------------- #
def test_max_rounds_cap_returns_non_approve_outcome():
    # Falsifier keeps finding killers; each re-score still approves -> after 2
    # rounds the cap is hit without two clean passes.
    falsify_fn = MagicMock(side_effect=[_found("K1"), _found("K2")])
    score_fn = MagicMock(return_value=_scorer_out(["none", "partial"]))  # re-score approves

    result = run_falsifier_rounds(IDEA, _base_approve(), [{"work_id": "C0"}],
                                  score_fn=score_fn, falsify_fn=falsify_fn, k=2, max_rounds=2)

    assert result["approved"] is False              # never a silent pass
    assert result["reason"] == REASON_CAPPED
    assert result["capped"] is True
    assert result["falsifier_rounds"] == 2
    assert score_fn.call_count == 2                 # re-scored each found round


def test_gate_decision_emitted_on_cap_via_pipeline():
    # Through the pipeline, the capped outcome emits a Stage 0 gate_decision
    # (rejected) — an audit trail entry, never a silent pass.
    from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
    from ai_research_engineer.core.novelty.pipeline import evaluate_idea

    events = []

    def rec(loop, outcome, reason):
        events.append((loop, outcome, reason))

    score_fn = MagicMock(return_value=_scorer_out(["none", "partial"]))  # always approves
    falsify_fn = MagicMock(side_effect=[_found("K1"), _found("K2")])
    store = RejectedIdeaStore(state={}, embed_fn=lambda t: [1.0, 0.0])

    result = evaluate_idea(IDEA, [{"work_id": "C0"}], score_fn=score_fn, falsify_fn=falsify_fn,
                           k=2, store=store, record_gate_decision=rec)

    assert result["approved"] is False
    assert events and events[-1][1] == "rejected"   # gate_decision emitted, rejected

"""S2-3: code-authoritative gate + prompt-content guards.

The gate must coerce the scorer's output in code — an APPROVE with a `core` row,
a missing overlap_severity, or fewer than k rows becomes a REJECT regardless of
the verdict field. The LLM cannot approve by omission.
"""

from pathlib import Path

from ai_research_engineer.core.novelty.gate import (
    REASON_CORE,
    REASON_INCOMPLETE,
    evaluate_novelty,
    ideation_gate_decision,
)


_PROMPTS = Path("src/ai_research_engineer/prompts/base")


def _row(work_id, severity):
    return {
        "work_id": work_id,
        "overlap_summary": f"summary for {work_id}",
        "differs_because": f"differs from {work_id}",
        "overlap_severity": severity,
    }


def _table(severities):
    return [_row(f"W{i}", sev) for i, sev in enumerate(severities)]


# --------------------------------------------------------------------------- #
# Gate coercion
# --------------------------------------------------------------------------- #
def test_approve_with_core_is_coerced_to_reject():
    out = {"verdict": "approve", "differentiation_table": _table(["none", "partial", "core"])}
    res = evaluate_novelty(out, k=3)
    assert res.verdict == "reject"
    assert res.reason == REASON_CORE
    # The killing work is attached verbatim for the generator.
    assert len(res.killing_works) == 1
    assert res.killing_works[0]["work_id"] == "W2"
    assert res.killing_works[0]["overlap_severity"] == "core"


def test_approve_with_incomplete_table_is_reject():
    # Claims approve but only 2 rows when k=3 -> incomplete.
    out = {"verdict": "approve", "differentiation_table": _table(["none", "partial"])}
    res = evaluate_novelty(out, k=3)
    assert res.verdict == "reject"
    assert res.reason == REASON_INCOMPLETE


def test_approve_with_missing_severity_is_reject():
    table = _table(["none", "none"])
    del table[1]["overlap_severity"]  # malformed row
    out = {"verdict": "approve", "differentiation_table": table}
    res = evaluate_novelty(out, k=2)
    assert res.verdict == "reject"
    assert res.reason == REASON_INCOMPLETE


def test_approve_with_invalid_severity_value_is_reject():
    table = _table(["none", "somewhat"])  # "somewhat" not in {none,partial,core}
    out = {"verdict": "approve", "differentiation_table": table}
    res = evaluate_novelty(out, k=2)
    assert res.verdict == "reject"
    assert res.reason == REASON_INCOMPLETE


def test_clean_complete_approve_passes():
    out = {"verdict": "approve", "differentiation_table": _table(["none", "partial", "none"])}
    res = evaluate_novelty(out, k=3)
    assert res.verdict == "approve"
    assert res.approved is True
    assert res.killing_works == []


def test_empty_table_claiming_approve_is_reject():
    res = evaluate_novelty({"verdict": "approve", "differentiation_table": []}, k=3)
    assert res.verdict == "reject"
    assert res.reason == REASON_INCOMPLETE


def test_scorer_reject_on_clean_table_is_honored():
    # Complete, no core, but the scorer explicitly rejected for its own reason.
    out = {"verdict": "reject", "reason": "weak baselines",
           "differentiation_table": _table(["none", "partial"])}
    res = evaluate_novelty(out, k=2)
    assert res.verdict == "reject"
    assert res.reason == "weak baselines"


def test_mvpt_carried_but_not_used_for_decision():
    out = {"verdict": "approve", "mvpt": {"method_novelty": {"score": 1}},
           "differentiation_table": _table(["none"])}
    res = evaluate_novelty(out, k=1)
    # A dismal MVPT does not block a clean, complete approve.
    assert res.verdict == "approve"
    assert res.mvpt == {"method_novelty": {"score": 1}}


# --------------------------------------------------------------------------- #
# Ideation confirmation gate branches on the structured verdict
# --------------------------------------------------------------------------- #
def test_ideation_gate_branches_on_verdict():
    approve = {"verdict": "approve", "differentiation_table": _table(["none", "none"])}
    reject_core = {"verdict": "approve", "differentiation_table": _table(["none", "core"])}
    reject_incomplete = {"verdict": "approve", "differentiation_table": _table(["none"])}

    d_ok = ideation_gate_decision(approve, k=2)
    assert d_ok["exit"] is True and d_ok["approved"] is True and d_ok["killing_works"] == []

    d_core = ideation_gate_decision(reject_core, k=2)
    assert d_core["exit"] is False
    assert d_core["reason"] == REASON_CORE
    assert d_core["feedback"]["killing_works"][0]["overlap_severity"] == "core"

    d_inc = ideation_gate_decision(reject_incomplete, k=2)
    assert d_inc["exit"] is False and d_inc["reason"] == REASON_INCOMPLETE


# --------------------------------------------------------------------------- #
# Prompt-content guards
# --------------------------------------------------------------------------- #
def test_novelty_scorer_has_table_schema_and_no_tier():
    text = (_PROMPTS / "novelty_scorer.md").read_text()
    for field in ("work_id", "overlap_summary", "differs_because", "overlap_severity"):
        assert field in text
    for sev in ("none", "partial", "core"):
        assert sev in text
    assert "TIER_" not in text  # numeric publication tiers removed


def test_idea_generator_has_no_expected_mvpt():
    text = (_PROMPTS / "idea_generator.md").read_text()
    assert "expected_mvpt" not in text
    # Feedback wiring carries the killing works verbatim.
    assert "killing_works" in text


def test_ideation_confirmation_prompt_is_gone():
    # The ideation confirmation is now code-only; the LLM prompt was removed.
    assert not (_PROMPTS / "ideation_review_confirmation.md").exists()


def test_ideation_review_confirmation_referenced_nowhere_in_src():
    # Grep guard: no dead reference to the removed prompt anywhere under src/.
    src = Path("src")
    hits = [
        p for p in src.rglob("*")
        if p.is_file() and p.suffix in {".py", ".md"} and "ideation_review_confirmation" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == [], f"dead references to ideation_review_confirmation: {hits}"

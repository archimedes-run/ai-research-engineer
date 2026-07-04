"""S2-6: ideation tournament — shared recall corpus, ranked winner, runner-up,
zero-approved -> Stage 0 exhausted/halt. All agents mocked."""

from unittest.mock import MagicMock, patch

import numpy as np

from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
from ai_research_engineer.core.novelty.tournament import run_ideation_tournament, select_winner


def _fake_embed(texts, model_name=None):
    if isinstance(texts, str):
        texts = [texts]
    return np.array([[float(i + 1), 0.0, 1.0] for i in range(len(texts))], dtype=np.float32)


def _idea(n):
    return {"title": f"idea {n}", "description": f"desc {n}"}


def _row(work_id, severity):
    return {"work_id": work_id, "overlap_summary": "s", "differs_because": "d", "overlap_severity": severity}


def _scorer_for(table_by_idea):
    """score_fn that returns a per-idea table keyed by the idea title."""
    def score(idea, candidates):
        return {"verdict": "approve", "differentiation_table": table_by_idea[idea["title"]]}
    return score


def _clean(_idea, _table):
    return {"found": False, "searched": ["q"]}


def _store():
    # deterministic distinct embeddings so tournament ideas never self-dedupe
    counter = {"n": 0}

    def embed(text):
        counter["n"] += 1
        return [float(counter["n"]), 0.0, 1.0]

    return RejectedIdeaStore(state={}, embed_fn=embed)


# --------------------------------------------------------------------------- #
# recall runs ONCE for the round, shared across ideas
# --------------------------------------------------------------------------- #
def test_recall_invoked_once_shared_corpus():
    ideas = [_idea(i) for i in range(5)]  # 5 ideas
    corpus = [{"id": "K0", "title": "prior", "score": 0.1}]
    recall_spy = MagicMock(return_value=corpus)
    tables = {i["title"]: [_row("W0", "none"), _row("W1", "none")] for i in ideas}

    with patch("ai_research_engineer.core.novelty.prefilter.embed_texts", side_effect=_fake_embed):
        res = run_ideation_tournament(
            ideas, recall_fn=recall_spy, score_fn=_scorer_for(tables), falsify_fn=_clean,
            k=2, store=_store(),
        )

    recall_spy.assert_called_once()                 # ONE recall for the whole round
    assert recall_spy.call_args.args[0] == ideas     # over the shared set of ideas
    assert len(res["audits"]) == 5                    # a per-idea audit each
    assert all("decision" in a and "table" in a for a in res["audits"])


# --------------------------------------------------------------------------- #
# winner ranking: no core, then fewest partials, then greatest prefilter distance
# --------------------------------------------------------------------------- #
def test_winner_ranked_by_partials_then_distance():
    # Build audits directly to exercise select_winner ranking deterministically.
    audits = [
        {"idea": _idea(0), "approved": True,  # 2 partials -> worse
         "table": [_row("a", "partial"), _row("b", "partial")], "prefiltered": [{"score": 0.1}]},
        {"idea": _idea(1), "approved": True,  # 1 partial, near prior work (dist 0.1)
         "table": [_row("a", "partial")], "prefiltered": [{"score": 0.9}]},
        {"idea": _idea(2), "approved": True,  # 1 partial, FAR from prior work (dist 0.8) -> winner
         "table": [_row("a", "partial")], "prefiltered": [{"score": 0.2}]},
        {"idea": _idea(3), "approved": False, "table": [], "prefiltered": []},  # rejected -> ignored
    ]
    sel = select_winner(audits)
    assert sel["winner"]["idea"]["title"] == "idea 2"   # fewest partials + most distant
    assert sel["runner_up"]["idea"]["title"] == "idea 1"  # same partials, nearer -> runner-up
    assert sel["approved_count"] == 3


# --------------------------------------------------------------------------- #
# runner-up stored with its audit (via the orchestrator)
# --------------------------------------------------------------------------- #
def test_runner_up_present_when_multiple_approved():
    ideas = [_idea(0), _idea(1)]
    tables = {
        "idea 0": [_row("a", "partial"), _row("b", "none")],  # 1 partial
        "idea 1": [_row("a", "none"), _row("b", "none")],      # 0 partials -> winner
    }
    res = run_ideation_tournament(ideas, recall_fn=MagicMock(return_value=[]),
                                  score_fn=_scorer_for(tables), falsify_fn=_clean, k=2, store=_store())
    assert res["winner"]["idea"]["title"] == "idea 1"
    assert res["runner_up"]["idea"]["title"] == "idea 0"
    assert "decision" in res["runner_up"]  # the runner-up carries its full audit


# --------------------------------------------------------------------------- #
# zero approved -> no winner -> Stage 0 exhausted / halt (sabotage-b machinery)
# --------------------------------------------------------------------------- #
def test_zero_approved_exhausts_and_halts():
    from ai_research_engineer.agents.adk.agent import classify_loop_outcome
    from ai_research_engineer.agents.adk.hitl_sequential import loop_outcome_action

    ideas = [_idea(0), _idea(1), _idea(2)]
    # every idea has a core overlap -> the gate rejects all of them
    tables = {i["title"]: [_row("a", "core")] for i in ideas}
    res = run_ideation_tournament(ideas, recall_fn=MagicMock(return_value=[]),
                                  score_fn=_scorer_for(tables), falsify_fn=_clean, k=1, store=_store())

    assert res["winner"] is None and res["approved_count"] == 0

    # No winner -> the loop is NOT approved -> Stage 0 says exhausted -> halt.
    outcome = classify_loop_outcome(res["winner"] is not None)
    assert outcome == "exhausted"
    assert loop_outcome_action("ideation_loop", outcome) == "halt"


def test_ideas_per_round_is_four_to_six_in_prompt():
    from pathlib import Path
    text = Path("src/ai_research_engineer/prompts/base/idea_generator.md").read_text()
    assert "4-6" in text
    assert "2-3 hypotheses" not in text  # raised from 2-3


def test_stage_reflector_has_runner_up_pivot_line():
    from pathlib import Path
    text = Path("src/ai_research_engineer/prompts/base/stage_reflector.md").read_text()
    assert "ideation_runner_up" in text
    assert "runner-up" in text.lower() and "remediation" in text.lower()

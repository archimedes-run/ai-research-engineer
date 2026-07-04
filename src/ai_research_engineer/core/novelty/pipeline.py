"""Novelty evaluation pipeline (S2-4 + S2-5).

Ties the stages together for one idea:

  1. **Dedup (S2-5)** — if the idea is a near-duplicate of one rejected earlier
     this session, auto-reject with the prior reason **without calling the
     scorer** (zero tokens).
  2. **Score + gate (S2-3)** — run the scorer, coerce its output in code.
  3. **Falsifier (S2-4)** — on a scorer APPROVE, run adversarial falsifier
     rounds; two clean passes confirm APPROVE.

Rejections (from any stage) are recorded into the rejected-idea store so future
duplicates are caught cheaply. A ``record_gate_decision`` callback emits a Stage 0
gate_decision for every terminal outcome (no silent pass).

``score_fn`` / ``falsify_fn`` are injected (mocked in tests, LLM-backed in the
graph / benchmark).
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
from ai_research_engineer.core.novelty.falsifier import run_falsifier_rounds
from ai_research_engineer.core.novelty.gate import evaluate_novelty


logger = logging.getLogger(__name__)


def _emit(record_gate_decision: Optional[Callable], outcome: str, reason: str) -> None:
    if record_gate_decision is not None:
        try:
            record_gate_decision("ideation_novelty_gate", outcome, reason)
        except Exception as exc:  # audit is best-effort
            logger.debug("[novelty.pipeline] gate_decision emit failed: %s", exc)


def evaluate_idea(
    idea: dict,
    candidates: List[dict],
    *,
    score_fn: Callable[[dict, List[dict]], dict],
    falsify_fn: Callable[[dict, list], object],
    k: int,
    store: RejectedIdeaStore,
    threshold: Optional[float] = None,
    record_gate_decision: Optional[Callable] = None,
) -> dict:
    """Full novelty decision for one idea. Returns a decision dict with at least
    ``{approved, verdict, reason}``."""
    # 1) Dedup — auto-reject a near-duplicate of a prior rejection; NO scorer call.
    dup = store.find_duplicate(idea, threshold)
    if dup is not None:
        decision = {
            "approved": False,
            "verdict": "reject",
            "reason": dup["reason"],
            "deduped": True,
            "cosine": dup["cosine"],
        }
        _emit(record_gate_decision, "rejected", f"duplicate of a rejected idea ({dup['cosine']}): {dup['reason']}")
        return decision

    # 2) Score + gate.
    verdict = evaluate_novelty(score_fn(idea, candidates), k)
    if not verdict.approved:
        store.record_rejection(idea, verdict.reason)
        _emit(record_gate_decision, "rejected", verdict.reason)
        return {"approved": False, "verdict": "reject", "reason": verdict.reason,
                "killing_works": verdict.killing_works}

    # 3) Falsifier rounds on an approve.
    result = run_falsifier_rounds(idea, verdict, candidates, score_fn=score_fn, falsify_fn=falsify_fn, k=k)
    if not result["approved"]:
        store.record_rejection(idea, result["reason"])
    _emit(record_gate_decision, "approved" if result["approved"] else "rejected", result["reason"])
    return result

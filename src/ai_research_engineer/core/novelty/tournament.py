"""Ideation tournament (S2-6).

The generator proposes 4-6 ideas per round. Recall (S2-1) runs ONCE on the union
of the ideas' queries — a shared corpus — and every idea is prefiltered + scored
against it. The top APPROVED idea wins; the runner-up (if any) is kept so the
stage reflector can pivot to it if the winner's plan fails terminally.

Winner ranking among approved ideas:
  1. fewest ``core`` overlaps (approved ideas have none — kept for completeness),
  2. then fewest ``partial`` overlaps,
  3. then greatest prefilter distance (``1 - top cosine``) — the idea sitting
     farthest from its nearest prior work is the most novel.

``recall_fn`` / ``score_fn`` / ``falsify_fn`` are injected so this is testable
with mocked agents and reusable by the benchmark and the live graph agent.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
from ai_research_engineer.core.novelty.pipeline import evaluate_idea


logger = logging.getLogger(__name__)


def _count(table: list, severity: str) -> int:
    return sum(1 for r in (table or []) if isinstance(r, dict) and r.get("overlap_severity") == severity)


def _prefilter_distance(prefiltered: list) -> float:
    """1 - the highest cosine among the idea's prefiltered works (higher = more
    novel). No prefiltered works -> maximally distant."""
    top = max((row.get("score", 0.0) for row in (prefiltered or []) if isinstance(row, dict)), default=0.0)
    return 1.0 - float(top)


def rank_key(audit: dict):
    """Sort key (ascending) for an approved idea's audit."""
    table = audit.get("table") or []
    return (_count(table, "core"), _count(table, "partial"), -_prefilter_distance(audit.get("prefiltered")))


def select_winner(audits: List[dict]) -> dict:
    """Pick the winner + runner-up among approved audits (shared by the code
    orchestrator and the live graph agent — one ranking implementation)."""
    approved = [a for a in audits if a.get("approved")]
    ranked = sorted(approved, key=rank_key)
    return {
        "winner": ranked[0] if ranked else None,
        "runner_up": ranked[1] if len(ranked) > 1 else None,
        "ranked": ranked,
        "approved_count": len(approved),
    }


def build_audit(idx: int, idea: dict, decision: dict) -> dict:
    return {
        "idea_index": idx,
        "idea": idea,
        "approved": bool(decision.get("approved")),
        "verdict": decision.get("verdict"),
        "reason": decision.get("reason"),
        "table": decision.get("table", []),
        "prefiltered": decision.get("prefiltered", []),
        "decision": decision,
    }


def run_ideation_tournament(
    ideas: List[dict],
    *,
    recall_fn: Callable[[List[dict]], list],
    score_fn: Callable[[dict, list], dict],
    falsify_fn: Callable[[dict, list], object],
    k: int,
    store: RejectedIdeaStore,
    record_gate_decision: Optional[Callable] = None,
) -> dict:
    """Run one ideation round. ``recall_fn`` is called EXACTLY once (shared
    corpus); each idea is prefiltered + scored + falsified against it.

    Returns ``{winner, runner_up, ranked, approved_count, audits, corpus_size}``.
    """
    corpus = recall_fn(ideas) or []  # ONE recall for the round
    audits = [
        build_audit(
            idx,
            idea,
            evaluate_idea(idea, corpus, score_fn=score_fn, falsify_fn=falsify_fn, k=k,
                          store=store, record_gate_decision=record_gate_decision),
        )
        for idx, idea in enumerate(ideas)
    ]
    result = select_winner(audits)
    result["audits"] = audits
    result["corpus_size"] = len(corpus)
    return result

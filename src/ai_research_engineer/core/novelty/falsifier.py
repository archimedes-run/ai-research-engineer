"""Stage D — adversarial falsifier rounds (S2-4).

After the scorer APPROVEs, the falsifier tries to find a prior work that kills
the idea (a ``core`` overlap the differentiation table missed). If it finds one,
the work is injected into the candidate set and the scorer re-runs. Up to
``max_rounds`` (2) falsifier rounds; **two clean passes = final APPROVE**. If the
cap is hit without two clean passes, the outcome is returned per Stage 0
semantics (never a silent pass).

``score_fn(idea, candidates) -> scorer_output_dict`` and
``falsify_fn(idea, table) -> falsifier_output`` are injected so this is testable
with mocked agents and reusable by the benchmark (S2-7).
"""

from __future__ import annotations

import json
import logging
from typing import Callable, List

from ai_research_engineer.core.novelty.gate import evaluate_novelty


logger = logging.getLogger(__name__)

DEFAULT_MAX_ROUNDS = 2
REQUIRED_CLEAN_PASSES = 2
REASON_TWO_CLEAN = "two clean falsifier passes"
REASON_CAPPED = "falsifier cap reached without two clean passes"


def parse_falsifier_output(raw) -> dict:
    """Normalize the falsifier agent output to
    ``{found, work, why_core, searched}``."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "found": bool(data.get("found")),
        "work": data.get("work") or {},
        "why_core": data.get("why_core") or "",
        "searched": data.get("searched") or [],
    }


def _outcome(verdict: str, reason: str, rounds: list, **extra) -> dict:
    out = {
        "verdict": verdict,
        "approved": verdict == "approve",
        "reason": reason,
        "falsifier_rounds": len(rounds),
        "rounds": rounds,
    }
    out.update(extra)
    return out


def run_falsifier_rounds(
    idea: dict,
    base_verdict,
    candidates: List[dict],
    *,
    score_fn: Callable[[dict, List[dict]], dict],
    falsify_fn: Callable[[dict, list], object],
    k: int,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict:
    """Run adversarial falsifier rounds on an already-APPROVED idea.

    ``base_verdict`` is the GateResult from the initial scorer approve. Returns a
    decision dict: ``approved`` True only on two clean passes.
    """
    current_table = list(getattr(base_verdict, "table", None) or [])
    working_candidates = list(candidates)
    clean_passes = 0
    rounds: list = []

    for round_no in range(1, max_rounds + 1):
        f = parse_falsifier_output(falsify_fn(idea, current_table))
        rounds.append({"round": round_no, "found": f["found"], "work": f["work"], "why_core": f["why_core"]})

        if f["found"]:
            # Inject the killing work and force the scorer to re-run against it.
            working_candidates = working_candidates + [f["work"]]
            rescored = evaluate_novelty(score_fn(idea, working_candidates), k)
            current_table = list(rescored.table or [])
            clean_passes = 0
            if not rescored.approved:
                return _outcome(
                    "reject",
                    rescored.reason or f["why_core"] or "falsifier found a core overlap",
                    rounds,
                    killing_works=rescored.killing_works or [f["work"]],
                )
            # Re-score still approves — keep probing.
        else:
            clean_passes += 1
            if clean_passes >= REQUIRED_CLEAN_PASSES:
                return _outcome("approve", REASON_TWO_CLEAN, rounds, clean_passes=clean_passes)

    # Cap reached without two clean passes: NOT a silent approve.
    return _outcome("reject", REASON_CAPPED, rounds, capped=True, clean_passes=clean_passes)

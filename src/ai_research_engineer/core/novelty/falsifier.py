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


# >>> S2-4 FALSIFIER CONTROL FLOW — SINGLE CONSTRUCTION SITE <<<
# The score->falsify->re-score round logic (found->inject->re-score, two clean
# passes -> approve, 2-round cap -> non-approve) lives ONLY here, as a generator
# state machine. Both the sync driver (run_falsifier_rounds, for tests + the
# benchmark) and the async ADK driver (FalsifierReVerdictAgent, live graph) pump
# this generator — neither re-implements the loop. A grep guard enforces that
# this control-flow marker appears in exactly one module.
def falsifier_flow(idea: dict, base_verdict, candidates: List[dict], k: int, max_rounds: int):
    """Generator control flow. Yields requests to the driver and receives results:

      * ``yield ("falsify", idea, table)``     -> driver sends the falsifier output,
      * ``yield ("score", idea, candidates)``  -> driver sends the scorer output dict.

    Returns (via ``StopIteration.value``) the decision dict. ``approved`` is True
    only after two clean falsifier passes.
    """
    current_table = list(getattr(base_verdict, "table", None) or [])
    working_candidates = list(candidates)
    clean_passes = 0
    rounds: list = []

    for round_no in range(1, max_rounds + 1):
        f = parse_falsifier_output((yield ("falsify", idea, current_table)))
        rounds.append({"round": round_no, "found": f["found"], "work": f["work"], "why_core": f["why_core"]})

        if f["found"]:
            # Inject the killing work and force the scorer to re-run against it.
            working_candidates = working_candidates + [f["work"]]
            rescored = evaluate_novelty((yield ("score", idea, working_candidates)), k)
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
    """Synchronous driver over ``falsifier_flow`` (used by the tests + benchmark).

    ``base_verdict`` is the GateResult from the initial scorer approve.
    """
    flow = falsifier_flow(idea, base_verdict, candidates, k, max_rounds)
    try:
        request = flow.send(None)
        while True:
            kind, arg_idea, arg_payload = request
            result = falsify_fn(arg_idea, arg_payload) if kind == "falsify" else score_fn(arg_idea, arg_payload)
            request = flow.send(result)
    except StopIteration as stop:
        return stop.value

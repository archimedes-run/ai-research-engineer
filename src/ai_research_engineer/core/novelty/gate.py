"""Stage C gate — code-authoritative novelty verdict (S2-3).

The scorer emits a differentiation table + a claimed verdict. This module is the
*authority*: it schema-validates the table and coerces the verdict in code, so
the LLM cannot approve by omission. The rules (independent of the claimed
verdict):

  * any row with ``overlap_severity == "core"``  -> REJECT, the killing work(s)
    attached verbatim for the generator,
  * a table with fewer than ``k`` valid rows, or any row missing/!valid
    ``overlap_severity`` (or the required fields) -> REJECT, reason
    "incomplete differentiation",
  * otherwise the scorer's claimed verdict stands (it may APPROVE, or REJECT for
    its own stated reason).

MVPT, if present, is carried through as a reporting lens only — never consulted
for the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


_VALID_SEVERITY = {"none", "partial", "core"}
_REQUIRED_ROW_FIELDS = ("work_id", "overlap_summary", "differs_because", "overlap_severity")

REASON_CORE = "core overlap with prior work"
REASON_INCOMPLETE = "incomplete differentiation"


@dataclass
class GateResult:
    verdict: str  # "approve" | "reject"
    reason: str
    killing_works: List[dict] = field(default_factory=list)
    table: List[dict] = field(default_factory=list)
    mvpt: Optional[dict] = None

    @property
    def approved(self) -> bool:
        return self.verdict == "approve"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "approved": self.approved,
            "reason": self.reason,
            "killing_works": self.killing_works,
            "table": self.table,
            "mvpt": self.mvpt,
        }


def _extract_table(scorer_output: dict) -> list:
    for key in ("differentiation_table", "differentiation", "works"):
        val = scorer_output.get(key)
        if isinstance(val, list):
            return val
    return []


def _row_is_valid(row) -> bool:
    if not isinstance(row, dict):
        return False
    if any(not row.get(f) for f in _REQUIRED_ROW_FIELDS if f != "overlap_severity"):
        return False
    return row.get("overlap_severity") in _VALID_SEVERITY


def _claimed_verdict(scorer_output: dict) -> str:
    v = str(scorer_output.get("verdict", "")).strip().lower()
    if v in ("approve", "approved", "accept"):
        return "approve"
    if v in ("reject", "rejected"):
        return "reject"
    rec = str(scorer_output.get("recommendation", "")).strip().lower()
    if rec.startswith("approve"):
        return "approve"
    if rec.startswith("reject"):
        return "reject"
    # No parseable claim -> default to reject (fail closed).
    return "reject"


def evaluate_novelty(scorer_output: dict, k: int) -> GateResult:
    """Authoritative gate decision. ``scorer_output`` is the scorer's parsed JSON;
    ``k`` is the number of prefiltered works the table must cover."""
    if not isinstance(scorer_output, dict):
        return GateResult("reject", REASON_INCOMPLETE, table=[])

    table = _extract_table(scorer_output)
    mvpt = scorer_output.get("mvpt") if isinstance(scorer_output.get("mvpt"), dict) else None

    valid = [r for r in table if _row_is_valid(r)]
    has_invalid = len(valid) != len(table)

    # 1) Any core overlap kills the idea — attach the killing work(s) verbatim.
    core = [r for r in valid if r.get("overlap_severity") == "core"]
    if core:
        return GateResult("reject", REASON_CORE, killing_works=core, table=table, mvpt=mvpt)

    # 2) The table must be complete and well-formed. Fewer than k valid rows, or
    #    any malformed row, is treated as REJECT regardless of the claim.
    if has_invalid or len(valid) < k:
        return GateResult("reject", REASON_INCOMPLETE, table=table, mvpt=mvpt)

    # 3) Clean, complete table — honor the scorer's claimed verdict.
    claim = _claimed_verdict(scorer_output)
    if claim == "approve":
        return GateResult("approve", "no core overlap; differentiation complete", table=table, mvpt=mvpt)
    return GateResult("reject", scorer_output.get("reason") or "scorer rejected", table=table, mvpt=mvpt)


def ideation_gate_decision(scorer_output: dict, k: int) -> dict:
    """Map the gate result to the ideation confirmation branch.

    Returns ``{exit, reason, verdict, approved, killing_works, feedback}``:
      * ``exit`` True  -> a novel idea is confirmed; proceed to planning,
      * ``exit`` False -> rejected; ``feedback`` carries the killing work(s)
        verbatim into the next generation round.
    """
    result = evaluate_novelty(scorer_output, k)
    feedback = {
        "verdict": result.verdict,
        "reason": result.reason,
        "killing_works": result.killing_works,
    }
    return {
        "exit": result.approved,
        "reason": result.reason,
        "verdict": result.verdict,
        "approved": result.approved,
        "killing_works": result.killing_works,
        "feedback": feedback,
    }

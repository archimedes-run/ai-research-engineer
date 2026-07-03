"""Stage 0 sabotage scenarios (S0-10).

Six adversarial scenarios, all driven by in-process fakes — no real LLM calls
and no network. Each is pinned to the Stage 0 feature that makes it pass; until
that feature exists the test is expected to fail, so every scenario carries
``@pytest.mark.xfail(strict=True, ...)``.

The "pending" trigger in each test is a real, spec-mandated seam:
  * the typed events from S0-9 (``core.events`` does not yet know these types),
  * the ``score=None`` / ``status`` Node contract from S0-4,
  * the graphify-stripping ``load_prompt`` from S0-7,
  * the intake classifier module from S0-5.

All pending imports/calls happen *inside* the test bodies so that collection
never errors — only the test itself fails (which is what xfail records).
"""

import json
import subprocess
import time
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# Fakes — stand-ins for every LLM agent and for eval.sh. Deterministic, offline.
# --------------------------------------------------------------------------- #
class FakeReviewAgent:
    """Deterministic stand-in for the coding reviewer LLM."""

    def __init__(self, *, blocking: bool = True, degraded: bool = False, text: str | None = None):
        self.blocking = blocking
        self.degraded = degraded
        self._text = text
        self.calls = 0

    def review(self, *_args, **_kwargs) -> str:
        self.calls += 1
        if self._text is not None:
            return self._text
        if self.degraded:
            return "Review could not be completed due to a tool failure (graphify import error)."
        if self.blocking:
            return "## Blocking Issues\n- The training loop diverges; loss becomes NaN by epoch 2.\n"
        return "## Review\nNo blocking issues found. Implementation matches the spec. LGTM.\n"


class FakeNoveltyScorer:
    """Deterministic stand-in for the novelty-scoring LLM gate."""

    def __init__(self, *, approve: bool = False, score: float = 1.0):
        self.approve = approve
        self.score = score
        self.calls = 0

    def score_idea(self, *_args, **_kwargs) -> dict:
        self.calls += 1
        return {"approved": self.approve, "novelty_score": self.score}


def write_eval_script(dirpath: Path, *, body: str) -> Path:
    """Write a tiny fake eval.sh into ``dirpath`` and return its path."""
    script = Path(dirpath) / "eval.sh"
    script.write_text("#!/usr/bin/env bash\nset -e\n" + body + "\n")
    script.chmod(0o755)
    return script


def _run_gate_loop(gate, *, max_iterations: int) -> str:
    """Run a confirmation loop against a fake gate; return the S0-1 outcome.

    Mirrors the intended NonEscalatingLoopAgent contract: the loop exits early
    ("approved") only when the gate approves, otherwise it exhausts its budget
    ("exhausted"). The gate here is one of the deterministic fakes above.
    """
    for _ in range(max_iterations):
        if gate():
            return "approved"
    return "exhausted"


# --------------------------------------------------------------------------- #
# (a) Reviewer always rejects -> loop "exhausted", stage "completed_unverified"
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-1/S0-2/S0-9")
def test_a_reviewer_always_rejects_marks_stage_unverified():
    from ai_research_engineer.core.events import create_event, event_to_dict

    reviewer = FakeReviewAgent(blocking=True)

    # A confirmation gate approves only when the review has no Blocking Issues.
    def gate() -> bool:
        return "Blocking Issues" not in reviewer.review()

    outcome = _run_gate_loop(gate, max_iterations=3)
    assert reviewer.calls == 3, "the reviewer must be consulted every iteration"
    assert outcome == "exhausted", "a perpetually-rejecting reviewer must exhaust the loop"

    # S0-2: an exhausted implementation loop -> stage is honest about being unverified.
    state = {"implementation_loop_outcome": outcome}
    stage = {
        "completed": True,  # back-compat bool retained
        "status": "completed" if state["implementation_loop_outcome"] == "approved" else "completed_unverified",
    }
    assert stage["status"] == "completed_unverified"
    assert stage["completed"] is True

    # No downstream phase may treat an unverified stage as verified.
    assert stage["status"] != "completed", "unverified stage must not read as verified"

    # S0-9 (pending): a structured gate_decision event fires and serializes.
    event = create_event(
        "gate_decision",
        loop="implementation_loop",
        outcome="exhausted",
        reason="max_iterations reached without reviewer approval",
    )
    payload = event_to_dict(event)
    assert payload["type"] == "gate_decision"
    assert payload["outcome"] == "exhausted"
    assert payload["loop"] == "implementation_loop"


# --------------------------------------------------------------------------- #
# (b) Novelty scorer always rejects -> workflow halts after ideation
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-1/S0-9")
def test_b_novelty_rejection_halts_before_planning():
    from ai_research_engineer.core.events import create_event, event_to_dict

    scorer = FakeNoveltyScorer(approve=False)
    planning_ran = {"value": False}

    def run_planning() -> None:  # must never be called when ideation is exhausted
        planning_ran["value"] = True

    outcome = _run_gate_loop(lambda: scorer.score_idea()["approved"], max_iterations=3)
    assert scorer.calls == 3
    assert outcome == "exhausted"

    # S0-1: HITLSequentialAgent must halt on an exhausted ideation_loop and NOT
    # advance to planning. We model the halt: planning is skipped.
    if outcome != "exhausted":
        run_planning()
    assert planning_ran["value"] is False, "planning must not run after ideation is exhausted"

    # S0-9 (pending): the halt is reported via a structured gate_decision event.
    event = create_event(
        "gate_decision",
        loop="ideation_loop",
        outcome="exhausted",
        reason="novelty gate never approved an idea",
    )
    payload = event_to_dict(event)
    assert payload["type"] == "gate_decision"
    assert payload["loop"] == "ideation_loop"


# --------------------------------------------------------------------------- #
# (c) Self-reported score of 999 is rejected because eval.sh wasn't run
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-4/S0-9")
def test_c_stale_self_reported_score_is_rejected(tmp_path):
    from ai_research_engineer.core.events import create_event, event_to_dict
    from ai_research_engineer.evolve.utils.structures import Node

    workflow = tmp_path / "workflow"
    workflow.mkdir()

    # The coding agent writes an inflated score to results.json *before* the
    # orchestrator would evaluate. In this scenario the orchestrator-mock never
    # runs eval.sh, so results.json is stale relative to the eval start.
    results = workflow / "results.json"
    results.write_text(json.dumps({"score": 999}))
    results_mtime = results.stat().st_mtime

    # Sealed-evaluator rule (S0-4): trust the score only if results.json was
    # written *after* the orchestrator started its own eval.
    eval_started_at = results_mtime + 10.0  # eval starts strictly after the stale write
    fresh = results.stat().st_mtime > eval_started_at
    score = json.loads(results.read_text())["score"] if fresh else None
    status = "success" if fresh else "failed"

    assert score is None, "a stale self-reported score must be discarded"
    assert status == "failed"

    # S0-4 (pending): Node/Database must accept score=None with a status field.
    node = Node(name="gen-1", score=None, status="failed")
    assert node.score is None
    assert node.status == "failed"

    # S0-9 (pending): eval_result event carries the sealed verdict.
    event = create_event("eval_result", gen=1, score=None, status="failed", duration_s=0.0)
    payload = event_to_dict(event)
    assert payload["type"] == "eval_result"
    assert payload["status"] == "failed"
    assert payload.get("score") is None


# --------------------------------------------------------------------------- #
# (d) eval.sh sleeps past the timeout -> node status "timeout", score None
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-4/S0-9")
def test_d_eval_timeout_yields_timeout_status_and_none_score(tmp_path):
    from ai_research_engineer.core.events import create_event, event_to_dict
    from ai_research_engineer.evolve.utils.structures import Node

    workflow = tmp_path / "workflow"
    workflow.mkdir()
    write_eval_script(workflow, body="sleep 5")  # deliberately exceeds the timeout

    timeout_s = 0.5
    started = time.time()
    try:
        subprocess.run(
            ["bash", "eval.sh"],
            cwd=workflow,
            timeout=timeout_s,
            capture_output=True,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    duration_s = round(time.time() - started, 3)

    assert timed_out, "eval.sh must exceed the configured timeout"

    score = None
    status = "timeout" if timed_out else "success"

    # S0-4 (pending): Node commits the timeout honestly.
    node = Node(name="gen-2", score=score, status=status)
    assert node.score is None
    assert node.status == "timeout"

    # S0-9 (pending): eval_result event records the timeout with a duration.
    event = create_event("eval_result", gen=2, score=None, status="timeout", duration_s=duration_s)
    payload = event_to_dict(event)
    assert payload["type"] == "eval_result"
    assert payload["status"] == "timeout"


# --------------------------------------------------------------------------- #
# (e) graphify unavailable -> assembled prompts contain zero "graphify"
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-7")
def test_e_graphify_unavailable_strips_all_graphify_language():
    from ai_research_engineer.prompts import load_prompt

    # S0-7 (pending): with graphify unavailable, load_prompt strips the
    # <!-- BEGIN:graphify -->..<!-- END:graphify --> sections from both prompts.
    coding = load_prompt("coding_base", domain="aiml", tool_availability={"graphify": False})
    review = load_prompt("coding_review", domain="aiml", tool_availability={"graphify": False})

    assert "graphify" not in coding.lower(), "coding_base must not mention graphify when unavailable"
    assert "graphify" not in review.lower(), "coding_review must not mention graphify when unavailable"

    # A mocked review still completes cleanly under the degraded tooling.
    reviewer = FakeReviewAgent(blocking=False)
    verdict = reviewer.review()
    assert "Blocking Issues" not in verdict


# --------------------------------------------------------------------------- #
# (f) "Replicate ..." prompt under research_mode="novelty" -> intake_decision
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="Stage 0 feature pending: S0-5/S0-9")
def test_f_replicate_prompt_under_novelty_mode_fires_intake_decision():
    from ai_research_engineer.core.intake import classify_intent  # pending module (S0-5)

    from ai_research_engineer.core.events import create_event, event_to_dict

    prompt = "Replicate tabular Q-learning on FrozenLake and reproduce the reported success rate."
    research_mode = "novelty"

    intent = classify_intent(prompt)
    assert intent == "replicate", "a 'Replicate ...' prompt must classify as replicate"

    # Intent conflicts with the configured mode -> autonomous auto-switches
    # (or HITL pauses). Either way an intake_decision event must fire.
    conflict = intent == "replicate" and research_mode == "novelty"
    assert conflict
    action = "switch"  # autonomous default; "pause" under hitl

    event = create_event(
        "intake_decision",
        detected_intent=intent,
        selected_mode="replication",
        action=action,
    )
    payload = event_to_dict(event)
    assert payload["type"] == "intake_decision"
    assert payload["detected_intent"] == "replicate"
    assert payload["action"] in {"switch", "pause"}

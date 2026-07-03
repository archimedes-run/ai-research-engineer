"""Stage 0 sabotage scenarios (S0-10).

Six adversarial scenarios, all driven by in-process fakes — no real LLM calls
and no network. Each is pinned to the Stage 0 feature that makes it pass.

Scenarios (a) and (b) exercise implemented features (S0-1 loop outcomes and
S0-2 honest stages) and drive the real seams. The remaining scenarios pin
features that are still pending, so they carry
``@pytest.mark.xfail(strict=True, ...)``:
  * the typed events from S0-9 (``core.events`` does not yet know these types),
  * the ``score=None`` / ``status`` Node contract from S0-4,
  * the graphify-stripping ``load_prompt`` from S0-7,
  * the intake classifier module from S0-5.

Pending imports/calls happen *inside* the still-xfail test bodies so that
collection never errors — only the test itself fails (which is what xfail
records).
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


# --------------------------------------------------------------------------- #
# (a) Reviewer always rejects -> loop "exhausted", stage "completed_unverified"
# --------------------------------------------------------------------------- #
def test_a_reviewer_always_rejects_marks_stage_unverified():
    # S0-1/S0-2/S0-9 are implemented — this scenario now exercises the real seams.
    from ai_research_engineer.agents.adk.agent import classify_loop_outcome
    from ai_research_engineer.agents.adk.stage_orchestrator import derive_stage_status, stage_completed_flag
    from ai_research_engineer.core.events import create_event, event_to_dict

    reviewer = FakeReviewAgent(blocking=True)

    # Mocked confirmation loop: a gate approves only when the review has no
    # Blocking Issues. A perpetually-rejecting reviewer never approves.
    approved = False
    for _ in range(3):
        if "Blocking Issues" not in reviewer.review():
            approved = True
            break
    assert reviewer.calls == 3, "the reviewer must be consulted every iteration"

    # S0-1: the loop records a typed outcome — here "exhausted".
    outcome = classify_loop_outcome(approved)
    assert outcome == "exhausted", "a perpetually-rejecting reviewer must exhaust the loop"

    # S0-2: an exhausted implementation loop -> stage is honest about being unverified,
    # while the legacy `completed` bool stays True (derived) for back-compat.
    status = derive_stage_status(outcome)
    stage = {"status": status, "completed": stage_completed_flag(status)}
    assert stage["status"] == "completed_unverified"
    assert stage["completed"] is True
    assert stage["status"] != "completed", "unverified stage must not read as verified"

    # S0-9: a structured gate_decision event fires and serializes.
    event = create_event(
        "gate_decision",
        loop="implementation_loop",
        outcome=outcome,
        reason="max_iterations reached without reviewer approval",
    )
    payload = event_to_dict(event)
    assert payload["type"] == "gate_decision"
    assert payload["outcome"] == "exhausted"
    assert payload["loop"] == "implementation_loop"


# --------------------------------------------------------------------------- #
# (b) Novelty scorer always rejects -> workflow halts after ideation
# --------------------------------------------------------------------------- #
def test_b_novelty_rejection_halts_before_planning():
    # S0-1 is implemented — drive the REAL HITLSequentialAgent and prove that an
    # exhausted ideation loop halts the workflow before planning ever runs.
    import asyncio
    from unittest.mock import MagicMock

    from ai_research_engineer.agents.adk.hitl_sequential import HITLSequentialAgent, loop_outcome_action
    from ai_research_engineer.core.events import create_event, event_to_dict

    scorer = FakeNoveltyScorer(approve=False)

    class _FakeIdeationLoop:
        """Mocked ideation loop: never approved -> records 'exhausted' (S0-1)."""

        name = "ideation_loop"

        def __init__(self):
            self.calls = 0

        async def run_async(self, ctx):
            self.calls += 1
            approved = False
            for _ in range(3):
                if scorer.score_idea()["approved"]:
                    approved = True
                    break
            ctx.session.state["ideation_loop_outcome"] = "approved" if approved else "exhausted"
            if False:  # make this an async generator without yielding events
                yield

    class _FakePlanningLoop:
        """Must never run once ideation is exhausted."""

        name = "high_level_planning_loop"

        def __init__(self):
            self.calls = 0

        async def run_async(self, ctx):
            self.calls += 1
            if False:
                yield

    ideation = _FakeIdeationLoop()
    planning = _FakePlanningLoop()
    workflow = HITLSequentialAgent(sub_agents=[ideation, planning], hitl_enabled=False)

    ctx = MagicMock()
    ctx.session.state = {}
    ctx.session.id = "sabotage-b"

    async def _drain():
        return [event async for event in workflow._run_async_impl(ctx)]

    events = asyncio.run(_drain())

    assert ideation.calls == 1
    assert scorer.calls == 3
    assert ctx.session.state["ideation_loop_outcome"] == "exhausted"

    # The core assertion: planning never ran — the workflow halted after ideation.
    assert planning.calls == 0, "planning must not run after ideation is exhausted"
    assert loop_outcome_action("ideation_loop", "exhausted") == "halt"

    # A clear terminal halt event was emitted.
    texts = [
        part.text for event in events if event.content for part in event.content.parts if getattr(part, "text", None)
    ]
    assert any("halted" in t.lower() for t in texts), "a terminal halt event must be emitted"

    # S0-9: the halt is reportable as a structured gate_decision event.
    payload = event_to_dict(
        create_event(
            "gate_decision",
            loop="ideation_loop",
            outcome="exhausted",
            reason="novelty gate never approved an idea",
        )
    )
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

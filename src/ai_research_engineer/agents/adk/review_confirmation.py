"""
Review Confirmation Agent with structured output.

This module provides a specialized agent that determines whether to exit a review
loop based on the review feedback. It uses structured output (output_schema) instead
of normal text output and does not have access to any tools.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event, EventActions
from google.adk.planners import BuiltInPlanner
from google.genai import types
from pydantic import BaseModel, Field, PrivateAttr
from typing_extensions import override

from ai_research_engineer.agents.adk.loop_detection import LoopDetectionAgent
from ai_research_engineer.agents.adk.utils import REVIEW_MODEL, get_generate_content_config
from ai_research_engineer.core.config import get_prefilter_k
from ai_research_engineer.core.novelty.falsifier import DEFAULT_MAX_ROUNDS, falsifier_flow
from ai_research_engineer.core.novelty.gate import evaluate_novelty, ideation_gate_decision
from ai_research_engineer.core.novelty.prefilter import top_similar
from ai_research_engineer.core.novelty.tournament import build_audit, select_winner
from ai_research_engineer.prompts import load_prompt


logger = logging.getLogger(__name__)


def _create_clear_decision_callback(state_key: str):
    """
    Factory function to create a before-agent callback that clears stale decisions.

    This callback clears any previous decision from the state before the agent runs,
    preventing state pollution from previous invocations or other agents.

    Parameters
    ----------
    state_key : str
        The state key to clear

    Returns
    -------
    Callable
        A callback function that clears the specified state key
    """

    def clear_decision_callback(callback_context: CallbackContext):
        """Clear stale decision from state before agent runs."""
        ctx = callback_context._invocation_context
        state = ctx.session.state

        if state_key in state:
            old_value = state[state_key]
            del state[state_key]
            logger.debug(f"[ReviewConfirmation] Cleared stale decision from state key '{state_key}': {old_value}")
        else:
            logger.debug(f"[ReviewConfirmation] No stale decision to clear for key '{state_key}'")

    return clear_decision_callback


def _create_exit_loop_callback(state_key: str):
    """
    Factory function to create an after-agent callback that conditionally exits the loop.

    This callback is invoked after the agent completes. It reads the agent's
    structured output from the specified state key and only sets the escalate
    flag if the agent decided to exit.

    To ensure the escalate flag is properly propagated, this callback returns
    an empty Content object, which triggers event creation in ADK's
    _handle_after_agent_callback method.

    Parameters
    ----------
    state_key : str
        The state key to read the decision from

    Returns
    -------
    Callable
        A callback function that reads from the specified state key and conditionally escalates
    """

    def exit_loop_callback(callback_context: CallbackContext):
        """
        After-agent callback that conditionally exits the loop by escalating.

        Parameters
        ----------
        callback_context : CallbackContext
            The callback context with invocation context access

        Returns
        -------
        Optional[types.Content]
            Empty content to trigger event creation when exiting the loop
        """
        ctx = callback_context._invocation_context
        state = ctx.session.state

        # Get the review confirmation decision from state using agent-specific key
        decision = state.get(state_key)

        if not decision:
            logger.warning(f"[ReviewConfirmation] No decision found in state key '{state_key}' - not exiting loop")
            return None

        # Validate that decision is a dictionary before calling .get()
        if not isinstance(decision, dict):
            logger.error(
                f"[ReviewConfirmation] Invalid decision type in key '{state_key}': {type(decision)} - not exiting loop"
            )
            return None

        # Check if the agent decided to exit
        should_exit = decision.get("exit", False)
        reason = decision.get("reason", "No reason provided")

        if should_exit:
            logger.info(f"[ReviewConfirmation] Exiting loop (key='{state_key}') - Reason: {reason}")
            # Set escalate flag on the event_actions
            if hasattr(callback_context, '_event_actions') and callback_context._event_actions:
                callback_context._event_actions.escalate = True
            else:
                logger.warning("[ReviewConfirmation] No event_actions available - cannot escalate")
                return None

            # Return empty content to trigger event creation with the escalate flag
            # This ensures NonEscalatingLoopAgent receives the escalate signal
            return types.Content(role="model", parts=[])
        else:
            logger.info(f"[ReviewConfirmation] Continuing loop (key='{state_key}') - Reason: {reason}")
            return None

    return exit_loop_callback


# Output schema for review confirmation (Pydantic BaseModel)
class ReviewConfirmationOutput(BaseModel):
    """Schema for review confirmation decision."""

    exit: bool = Field(
        description="Whether to exit the review loop. True if implementation is approved, False if more work is needed."
    )
    reason: str = Field(description="Brief explanation of the decision to exit or continue.")


# Keep for backwards compatibility
REVIEW_CONFIRMATION_OUTPUT_SCHEMA = ReviewConfirmationOutput


def _compute_novelty_verdict(state: dict, k: int) -> dict:
    """Parse the scorer output from state and return the code-authoritative
    ideation verdict (also cached in ``state['novelty_verdict']``)."""
    raw = state.get("novelty_scorer_feedback")
    scorer_output = raw
    if isinstance(raw, str):
        try:
            scorer_output = json.loads(raw)
        except Exception:
            scorer_output = {}
    if not isinstance(scorer_output, dict):
        scorer_output = {}
    verdict = ideation_gate_decision(scorer_output, k)
    state["novelty_verdict"] = verdict
    return verdict


def _parse_json_maybe(raw) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def _parse_candidates(raw) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


def _decision_to_verdict(decision: dict) -> dict:
    """Shape a falsifier_flow decision into the novelty_verdict the gate reads."""
    approved = bool(decision.get("approved"))
    killing = decision.get("killing_works", [])
    return {
        "exit": approved,
        "approved": approved,
        "verdict": decision.get("verdict"),
        "reason": decision.get("reason"),
        "killing_works": killing,
        "feedback": {"verdict": decision.get("verdict"), "reason": decision.get("reason"), "killing_works": killing},
        "falsifier_rounds": decision.get("falsifier_rounds"),
    }


def _idea_from_state(state: dict) -> dict:
    """Build the {title, description} the prefilter ranks against from state."""
    raw = state.get("generated_ideas")
    parsed = _parse_json_maybe(raw)
    if parsed.get("title") or parsed.get("description"):
        return {"title": parsed.get("title") or "", "description": parsed.get("description") or ""}
    return {"title": "", "description": raw if isinstance(raw, str) else json.dumps(raw or "")}


class PrefilterAgent(BaseAgent):
    """S2-2 (live graph) — embedding prefilter between recall and the scorer.

    Reads the recall candidates from ``state['recall_candidates']`` and the idea
    from ``state['generated_ideas']``, ranks with the SHARED ``top_similar``, and
    writes the top-k to ``state['prefiltered_works']`` — the exact key the scorer
    prompt reads and the re-verdict agent re-injects into. Uses the same
    ``top_similar`` implementation as ``pipeline.evaluate_idea`` (no parallel logic).
    """

    _k: Any = PrivateAttr()

    def __init__(self, k: Optional[int] = None, name: str = "prefilter_agent"):
        super().__init__(name=name, description="Ranks recall candidates and writes the top-k for the scorer.")
        self._k = k

    def _info(self, text: str) -> Event:
        return Event(author=self.name, content=types.Content(role="model", parts=[types.Part(text=text)]),
                     turn_complete=False)

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        k = self._k if self._k is not None else get_prefilter_k()
        candidates = _parse_candidates(state.get("recall_candidates"))
        ranked = top_similar(_idea_from_state(state), candidates, k=k)
        state["prefiltered_works"] = json.dumps(ranked)
        yield self._info(f"🔎 Prefilter: {len(candidates)} recall candidates → top {len(ranked)} for the scorer.")


def create_prefilter_agent(k: Optional[int] = None) -> PrefilterAgent:
    """Factory for the S2-2 prefilter agent (sits between recall and the scorer)."""
    return PrefilterAgent(k=k)


def _norm_idea(x) -> dict:
    if isinstance(x, dict):
        return {"title": x.get("title") or "", "description": x.get("description") or x.get("why_novel") or ""}
    return {"title": "", "description": str(x)}


def _parse_ideas(raw) -> list:
    """Parse the generator output into a list of {title, description} ideas."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            data = raw
    if isinstance(data, list):
        return [_norm_idea(x) for x in data if x]
    if isinstance(data, dict):
        for key in ("ideas", "new_ideas", "proposed_ideas", "directions"):
            if isinstance(data.get(key), list):
                return [_norm_idea(x) for x in data[key] if x]
        if data.get("title") or data.get("description"):
            return [_norm_idea(data)]
    if isinstance(raw, str) and raw.strip():
        return [{"title": "", "description": raw.strip()}]
    return []


class IdeationTournamentAgent(BaseAgent):
    """S2-6 — runs one ideation round as a tournament over 4-6 ideas.

    Recall (S2-1) runs ONCE on the union of the ideas' queries; each idea is then
    prefiltered + scored + falsified against that shared corpus by re-using the
    prefilter / scorer / re-verdict sub-agents. The winner is chosen by the SHARED
    ``select_winner`` ranking; the runner-up (with its audit) is stored in
    ``state['ideation_runner_up']``. The final ``novelty_verdict`` (winner ->
    approve, none -> reject) is handed to the code gate, so zero approved ideas
    exhaust the loop per Stage 0 semantics — never a silent continue.
    """

    _k: Any = PrivateAttr()
    _prefilter: Any = PrivateAttr()
    _scorer: Any = PrivateAttr()
    _reverdict: Any = PrivateAttr()
    _working_dir: Any = PrivateAttr()

    def __init__(self, prefilter_agent, scorer_agent, reverdict_agent, k: int = 12,
                 working_dir: str = "", name: str = "ideation_tournament_agent"):
        super().__init__(name=name, description="Runs the ideation tournament (shared recall corpus, ranked winner).")
        self._prefilter = prefilter_agent
        self._scorer = scorer_agent
        self._reverdict = reverdict_agent
        self._k = k
        self._working_dir = working_dir

    def _info(self, text: str) -> Event:
        return Event(author=self.name, content=types.Content(role="model", parts=[types.Part(text=text)]),
                     turn_complete=False)

    def _recall_once(self, ideas: list) -> list:
        """One recall over the union of the ideas' text -> shared candidate corpus."""
        import dataclasses

        from ai_research_engineer.core.novelty.recall import recall_prior_work

        union = {"title": "", "description": " ".join(
            f"{i.get('title', '')} {i.get('description', '')}".strip() for i in ideas)}
        try:
            return [dataclasses.asdict(c) for c in recall_prior_work(union, self._working_dir)]
        except Exception as exc:
            logger.warning("[tournament] recall failed: %s", exc)
            return []

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        ideas = _parse_ideas(state.get("generated_ideas"))
        if not ideas:
            state["novelty_verdict"] = {"approved": False, "verdict": "reject", "reason": "no ideas generated"}
            yield self._info("🏟️ Tournament: no ideas to evaluate.")
            return

        corpus = self._recall_once(ideas)          # S2-1 recall — ONCE for the round
        state["recall_candidates"] = json.dumps(corpus)

        audits = []
        for idx, idea in enumerate(ideas):
            state["generated_ideas"] = json.dumps(idea)
            state.pop("novelty_verdict", None)
            for sub in (self._prefilter, self._scorer, self._reverdict):
                async for ev in sub.run_async(ctx):
                    yield ev
            verdict = state.get("novelty_verdict") or {}
            table = _parse_json_maybe(state.get("novelty_scorer_feedback")).get("differentiation_table", [])
            decision = {
                "approved": bool(verdict.get("approved")),
                "verdict": verdict.get("verdict"),
                "reason": verdict.get("reason"),
                "table": table,
                "prefiltered": _parse_candidates(state.get("prefiltered_works")),
                "killing_works": verdict.get("killing_works", []),
            }
            audits.append(build_audit(idx, idea, decision))

        selection = select_winner(audits)
        state["ideation_audits"] = audits
        if selection["winner"]:
            state["generated_ideas"] = json.dumps(selection["winner"]["idea"])
            state["novelty_verdict"] = {"approved": True, "verdict": "approve",
                                        "reason": "tournament winner", "killing_works": []}
            if selection["runner_up"]:
                state["ideation_runner_up"] = selection["runner_up"]
            yield self._info(
                f"🏟️ Tournament: {selection['approved_count']}/{len(ideas)} approved — winner selected"
                + (", runner-up stored." if selection["runner_up"] else ".")
            )
        else:
            state["novelty_verdict"] = {"approved": False, "verdict": "reject",
                                        "reason": "no idea survived the novelty audit", "killing_works": []}
            yield self._info(f"🏟️ Tournament: 0/{len(ideas)} approved — ideation will regenerate or exhaust.")


def create_ideation_tournament_agent(prefilter_agent, scorer_agent, reverdict_agent, k: int = 12,
                                     working_dir: str = "") -> IdeationTournamentAgent:
    """Factory for the S2-6 ideation tournament agent."""
    return IdeationTournamentAgent(prefilter_agent, scorer_agent, reverdict_agent, k=k, working_dir=working_dir)


class FalsifierReVerdictAgent(BaseAgent):
    """S2-4 — runs the adversarial falsifier re-verdict loop in the live graph.

    Sits between the scorer and the code gate. On a scorer APPROVE it drives the
    SHARED ``falsifier_flow`` control machine, re-invoking the falsifier and
    scorer LLM agents on the augmented candidate set (up to 2 rounds), and writes
    the FINAL code-gate verdict to ``state['novelty_verdict']`` for the gate. It
    adds no control-flow logic of its own — it only pumps ``falsifier_flow``. The
    outer generation loop fires only on the gate's final REJECT, not on falsifier
    finds.
    """

    _k: Any = PrivateAttr()
    _scorer: Any = PrivateAttr()
    _falsifier: Any = PrivateAttr()

    def __init__(self, scorer_agent, falsifier_agent, k: int = 12, name: str = "falsifier_reverdict_agent"):
        super().__init__(name=name, description="Drives the shared falsifier re-verdict control flow (no new logic).")
        self._scorer = scorer_agent
        self._falsifier = falsifier_agent
        self._k = k

    def _info(self, text: str) -> Event:
        return Event(author=self.name, content=types.Content(role="model", parts=[types.Part(text=text)]),
                     turn_complete=False)

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        initial = _parse_json_maybe(state.get("novelty_scorer_feedback"))
        base = evaluate_novelty(initial, self._k)

        if not base.approved:
            # A scorer REJECT stands; the falsifier only probes approvals.
            state["novelty_verdict"] = ideation_gate_decision(initial, self._k)
            yield self._info("🔬 Falsifier skipped — scorer did not approve.")
            return

        idea = {"generated_ideas": state.get("generated_ideas")}
        candidates = _parse_candidates(state.get("prefiltered_works"))
        flow = falsifier_flow(idea, base, candidates, self._k, DEFAULT_MAX_ROUNDS)
        decision = None
        try:
            request = flow.send(None)
            while True:
                kind, _idea, payload = request
                if kind == "falsify":
                    async for ev in self._falsifier.run_async(ctx):
                        yield ev
                    result = state.get("novelty_falsifier_feedback")
                else:  # "score" — inject the augmented candidate set, re-run scorer
                    state["prefiltered_works"] = json.dumps(payload)
                    async for ev in self._scorer.run_async(ctx):
                        yield ev
                    result = _parse_json_maybe(state.get("novelty_scorer_feedback"))
                request = flow.send(result)
        except StopIteration as stop:
            decision = stop.value

        state["novelty_verdict"] = _decision_to_verdict(decision or {})
        yield self._info(f"🔬 Falsifier re-verdict: {(decision or {}).get('verdict')} — {(decision or {}).get('reason')}")


def create_falsifier_reverdict_agent(scorer_agent, falsifier_agent, k: int = 12) -> FalsifierReVerdictAgent:
    """Factory for the S2-4 falsifier re-verdict agent (sits between the scorer
    and the ideation gate)."""
    return FalsifierReVerdictAgent(scorer_agent, falsifier_agent, k=k)


def _audit_reason(verdict: dict) -> str:
    """Audit-trail reason: killing work(s) verbatim on a core overlap,
    ``"incomplete_differentiation"`` on an incomplete table, else the reason."""
    if verdict.get("approved"):
        return verdict.get("reason") or "approved"
    killing = verdict.get("killing_works") or []
    if killing:
        return "core overlap — killing work(s): " + json.dumps(killing)
    if (verdict.get("reason") or "") == "incomplete differentiation":
        return "incomplete_differentiation"
    return verdict.get("reason") or "rejected"


class IdeationGateAgent(BaseAgent):
    """Code-only ideation novelty gate (S2-3) — no LLM call.

    Reads the code-computed novelty verdict (``state['novelty_verdict']``,
    recomputing from the scorer output if absent) and sets the loop exit
    directly: ``approved`` -> escalate (exit True); otherwise no escalate (the
    generator regenerates). Records a Stage 0 gate_decision so the sabotage suite
    and audit trail read consistently. Scoped to ideation only — planning, paper,
    and implementation confirmations keep their LLM agents.
    """

    _k: Any = PrivateAttr()

    def __init__(self, k: int = 12, name: str = "ideation_gate_agent"):
        super().__init__(
            name=name,
            description="Code-authoritative ideation novelty gate (no LLM).",
        )
        self._k = k

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        # The falsifier re-verdict agent (S2-4) writes the FINAL novelty_verdict
        # upstream; fall back to computing it from the scorer output if it ran
        # standalone (e.g. no falsifier stage wired).
        verdict = state.get("novelty_verdict")
        if not isinstance(verdict, dict):
            verdict = _compute_novelty_verdict(state, self._k)

        approved = bool(verdict.get("approved"))
        reason = _audit_reason(verdict)

        # Stage 0 gate_decision entry (mirrors NonEscalatingLoopAgent) so the
        # streaming layer emits a consistent GateDecisionEvent for the audit trail.
        decisions = state.get("_gate_decisions")
        if not isinstance(decisions, list):
            decisions = []
        decisions.append(
            {
                "loop": "ideation_novelty_gate",
                "outcome": "approved" if approved else "rejected",
                "reason": reason,
            }
        )
        state["_gate_decisions"] = decisions
        logger.info("[ideation_gate] code verdict=%s — %s", verdict.get("verdict"), reason)

        text = (
            f"🚦 **Ideation novelty gate** (code): "
            f"**{'APPROVE' if approved else 'REJECT'}** — {reason}"
        )
        yield Event(
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            actions=EventActions(escalate=approved),
            turn_complete=False,
        )


def create_ideation_gate_agent(k: int = 12) -> IdeationGateAgent:
    """Factory for the code-only ideation novelty gate (replaces the ideation
    confirmation LLM)."""
    return IdeationGateAgent(k=k)


def create_review_confirmation_agent(
    auto_exit_on_completion: bool = False,
    prompt_name: str = "plan_review_confirmation",
) -> LoopDetectionAgent:
    """
    Create a review confirmation agent with structured output.

    This agent analyzes review feedback and determines whether the review loop
    should exit. It uses structured output (output_schema) to ensure consistent
    JSON responses and does not have access to any tools.

    Each agent instance uses a unique state key based on the prompt_name to prevent
    state pollution between different review confirmation agents (e.g., plan review
    vs implementation review).

    Parameters
    ----------
    auto_exit_on_completion : bool, optional
        If True, automatically exit the loop after agent completion by escalating.
        This uses an after_agent_callback to set escalate=True. Defaults to False.
    prompt_name : str, optional
        Name of the prompt file to load (default: "plan_review_confirmation").
        This is also used to generate a unique state key for this agent instance.

    Returns
    -------
    LoopDetectionAgent
        The configured review confirmation agent

    Examples
    --------
    >>> agent = create_review_confirmation_agent()
    >>> # Agent will output structured JSON like:
    >>> # {"exit": true, "reason": "All issues resolved"}
    >>> # or
    >>> # {"exit": false, "reason": "Critical bugs remain"}
    >>>
    >>> # With auto-exit enabled:
    >>> agent = create_review_confirmation_agent(auto_exit_on_completion=True)
    >>> # Agent will automatically exit the loop after completion

    Notes
    -----
    The agent uses a unique state key derived from the prompt_name to prevent
    cross-contamination between different review confirmation agents. For example:
    - "plan_review_confirmation" -> state key: "plan_review_confirmation_decision"
    - "implementation_review_confirmation" -> state key: "implementation_review_confirmation_decision"

    A before_agent_callback is used to clear any stale decisions before the agent runs,
    providing defense-in-depth against state pollution.
    """
    logger.info(f"[AgenticDS] Creating review confirmation agent (prompt={prompt_name})")

    instruction = load_prompt(prompt_name)

    # Create unique state key per agent instance to prevent cross-contamination
    state_key = f"{prompt_name}_decision"
    logger.debug(f"[AgenticDS] Using state key: {state_key}")

    # Create agent-specific callbacks using factory functions
    # These closures capture the state_key for this specific agent instance
    before_callback = _create_clear_decision_callback(state_key)
    after_callback = _create_exit_loop_callback(state_key) if auto_exit_on_completion else None

    agent = LoopDetectionAgent(
        name=f"{prompt_name}_agent",
        model=REVIEW_MODEL,
        description="Determines whether to exit the review loop based on implementation status.",
        instruction=instruction,
        tools=[],  # No tools - structured output only
        planner=BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=-1,
            ),
        ),
        generate_content_config=get_generate_content_config(temperature=0.0),
        output_schema=REVIEW_CONFIRMATION_OUTPUT_SCHEMA,  # Use output_schema for structured JSON
        output_key=state_key,  # Use unique state key per agent instance
        before_agent_callback=before_callback,  # Clear stale decisions before agent runs
        after_agent_callback=after_callback,  # Conditionally escalate after agent completes
    )

    logger.info(
        f"[AgenticDS] Review confirmation agent created successfully "
        f"(prompt={prompt_name}, state_key={state_key}, auto_exit_on_completion={auto_exit_on_completion})"
    )

    return agent

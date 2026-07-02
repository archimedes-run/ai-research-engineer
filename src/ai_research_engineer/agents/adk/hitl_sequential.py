"""
HITLSequentialAgent — SequentialAgent wrapper with Human-in-the-Loop gates.

When hitl_enabled=False (the default / Autonomous mode) this agent is
byte-identical to SequentialAgent: no pauses, no checkpoints, no extra state.

When hitl_enabled=True (Supervised mode) the agent checks a set of named
gates after certain sub-agents. If a gate is active the run is suspended:
  1. Serialise JSON-able session state to a checkpoint.
  2. Create a hitl_request row (status=pending).
  3. Set HITL state keys on the session.
  4. Mark the session awaiting_input in RunStore.
  5. Return — the SSE stream will emit HITLRequestEvent and close.

On resume (a new AIEngineer with the same session_id and a restored
initial_state containing the injected answer), _hitl_completed_agents
records which sub-agents already ran so they are skipped.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, AsyncGenerator, Dict, List, Optional

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.adk.utils.context_utils import Aclosing
from pydantic import PrivateAttr
from typing_extensions import override


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_SENTINEL: List = []  # empty list used to bypass Pydantic sub_agents validation

# Gates active by default (on) when hitl_enabled=True.
# Key = sub-agent name that triggers the gate AFTER it finishes.
# Value = gate_key stored in state and sent in HITLRequestEvent.
DEFAULT_GATES: Dict[str, str] = {
    "planning_tree_agent": "gate_plan",
    "reference_verifier_agent": "gate_verification",
}

# Gates that exist but are OFF by default.
# "ideation_tree_agent": "gate_ideation"
# "paper_writing_loop": "gate_paper"
# "stage_orchestrator": "gate_stage"  (deferred to Phase C.2)

_HITL_QUESTION: Dict[str, str] = {
    "gate_plan": (
        "The research plan has been generated. "
        "Review the plan and reply 'approve' to proceed, or provide feedback to revise."
    ),
    "gate_verification": (
        "The reference verifier has completed. "
        "Reply 'approve' to compile the PDF, or provide feedback."
    ),
}

_HITL_DEFAULT_QUESTION = (
    "The workflow has paused for human review. "
    "Reply 'approve' to continue, or provide feedback."
)


def _serialize_state(state: dict) -> str:
    """Serialise only JSON-safe values from session state."""
    safe: Dict = {}
    for k, v in state.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            logger.debug("[HITL] Skipping non-serialisable state key: %s", k)
    return json.dumps(safe)


class HITLSequentialAgent(BaseAgent):
    """
    Drop-in replacement for SequentialAgent with optional HITL gates.

    Parameters
    ----------
    sub_agents : list of BaseAgent
        Ordered list of agents to run sequentially.
    gates : dict, optional
        Mapping of agent-name → gate_key.  Defaults to DEFAULT_GATES.
        Supply an empty dict to disable all gates even in supervised mode.
    hitl_enabled : bool
        When False (default) the agent is byte-identical to SequentialAgent.
    working_dir : str, optional
        Working directory used to build tree context for gate prompts.
    session_store_session_id : str, optional
        Session ID used to call RunStore; injected by create_agent/api.py.
    """

    _gates: Dict[str, str] = PrivateAttr(default_factory=dict)
    _hitl_enabled: bool = PrivateAttr(default=False)
    _working_dir: str = PrivateAttr(default="")
    _store_session_id: str = PrivateAttr(default="")

    def __init__(
        self,
        sub_agents: list,
        gates: Optional[Dict[str, str]] = None,
        hitl_enabled: bool = False,
        working_dir: str = "",
        store_session_id: str = "",
        **kwargs,
    ) -> None:
        kwargs.setdefault("name", "ai_research_engineer_workflow")
        kwargs.setdefault(
            "description",
            "Complete AI Research Engineer workflow with adaptive stage-wise implementation.",
        )
        # Pass an empty list to Pydantic to bypass BaseAgent type validation.
        # Actual agents are stored in `_hitl_sub_agents` via object.__setattr__,
        # which bypasses Pydantic's __setattr__ validation entirely.
        super().__init__(sub_agents=[], **kwargs)
        object.__setattr__(self, "_hitl_sub_agents", sub_agents)
        self._gates = gates if gates is not None else dict(DEFAULT_GATES)
        self._hitl_enabled = hitl_enabled
        self._working_dir = working_dir
        self._store_session_id = store_session_id

    # ------------------------------------------------------------------
    # Main implementation
    # ------------------------------------------------------------------

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        _agents = self._hitl_sub_agents  # access via plain Python attr

        if not self._hitl_enabled:
            # Autonomous mode: exactly like SequentialAgent
            for agent in _agents:
                async with Aclosing(agent.run_async(ctx)) as agen:
                    async for event in agen:
                        yield event
            return

        # Supervised mode
        state = ctx.session.state
        completed: List[str] = list(state.get("_hitl_completed_agents") or [])

        for agent in _agents:
            agent_name = agent.name

            # Fast-forward already-completed agents (resume path)
            if agent_name in completed:
                logger.info("[HITL] Skipping already-completed agent: %s", agent_name)
                continue

            # Run the agent
            async with Aclosing(agent.run_async(ctx)) as agen:
                async for event in agen:
                    yield event

            # Mark completed
            completed.append(agent_name)
            state["_hitl_completed_agents"] = completed

            # Check gate
            gate_key = self._gates.get(agent_name)
            if gate_key:
                paused = await self._check_gate(ctx, gate_key, agent_name)
                if paused:
                    return  # caller (_stream_responses) will emit HITLRequestEvent

    # ------------------------------------------------------------------
    # Gate logic
    # ------------------------------------------------------------------

    async def _check_gate(
        self, ctx: InvocationContext, gate_key: str, agent_name: str
    ) -> bool:
        """
        Persist checkpoint and HITL request, set pause state.

        Returns True if the workflow should pause, False to continue.
        """
        state = ctx.session.state
        session_id = ctx.session.id

        # Build context markdown from tree (fail-soft)
        context_md = self._build_context_md(session_id)

        # Serialise state to checkpoint
        try:
            from ai_research_engineer.server.run_store import RunStore  # noqa: PLC0415

            state_json = _serialize_state(dict(state))
            RunStore.save_checkpoint(session_id, gate_key, state_json)

            request = RunStore.create_hitl_request(
                session_id=session_id,
                stage_key=gate_key,
                question=_HITL_QUESTION.get(gate_key, _HITL_DEFAULT_QUESTION),
                context_md=context_md,
            )

            # Write pause state — read by _stream_responses after runner loop
            state["_hitl_paused"] = gate_key
            state["_hitl_request_id"] = request["request_id"]
            state["_hitl_question"] = request["question"]
            state["_hitl_context_md"] = context_md

            # Update session status
            RunStore.update_session(session_id, {"status": "awaiting_input"})

            logger.info(
                "[HITL] Paused at gate=%s, request_id=%s, session=%s",
                gate_key,
                request["request_id"],
                session_id,
            )
            return True

        except Exception as exc:
            logger.error("[HITL] Gate checkpoint failed (fail-soft, continuing): %s", exc, exc_info=True)
            return False

    def _build_context_md(self, session_id: str) -> str:
        """Build a markdown summary from the argument tree (fail-soft)."""
        try:
            from pathlib import Path  # noqa: PLC0415

            from ai_research_engineer.core.argument_tree import _DEFAULT_DB, TreeBuilder  # noqa: PLC0415

            db_path = Path(self._working_dir) / ".data" / "pipeline.db" if self._working_dir else _DEFAULT_DB
            tree = TreeBuilder(run_id=session_id, db_path=db_path)
            try:
                return tree.to_context()
            finally:
                tree.close()
        except Exception as exc:
            logger.debug("[HITL] Context build failed: %s", exc)
            return ""

    @override
    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError(f"{self.__class__.__name__} does not support live mode.")
        yield  # pragma: no cover

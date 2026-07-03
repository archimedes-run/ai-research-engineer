"""
Custom stage orchestrator agent for AI Research Engineer.

This module provides a custom orchestrator that feeds high-level stages one at a time
to the implementation loop, checks success criteria after each stage, and adapts
remaining stages through reflection.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr

from ai_research_engineer.agents.adk.event_compression import compress_events_manually


logger = logging.getLogger(__name__)

# Injected into the reflector when the orchestrator detects two consecutive
# no-progress iterations (S0-3).
FORCED_REFLECTION_INSTRUCTION = (
    "You MUST either propose a concrete stage modification/new stage or explicitly "
    "declare the remaining criteria unmeetable with reasons."
)

# Stage status values (S0-2). A stage is only honestly "completed" when its
# implementation loop was actually approved; otherwise it is recorded as
# "completed_unverified" so no downstream phase mistakes it for verified work.
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_UNVERIFIED = "completed_unverified"
_COMPLETED_STATUSES = frozenset({STATUS_COMPLETED, STATUS_COMPLETED_UNVERIFIED})


def derive_stage_status(implementation_outcome: Optional[str]) -> str:
    """Map an implementation-loop outcome to an honest stage status (S0-2)."""
    return STATUS_COMPLETED if implementation_outcome == "approved" else STATUS_COMPLETED_UNVERIFIED


def stage_completed_flag(status: str) -> bool:
    """Derive the legacy ``completed`` bool from the stage status (S0-2).

    Both "completed" and "completed_unverified" mean the stage cycle has
    finished — so the orchestrator's remaining-stage filter and existing
    consumers keep working unchanged. The ``status`` field carries the truth.
    """
    return status in _COMPLETED_STATUSES


def format_criteria_status(criteria: List[Dict], max_length: int = 80) -> str:
    """
    Format criteria list for readable logging.

    Parameters
    ----------
    criteria : List[Dict]
        List of criteria dictionaries with 'index', 'criteria', and 'met' fields
    max_length : int, optional
        Maximum length for criteria text before truncation (default: 80)

    Returns
    -------
    str
        Formatted multi-line string showing each criterion with status
    """
    if not criteria:
        return "  (No criteria defined)"

    lines = []
    for c in criteria:
        status = "✅ MET" if c.get("met", False) else "❌ NOT MET"
        criteria_text = c.get("criteria", "Unknown criterion")

        # Truncate long criteria text
        if len(criteria_text) > max_length:
            criteria_text = criteria_text[:max_length] + "..."

        lines.append(f"  [{status}] Criterion {c.get('index', '?')}: {criteria_text}")

    return "\n".join(lines)


class StageOrchestratorAgent(BaseAgent):
    """
    Custom orchestrator that manages stage-by-stage implementation.

    This agent feeds high-level stages one at a time to the implementation loop,
    then checks success criteria and reflects on remaining stages after each iteration.
    The workflow exits when all success criteria are met.

    Parameters
    ----------
    implementation_loop : BaseAgent
        The agent that implements each stage (coding + review loop)
    criteria_checker : BaseAgent
        Agent that checks which success criteria have been met
    stage_reflector : BaseAgent
        Agent that reflects on and adapts remaining stages
    name : str, optional
        Agent name (default: "stage_orchestrator")
    description : str, optional
        Agent description
    """

    # Use PrivateAttr for agent references since they shouldn't be serialized
    _implementation_loop: Any = PrivateAttr()
    _criteria_checker: Any = PrivateAttr()
    _stage_reflector: Any = PrivateAttr()
    _working_dir: Optional[str] = PrivateAttr(default=None)
    _hitl_enabled: bool = PrivateAttr(default=False)

    def __init__(
        self,
        implementation_loop: BaseAgent,
        criteria_checker: BaseAgent,
        stage_reflector: BaseAgent,
        name: str = "stage_orchestrator",
        description: str = "Orchestrates stage-by-stage implementation with criteria checking",
        working_dir: Optional[str] = None,
        hitl_enabled: bool = False,
    ):
        super().__init__(name=name, description=description)
        self._implementation_loop = implementation_loop
        self._criteria_checker = criteria_checker
        self._stage_reflector = stage_reflector
        # working_dir is used by the S0-3 no-progress guard to hash files under
        # workflow/ and results/; hitl_enabled selects pause vs terminate.
        self._working_dir = working_dir
        self._hitl_enabled = hitl_enabled

    @property
    def implementation_loop(self) -> BaseAgent:
        """Get the implementation loop agent."""
        return self._implementation_loop

    @property
    def criteria_checker(self) -> BaseAgent:
        """Get the criteria checker agent."""
        return self._criteria_checker

    @property
    def stage_reflector(self) -> BaseAgent:
        """Get the stage reflector agent."""
        return self._stage_reflector

    @staticmethod
    def _tree_safe(fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call fn(*args, **kwargs), log and swallow any exception.

        The argument tree is observability only — failures must never affect
        control flow.
        """
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("[StageOrchestrator] Tree write ignored: %s", exc)
            return None

    def _compute_progress_hash(self, criteria: List[Dict], stages: List[Dict]) -> str:
        """sha256 over the criteria met-bitmap, stage status vector, and the
        (path, mtime, size) signature of files under workflow/ and results/ (S0-3).
        """
        parts: List[str] = [
            "criteria:" + "".join("1" if c.get("met", False) else "0" for c in criteria),
            "stages:"
            + ",".join(
                str(s.get("status") or ("completed" if s.get("completed", False) else "pending")) for s in stages
            ),
        ]

        file_sig: List[str] = []
        if self._working_dir:
            base = Path(self._working_dir)
            for sub in ("workflow", "results"):
                d = base / sub
                if not d.exists():
                    continue
                for p in d.rglob("*"):
                    if p.is_file():
                        try:
                            st = p.stat()
                            file_sig.append(f"{p.relative_to(base)}:{st.st_mtime_ns}:{st.st_size}")
                        except OSError:
                            continue
        parts.append("files:" + "|".join(sorted(file_sig)))

        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def _record_progress_hash(self, state: dict, progress_hash: str, iteration: int) -> Event:
        """Append a progress_hash record to state and build its ADK event (S0-3/S0-9)."""
        entries = state.get("_progress_hashes")
        if not isinstance(entries, list):
            entries = []
        entries.append({"hash": progress_hash, "iteration": iteration})
        state["_progress_hashes"] = entries
        return Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"\n\n🔁 progress_hash (iteration {iteration}): {progress_hash[:12]}…\n\n")],
            ),
            turn_complete=False,
        )

    def _record_gate_decision(self, state: dict, outcome: str, reason: str) -> None:
        """Append a structured gate decision to state (shared with S0-1 emission)."""
        decisions = state.get("_gate_decisions")
        if not isinstance(decisions, list):
            decisions = []
        decisions.append({"loop": self.name, "outcome": outcome, "reason": reason})
        state["_gate_decisions"] = decisions

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Main orchestration logic.

        Implements the core control flow:
        1. Check if all criteria are met -> exit if yes
        2. Get next uncompleted stage
        3. Run implementation_loop for that stage
        4. Run criteria_checker to update criteria status
        5. Run stage_reflector to adapt remaining stages
        6. Repeat

        Parameters
        ----------
        ctx : InvocationContext
            The invocation context with session access

        Yields
        ------
        Event
            Events from sub-agents and orchestration status updates
        """
        state = ctx.session.state

        # Initialize/clear stage-specific state keys
        if "current_stage" not in state:
            state["current_stage"] = None
        if "current_stage_index" not in state:
            state["current_stage_index"] = 0
        if "stage_implementations" not in state:
            state["stage_implementations"] = []

        # Get stages and criteria from state
        stages: List[Dict] = state.get("high_level_stages", [])
        criteria: List[Dict] = state.get("high_level_success_criteria", [])

        # Validate stages
        if not stages or len(stages) == 0:
            logger.error("[StageOrchestrator] No stages found in state!")
            error_event = Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="\n\n[ERROR] No high-level stages found in state. "
                            "Cannot proceed with orchestration.\n\n"
                        )
                    ],
                ),
                turn_complete=True,
            )
            yield error_event
            return

        # Validate stages structure (check first few stages)
        stages_to_check = min(3, len(stages))
        for i in range(stages_to_check):
            stage = stages[i]
            if not isinstance(stage, dict) or "index" not in stage or "title" not in stage:
                logger.error(f"[StageOrchestrator] Stages have invalid structure at index {i}!")
                error_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n[ERROR] High-level stages have invalid structure. "
                                f"Stage at index {i} is missing required fields.\n\n"
                            )
                        ],
                    ),
                    turn_complete=True,
                )
                yield error_event
                return

        # Validate criteria
        if not criteria or len(criteria) == 0:
            logger.error("[StageOrchestrator] No success criteria found in state!")
            error_event = Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="\n\n[ERROR] No success criteria found in state. "
                            "Cannot proceed with orchestration.\n\n"
                        )
                    ],
                ),
                turn_complete=True,
            )
            yield error_event
            return

        # Validate criteria structure (check first few criteria)
        criteria_to_check = min(3, len(criteria))
        for i in range(criteria_to_check):
            criterion = criteria[i]
            if not isinstance(criterion, dict) or "index" not in criterion or "criteria" not in criterion:
                logger.error(f"[StageOrchestrator] Criteria have invalid structure at index {i}!")
                error_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n[ERROR] Success criteria have invalid structure. "
                                f"Criterion at index {i} is missing required fields.\n\n"
                            )
                        ],
                    ),
                    turn_complete=True,
                )
                yield error_event
                return

        logger.info(f"[StageOrchestrator] Starting orchestration with {len(stages)} stages")
        logger.info(f"[StageOrchestrator] Success criteria count: {len(criteria)}")

        # Log all success criteria at the start for visibility
        logger.info("[StageOrchestrator] Success Criteria (End-State Goals):")
        logger.info(format_criteria_status(criteria))
        logger.info(
            "[StageOrchestrator] Note: These are end-state goals that will be progressively "
            "met as stages complete. Early 'NOT MET' status is expected and normal."
        )

        # Initialize stage_implementations if not exists
        if "stage_implementations" not in state:
            state["stage_implementations"] = []

        # --- Argument tree: initialise (failure-isolated) ---
        _tree: Optional[Any] = None
        try:
            from ai_research_engineer.core.argument_tree import TreeBuilder

            _tree = TreeBuilder(ctx.session.id)
        except Exception as _te:
            logger.warning("[StageOrchestrator] Could not init TreeBuilder: %s", _te)

        # Seed tree root + experiment/claim nodes once per run
        if _tree is not None and not state.get("_tree_seeded"):
            topic = (
                state.get("original_user_input")
                or state.get("latest_user_input")
                or state.get("implementation_task")
                or "Research run"
            )

            def _seed_tree() -> None:
                root = _tree.get_root()
                if root is None:
                    root_id = _tree.add_root(label=topic[:200], content=topic)
                else:
                    root_id = root["node_id"]
                # One experiment node per stage
                existing_experiments = {n["metadata"].get("stage_index") for n in _tree.get_nodes_by_type("experiment")}
                for stage in stages:
                    if stage.get("index") not in existing_experiments:
                        _tree.add_experiment(
                            label=stage.get("title", f"Stage {stage.get('index')}"),
                            content=stage.get("description", ""),
                            parent_id=root_id,
                            status="pending",
                            metadata={"stage_index": stage.get("index"), "title": stage.get("title", "")},
                        )
                # One claim node per criterion
                existing_claims = {n["metadata"].get("criterion_index") for n in _tree.get_nodes_by_type("claim")}
                for c in criteria:
                    if c.get("index") not in existing_claims:
                        _tree.add_claim(
                            label=c.get("criteria", f"Criterion {c.get('index')}"),
                            parent_id=root_id,
                            status="unsupported",
                            metadata={"criterion_index": c.get("index")},
                        )

            self._tree_safe(_seed_tree)
            state["_tree_seeded"] = True

        # Main orchestration loop
        iteration = 0
        max_iterations = 50  # Safety limit to prevent infinite loops

        # S0-3 no-progress guard state (tracked across iterations).
        last_progress_hash: Optional[str] = None
        identical_run = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"[StageOrchestrator] === Orchestration iteration {iteration} ===")

            # Refresh state objects (they may have been modified by callbacks)
            stages = state.get("high_level_stages", [])
            criteria = state.get("high_level_success_criteria", [])

            # Check exit condition: all criteria met?
            criteria_met_count = sum(1 for c in criteria if c.get("met", False))
            logger.info(f"[StageOrchestrator] Criteria status: {criteria_met_count}/{len(criteria)} met")

            if all(c.get("met", False) for c in criteria):
                logger.info("[StageOrchestrator] 🎉 All success criteria met! Exiting to summary.")

                # Create completion event
                completion_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n✅ All {len(criteria)} high-level success criteria have been met. "
                                "Proceeding to final summary generation.\n\n"
                            )
                        ],
                    ),
                    turn_complete=True,
                )
                yield completion_event
                if _tree is not None:
                    self._tree_safe(_tree.close)
                return

            # Get next uncompleted stage
            remaining_stages = [s for s in stages if not s.get("completed", False)]

            if not remaining_stages:
                logger.warning(
                    "[StageOrchestrator] No remaining stages but criteria not met. Asking reflector to extend stages."
                )

                # Run reflector to extend stages if needed
                logger.info("[StageOrchestrator] Running stage_reflector to extend plan...")
                async for event in self.stage_reflector.run_async(ctx):
                    yield event

                # Refresh stages from state (reflector may have modified them)
                stages = state.get("high_level_stages", [])
                remaining_stages = [s for s in stages if not s.get("completed", False)]

                if not remaining_stages:
                    logger.error(
                        "[StageOrchestrator] Still no stages after reflection. Exiting despite incomplete criteria."
                    )
                    warning_event = Event(
                        author=self.name,
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part(
                                    text="\n\n⚠️ No remaining stages to implement, but not all "
                                    "success criteria are met. Proceeding to summary.\n\n"
                                )
                            ],
                        ),
                        turn_complete=True,
                    )
                    yield warning_event
                    if _tree is not None:
                        self._tree_safe(_tree.close)
                    return

            # Get next stage to implement
            next_stage = remaining_stages[0]
            stage_idx = next_stage["index"]

            logger.info(f"[StageOrchestrator] 📍 Starting stage {stage_idx}: {next_stage['title']}")

            # Create stage start event
            stage_start_event = Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=f"\n\n### Stage {stage_idx + 1}: {next_stage['title']}\n\n"
                            f"{next_stage['description']}\n\n"
                            "Beginning implementation...\n\n"
                        )
                    ],
                ),
                partial=False,
            )
            yield stage_start_event

            # Set current stage in state (for implementation loop to read)
            state["current_stage"] = {
                "index": next_stage["index"],
                "title": next_stage["title"],
                "description": next_stage["description"],
            }

            # Clear previous implementation outputs
            state.pop("implementation_summary", None)
            state.pop("review_feedback", None)

            # === Run Implementation Loop ===
            logger.info("")
            logger.info("")
            logger.info("")
            logger.info(f"[StageOrchestrator] Running implementation_loop for stage {stage_idx}")

            try:
                async for event in self.implementation_loop.run_async(ctx):
                    yield event

                logger.info(f"[StageOrchestrator] Completed implementation_loop for stage {stage_idx}")

                # === Manual Event Compression After Implementation Loop ===
                logger.info("[StageOrchestrator] Running manual event compression after implementation loop")
                try:
                    await compress_events_manually(
                        ctx=ctx,
                        event_threshold=40,
                        overlap_size=20,
                    )
                except Exception as compress_err:
                    logger.warning(f"[StageOrchestrator] Manual compression failed: {compress_err}")

            except Exception as e:
                logger.error(
                    f"[StageOrchestrator] Implementation loop failed for stage {stage_idx}: {e}",
                    exc_info=True,
                )
                error_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n❌ Implementation loop failed for stage {stage_idx} "
                                f"({next_stage['title']}): {str(e)}\n\n"
                                "Skipping to next stage...\n\n"
                            )
                        ],
                    ),
                    turn_complete=True,
                )
                yield error_event
                # Skip this stage and continue to next
                continue

            # Store implementation result (but don't mark as completed yet)
            next_stage["implementation_result"] = state.get("implementation_summary", "")

            # Add to completed stages history BEFORE running checker/reflector
            # so they can see the current stage in their prompts
            stage_implementations = state.get("stage_implementations", [])
            stage_implementations.append(
                {
                    "stage_index": next_stage["index"],
                    "stage_title": next_stage["title"],
                    "implementation_summary": next_stage["implementation_result"],
                }
            )
            state["stage_implementations"] = stage_implementations

            # --- Tree: record result under this stage's experiment node ---
            if _tree is not None:
                impl_summary = next_stage.get("implementation_result", "")

                def _add_result(stage_idx=stage_idx, summary=impl_summary) -> None:
                    exp_nodes = [
                        n
                        for n in _tree.get_nodes_by_type("experiment")
                        if n["metadata"].get("stage_index") == stage_idx
                    ]
                    if exp_nodes:
                        exp_node_id = exp_nodes[0]["node_id"]
                        _tree.add_result(
                            label=f"Result: stage {stage_idx}",
                            content=summary[:2000] if summary else None,
                            parent_id=exp_node_id,
                            status="completed",
                            metadata={"stage_index": stage_idx},
                        )

                self._tree_safe(_add_result)

            # === Run Success Criteria Checker ===
            logger.info("")
            logger.info("")
            logger.info("")
            logger.info(f"[StageOrchestrator] Running criteria_checker after stage {stage_idx}")

            try:
                async for event in self.criteria_checker.run_async(ctx):
                    yield event

                # Criteria checker updates state["high_level_success_criteria"] via callback
                criteria = state.get("high_level_success_criteria", [])

                criteria_met_count = sum(1 for c in criteria if c.get("met", False))
                logger.info(
                    f"[StageOrchestrator] Criteria status after check: {criteria_met_count}/{len(criteria)} met"
                )

                # --- Tree: flip claim statuses ---
                if _tree is not None:

                    def _update_claims(criteria_snapshot=list(criteria)) -> None:
                        claim_nodes = _tree.get_nodes_by_type("claim")
                        idx_to_node = {n["metadata"].get("criterion_index"): n for n in claim_nodes}
                        for c in criteria_snapshot:
                            node = idx_to_node.get(c.get("index"))
                            if node:
                                new_status = "supported" if c.get("met", False) else node["status"]
                                if new_status != node["status"]:
                                    _tree.update_node_status(node["node_id"], new_status)

                    self._tree_safe(_update_claims)

            except Exception as e:
                logger.error(
                    f"[StageOrchestrator] Criteria checker failed for stage {stage_idx}: {e}",
                    exc_info=True,
                )
                # Log error but continue - criteria check is not mandatory for workflow
                error_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n⚠️ Criteria checker failed for stage {stage_idx}: {str(e)}\n"
                                "Continuing without criteria update...\n\n"
                            )
                        ],
                    ),
                    turn_complete=False,
                )
                yield error_event

            # === Run Stage Reflector ===
            logger.info("")
            logger.info("")
            logger.info("")
            logger.info(f"[StageOrchestrator] Running stage_reflector after stage {stage_idx}")

            try:
                async for event in self.stage_reflector.run_async(ctx):
                    yield event

                # Reflector may modify state["high_level_stages"] via callback
                stages = state.get("high_level_stages", [])

                # --- Tree: add experiment nodes for any new stages ---
                if _tree is not None:

                    def _sync_new_stages(stages_snapshot=list(stages)) -> None:
                        existing = {n["metadata"].get("stage_index") for n in _tree.get_nodes_by_type("experiment")}
                        root = _tree.get_root()
                        root_id = root["node_id"] if root else None
                        for s in stages_snapshot:
                            if s.get("index") not in existing:
                                _tree.add_experiment(
                                    label=s.get("title", f"Stage {s.get('index')}"),
                                    content=s.get("description", ""),
                                    parent_id=root_id,
                                    status="pending",
                                    metadata={"stage_index": s.get("index"), "title": s.get("title", "")},
                                )

                    self._tree_safe(_sync_new_stages)

            except Exception as e:
                logger.error(
                    f"[StageOrchestrator] Stage reflector failed for stage {stage_idx}: {e}",
                    exc_info=True,
                )
                # Log error but continue - reflection is not mandatory for workflow
                error_event = Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"\n\n⚠️ Stage reflector failed for stage {stage_idx}: {str(e)}\n"
                                "Continuing without stage modifications...\n\n"
                            )
                        ],
                    ),
                    turn_complete=False,
                )
                yield error_event
                # Refresh stages anyway
                stages = state.get("high_level_stages", [])

            # NOW record the stage's honest status (S0-2), after criteria check
            # and reflection. The stage is "completed" only if its implementation
            # loop was actually approved; otherwise "completed_unverified". The
            # legacy `completed` bool is derived so downstream consumers and the
            # remaining-stage filter keep working unchanged.
            impl_outcome = state.get("implementation_loop_outcome")
            stage_status = derive_stage_status(impl_outcome)
            next_stage["status"] = stage_status
            next_stage["completed"] = stage_completed_flag(stage_status)
            if stage_status == STATUS_COMPLETED_UNVERIFIED:
                logger.warning(
                    "[StageOrchestrator] Stage %s recorded as '%s' (implementation_loop_outcome=%r)",
                    stage_idx,
                    stage_status,
                    impl_outcome,
                )

            # --- Tree: mark experiment node completed ---
            if _tree is not None:

                def _mark_exp_completed(s_idx=stage_idx) -> None:
                    exp_nodes = [
                        n for n in _tree.get_nodes_by_type("experiment") if n["metadata"].get("stage_index") == s_idx
                    ]
                    if exp_nodes:
                        _tree.update_node_status(
                            exp_nodes[0]["node_id"],
                            "completed",
                            metadata_patch={"completed": True},
                        )

                self._tree_safe(_mark_exp_completed)

            # Update stages in state
            state["high_level_stages"] = stages

            logger.info(f"[StageOrchestrator] Stage {stage_idx} cycle complete. Continuing to next iteration.")

            # Update current_stage_index for tracking (keep 0-indexed for consistency)
            state["current_stage_index"] = stage_idx

            # === S0-3: No-progress guard ===
            # After a full stage cycle, hash the observable state. Two identical
            # hashes in a row -> force the reflector to act; three -> terminate.
            criteria_now = state.get("high_level_success_criteria", [])
            stages_now = state.get("high_level_stages", [])
            progress_hash = self._compute_progress_hash(criteria_now, stages_now)
            yield self._record_progress_hash(state, progress_hash, iteration)

            if progress_hash == last_progress_hash:
                identical_run += 1
            else:
                identical_run = 1
                last_progress_hash = progress_hash

            if identical_run >= 3:
                reason = (
                    f"No observable progress for {identical_run} consecutive iterations "
                    f"(progress_hash={progress_hash[:12]}…)."
                )
                logger.error("[StageOrchestrator] %s Terminating orchestration.", reason)
                self._record_gate_decision(state, "no_progress_terminated", reason)
                if self._hitl_enabled:
                    # Supervised: pause for a human instead of a hard terminate.
                    state["_hitl_paused"] = "gate_no_progress"
                    state["_hitl_question"] = (
                        "The stage orchestrator made no progress for three consecutive "
                        "iterations. Review the partial results and advise, or approve stopping."
                    )
                yield Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=(
                                    f"\n\n🛑 **No-progress termination** — {reason} "
                                    "Proceeding to summary with partial results.\n\n"
                                )
                            )
                        ],
                    ),
                    turn_complete=True,
                )
                if _tree is not None:
                    self._tree_safe(_tree.close)
                return

            if identical_run == 2:
                logger.warning(
                    "[StageOrchestrator] No progress across 2 iterations (progress_hash=%s…); forcing reflection.",
                    progress_hash[:12],
                )
                state["stage_reflector_forced_instruction"] = FORCED_REFLECTION_INSTRUCTION
                self._record_gate_decision(
                    state,
                    "no_progress_forced_reflection",
                    f"No progress across 2 iterations (progress_hash={progress_hash[:12]}…); "
                    "forcing stage_reflector to modify the plan or declare criteria unmeetable.",
                )
                yield Event(
                    author=self.name,
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=(
                                    "\n\n⏳ **No-progress detected (x2)** — re-running the reflector "
                                    "with a forcing instruction to modify the plan or declare the "
                                    "remaining criteria unmeetable.\n\n"
                                )
                            )
                        ],
                    ),
                    turn_complete=False,
                )
                async for event in self.stage_reflector.run_async(ctx):
                    yield event

        # Safety exit if max iterations reached
        logger.error(f"[StageOrchestrator] Reached maximum iterations ({max_iterations}). Exiting orchestration.")
        timeout_event = Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=f"\n\n⚠️ Reached maximum orchestration iterations ({max_iterations}). "
                        "Proceeding to summary with current progress.\n\n"
                    )
                ],
            ),
            turn_complete=True,
        )
        yield timeout_event

        # --- Tree: close connection ---
        if _tree is not None:
            self._tree_safe(_tree.close)

    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Live mode not supported for orchestrator."""
        raise NotImplementedError("Live mode is not supported for StageOrchestratorAgent. Use async mode instead.")

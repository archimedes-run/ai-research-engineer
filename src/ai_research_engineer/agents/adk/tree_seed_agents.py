"""Non-LLM agents that write observability nodes to the argument tree.

IdeationTreeAgent  — writes a hypothesis node after ideation_loop.
PlanningTreeAgent  — writes experiment + claim nodes after high_level_plan_parser.

Both agents are fail-soft: any tree error is logged and swallowed. Removing
these agents from the workflow leaves ideation/planning behaviour and emitted
events byte-identical.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator, Optional

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr
from typing_extensions import override


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared fail-soft wrapper (module-level so both agents can reuse)
# ---------------------------------------------------------------------------


def _tree_safe(fn, agent_name: str) -> None:
    try:
        fn()
    except Exception as exc:
        logger.warning("[%s] Tree write failed (non-blocking): %s", agent_name, exc)


# ---------------------------------------------------------------------------
# IdeationTreeAgent
# ---------------------------------------------------------------------------


class IdeationTreeAgent(BaseAgent):
    """Records the generated idea/hypothesis in the argument tree.

    Reads ``state["generated_ideas"]`` (set by idea_generator_agent) and
    writes a single ``hypothesis`` node under the tree root. Creates the root
    if it does not yet exist. Idempotent: skips if a hypothesis already exists
    for this run (guards against loop retries seeding duplicates).
    """

    _working_dir: str = PrivateAttr(default="")

    def __init__(self, working_dir: str = "", **kwargs) -> None:
        kwargs.setdefault("name", "ideation_tree_agent")
        kwargs.setdefault("description", "Records the generated hypothesis in the argument tree.")
        super().__init__(**kwargs)
        self._working_dir = working_dir

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        from ai_research_engineer.core.argument_tree import _DEFAULT_DB, TreeBuilder  # noqa: PLC0415

        state = ctx.session.state
        session_id = ctx.session.id
        generated_ideas: str = state.get("generated_ideas") or ""
        user_input: str = (state.get("original_user_input") or "Research Study").strip()

        db_path: Optional[Path] = (
            Path(self._working_dir) / ".data" / "pipeline.db" if self._working_dir else _DEFAULT_DB
        )
        hyp_label = generated_ideas[:200].strip() or "Generated hypothesis"

        def _write() -> None:
            tree = TreeBuilder(run_id=session_id, db_path=db_path)
            try:
                root = tree.get_root()
                root_id = root["node_id"] if root else tree.add_root(user_input[:200])
                if not tree.get_nodes_by_type("hypothesis"):
                    tree.add_hypothesis(
                        hyp_label,
                        content=generated_ideas[:4000] or None,
                        parent_id=root_id,
                    )
            finally:
                tree.close()

        _tree_safe(_write, self.name)

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"[IdeationTree] Hypothesis node recorded ({len(generated_ideas)} chars).")],
            ),
            turn_complete=True,
        )

    @override
    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError(f"{self.__class__.__name__} does not support live mode.")
        yield  # pragma: no cover


# ---------------------------------------------------------------------------
# PlanningTreeAgent
# ---------------------------------------------------------------------------


class PlanningTreeAgent(BaseAgent):
    """Records plan stages and criteria as experiment/claim nodes in the tree.

    Runs after ``high_level_plan_parser`` (so ``plan_parser_callback`` has
    already populated ``state["high_level_stages"]`` and
    ``state["high_level_success_criteria"]``).

    Uses the same stage_index / criterion_index de-dup logic as
    StageOrchestratorAgent so that when the orchestrator's seeding block runs
    it finds existing nodes and skips them — no duplicates.
    """

    _working_dir: str = PrivateAttr(default="")

    def __init__(self, working_dir: str = "", **kwargs) -> None:
        kwargs.setdefault("name", "planning_tree_agent")
        kwargs.setdefault("description", "Records plan stages and criteria in the argument tree.")
        super().__init__(**kwargs)
        self._working_dir = working_dir

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        from ai_research_engineer.core.argument_tree import _DEFAULT_DB, TreeBuilder  # noqa: PLC0415

        state = ctx.session.state
        session_id = ctx.session.id
        stages = state.get("high_level_stages") or []
        criteria = state.get("high_level_success_criteria") or []
        user_input: str = (state.get("original_user_input") or "Research Study").strip()

        if not stages and not criteria:
            logger.warning("[PlanningTree] No stages/criteria in state — skipping tree write for run %s", session_id)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="[PlanningTree] No plan data in state — tree write skipped.")],
                ),
                turn_complete=True,
            )
            return

        db_path: Optional[Path] = (
            Path(self._working_dir) / ".data" / "pipeline.db" if self._working_dir else _DEFAULT_DB
        )

        def _write() -> None:
            tree = TreeBuilder(run_id=session_id, db_path=db_path)
            try:
                root = tree.get_root()
                root_id = root["node_id"] if root else tree.add_root(user_input[:200])

                existing_experiments = {
                    n["metadata"].get("stage_index")
                    for n in tree.get_nodes_by_type("experiment")
                }
                for stage in stages:
                    if stage.get("index") not in existing_experiments:
                        tree.add_experiment(
                            label=f"Stage {stage['index']}: {stage.get('title', '')}",
                            parent_id=root_id,
                            status="pending",
                            metadata={"stage_index": stage["index"], "title": stage.get("title", "")},
                        )

                existing_claims = {
                    n["metadata"].get("criterion_index")
                    for n in tree.get_nodes_by_type("claim")
                }
                for c in criteria:
                    if c.get("index") not in existing_claims:
                        tree.add_claim(
                            label=(c.get("criteria") or "")[:200],
                            parent_id=root_id,
                            status="unsupported",
                            metadata={"criterion_index": c["index"]},
                        )
            finally:
                tree.close()

        _tree_safe(_write, self.name)

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(
                    text=f"[PlanningTree] Seeded {len(stages)} experiment(s), {len(criteria)} claim(s).",
                )],
            ),
            turn_complete=True,
        )

    @override
    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError(f"{self.__class__.__name__} does not support live mode.")
        yield  # pragma: no cover

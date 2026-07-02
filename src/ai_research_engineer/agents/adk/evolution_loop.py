"""
Evolutionary loop orchestrator for AI Research Engineer.
This module provides a custom ADK agent that runs the AI Research Engineer mutation loop,
sampling past code nodes, mutating them via Claude, and storing the results.
"""

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr

from ai_research_engineer.evolve.database import Database
from ai_research_engineer.evolve.utils.best_snapshot import BestSnapshotManager
from ai_research_engineer.evolve.utils.structures import Node


logger = logging.getLogger(__name__)

# Single source of truth for the file the evaluator runs and Claude edits.
PROGRAM_FILENAME = "initial_program.py"


class EvolutionLoopAgent(BaseAgent):
    """
    Custom orchestrator that manages the AI Research Engineer Darwinian loop.
    This agent samples the FAISS database for a high-scoring past node,
    feeds it to the Coding Agent for mutation, runs the evaluation,
    and uses the Analyzer Agent to learn from the results.

    Parameters
    ----------
    coding_agent : BaseAgent
        The agent that writes and mutates the code (Claude).
    analyzer_agent : BaseAgent
        Agent that reflects on the mutation's success/failure.
    database : Database
        The AI Research Engineer FAISS database tracking generations.
    best_snapshot : BestSnapshotManager
        Manager that backs up the SOTA generation.
    max_generations : int
        Number of evolution cycles to run.
    name : str
        Agent name.
    description : str
        Agent description.
    """

    # Use PrivateAttr for agent and DB references since they shouldn't be serialized
    _coding_agent: Any = PrivateAttr()
    _analyzer_agent: Any = PrivateAttr()
    _database: Any = PrivateAttr()
    _best_snapshot: Any = PrivateAttr()
    _max_generations: int = PrivateAttr()

    def __init__(
        self,
        coding_agent: BaseAgent,
        analyzer_agent: BaseAgent,
        database: Database,
        best_snapshot: BestSnapshotManager,
        max_generations: int = 10,
        name: str = "evolution_loop",
        description: str = "Runs the autonomous evolutionary optimization loop.",
    ):
        super().__init__(name=name, description=description)
        self._coding_agent = coding_agent
        self._analyzer_agent = analyzer_agent
        self._database = database
        self._best_snapshot = best_snapshot
        self._max_generations = max_generations

    def _read_current_score(self, working_dir: Path) -> float:
        """Helper to extract the empirical score from results.json."""
        results_file = working_dir / "workflow" / "results.json"
        if results_file.exists():
            try:
                data = json.loads(results_file.read_text(encoding="utf-8"))
                return float(data.get("score", data.get("eval_score", 0.0)))
            except Exception as e:
                logger.error(f"[EvolutionLoop] Failed to parse results.json: {e}")
        return 0.0

    def _program_path(self, working_dir: Path) -> Path:
        """Return the canonical path of the evaluator script."""
        return working_dir / "workflow" / PROGRAM_FILENAME

    def _read_current_code(self, working_dir: Path) -> str:
        """Read the evaluator script from the canonical path."""
        path = self._program_path(working_dir)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _materialize_parent(self, parent: Node, working_dir: Path) -> None:
        """Write the parent's code to disk so Claude mutates the correct baseline."""
        target = self._program_path(working_dir)
        target.parent.mkdir(parents=True, exist_ok=True)

        if parent.code:
            target.write_text(parent.code, encoding="utf-8")
            logger.info(f"[EvolutionLoop] Restored parent '{parent.name}' to {target}")
            return

        # Fallback: copy the code file from the most recent best snapshot step dir.
        # BestSnapshotManager stores code at best_dir/<step_name>/code (no extension).
        snapshot_base = self._best_snapshot.best_dir
        if snapshot_base and snapshot_base.exists():
            step_dirs = sorted(snapshot_base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for step_dir in step_dirs:
                snapshot_file = step_dir / "code"
                if snapshot_file.exists():
                    target.write_text(snapshot_file.read_text(encoding="utf-8"), encoding="utf-8")
                    logger.info(f"[EvolutionLoop] Restored parent from snapshot: {snapshot_file}")
                    return

        logger.warning(f"[EvolutionLoop] No code available for parent '{parent.name}'; mutating whatever is on disk.")

    @staticmethod
    def _tree_safe(fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call fn(*args, **kwargs), log and swallow any exception.

        The argument tree is observability only — failures must never affect
        control flow.
        """
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("[EvolutionLoop] Tree write ignored: %s", exc)
            return None

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Main evolutionary logic.
        1. Bootstrap Node 0 if DB is empty.
        2. Sample the DB for the next parent.
        3. Prompt Claude to mutate the parent.
        4. Extract the new score and code.
        5. Run the analyzer to generate insights.
        6. Commit new Node to DB.
        """
        state = ctx.session.state
        working_dir = Path(state.get("working_dir", "./agentic_output"))

        logger.info(f"[EvolutionLoop] Starting evolution for {self._max_generations} generations.")

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=f"\n\n🧬 **INITIALIZING EVOLUTION ENGINE**\nTargeting {self._max_generations} Generations.\n\n"
                    )
                ],
            ),
            turn_complete=True,
        )

        # --- Argument tree: initialise (failure-isolated) ---
        _tree: Optional[Any] = None
        # Maps database node id (int) → argument-tree node id (str UUID)
        db_to_tree: Dict[Any, str] = {}
        try:
            from ai_research_engineer.core.argument_tree import TreeBuilder

            _tree = TreeBuilder(ctx.session.id)
        except Exception as _te:
            logger.warning("[EvolutionLoop] Could not init TreeBuilder: %s", _te)

        # Seed root node once per run (idempotent)
        _tree_root_id: Optional[str] = None
        if _tree is not None and not state.get("_tree_seeded"):
            topic = (
                state.get("original_user_input")
                or state.get("latest_user_input")
                or state.get("implementation_task")
                or "Evolutionary optimisation run"
            )

            def _seed_root() -> Optional[str]:
                existing = _tree.get_root()
                if existing:
                    return existing["node_id"]
                return _tree.add_root(label=topic[:200], content=topic)

            _tree_root_id = self._tree_safe(_seed_root)

        # BOOTSTRAP: If DB is empty, ingest the baseline
        if len(self._database) == 0:
            logger.info("[EvolutionLoop] DB empty. Bootstrapping Node 0 from baseline.")
            baseline_code = self._read_current_code(working_dir)
            baseline_score = self._read_current_score(working_dir)

            node0 = Node(
                name="Generation_0_Baseline",
                motivation="Initial baseline seed program.",
                code=baseline_code,
                score=baseline_score,
                results={"score": baseline_score},
                analysis="Baseline initialized.",
            )
            self._database.add(node0)
            self._best_snapshot.update_if_better(node0, "step_0_baseline", working_dir / "workflow")

            # --- Tree: record baseline experiment + result ---
            if _tree is not None:
                # Resolve root — may have been created above, or we need to fetch it
                def _get_or_create_root() -> Optional[str]:
                    nonlocal _tree_root_id
                    if _tree_root_id:
                        return _tree_root_id
                    existing = _tree.get_root()
                    if existing:
                        _tree_root_id = existing["node_id"]
                        return _tree_root_id
                    topic = state.get("original_user_input") or "Evolutionary optimisation run"
                    _tree_root_id = _tree.add_root(label=topic[:200], content=topic)
                    return _tree_root_id

                def _write_baseline(n0=node0) -> None:
                    root_id = _get_or_create_root()
                    exp_id = _tree.add_experiment(
                        label=n0.name,
                        content=n0.motivation,
                        parent_id=root_id,
                        status="completed",
                        metadata={"gen": 0, "db_node_id": n0.id, "sota": True},
                    )
                    _tree.add_result(
                        label=f"Score: {n0.score}",
                        parent_id=exp_id,
                        status="completed",
                        metadata={"metric_name": "score", "value": n0.score, "gen": 0},
                    )
                    db_to_tree[n0.id] = exp_id

                self._tree_safe(_write_baseline)
            state["_tree_seeded"] = True

        # MAIN EVOLUTIONARY LOOP
        for gen in range(1, self._max_generations + 1):
            logger.info(f"[EvolutionLoop] === Generation {gen} ===")

            # 1. Sample Parent
            parents = self._database.sample(n=1)
            parent = parents[0] if parents else None

            if not parent:
                logger.error("[EvolutionLoop] Failed to sample parent from DB.")
                break

            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=f"\n\n🔄 **GENERATION {gen}**\nSampled Parent: {parent.name} (Score: {parent.score})\nMutating...\n\n"
                        )
                    ],
                ),
                partial=False,
            )

            # 2. Restore parent program to disk so Claude mutates the correct baseline
            self._materialize_parent(parent, working_dir)
            program_path = self._program_path(working_dir)

            # 3. Inject Mutation Prompt to Claude's State
            state["implementation_task"] = (
                f"EVOLUTIONARY OPTIMIZATION TASK - GENERATION {gen}\n\n"
                f"The parent program has been restored to: {program_path}\n"
                f"Edit that file in place to improve its empirical score.\n\n"
                f"Parent score: {parent.score}\n"
                f"Parent Motivation: {parent.motivation}\n"
                f"Parent Analysis: {parent.analysis}\n\n"
                f"Your task:\n"
                f"1. Surgically edit {program_path.name} to improve performance (tune hyperparams, change optimizers, etc.).\n"
                f"2. Run the `eval.sh` script to test your changes.\n"
                f"3. Ensure the new score is written to `results.json`."
            )

            # 5. Run Claude (Mutation)
            try:
                async for event in self._coding_agent.run_async(ctx):
                    yield event
            except Exception as e:
                logger.error(f"[EvolutionLoop] Claude mutation failed on Gen {gen}: {e}")
                continue

            # 6. Extract Results
            new_code = self._read_current_code(working_dir)
            new_score = self._read_current_score(working_dir)

            # 7. Run Analyzer (Stage Reflector acting as Analyzer)
            # We spoof the state so the reflector evaluates the mutation
            state["high_level_stages"] = [{"title": f"Generation {gen}", "description": "Evolutionary mutation step"}]
            state["stage_implementations"] = [
                {"implementation_summary": f"Parent score: {parent.score}, New score: {new_score}"}
            ]

            analyzer_feedback = ""
            try:
                logger.info(f"[EvolutionLoop] Running Analyzer for Gen {gen}")
                async for event in self._analyzer_agent.run_async(ctx):
                    # We stream the analyzer's thoughts too
                    yield event

                # Extract the analyzer's JSON output
                reflector_output = state.get("stage_reflector_output", {})
                analyzer_feedback = json.dumps(reflector_output)
            except Exception as e:
                logger.warning(f"[EvolutionLoop] Analyzer failed on Gen {gen}: {e}")
                analyzer_feedback = f"Analysis failed: {e}"

            # 8. Save new Node
            new_node = Node(
                name=f"Generation_{gen}",
                parent=[parent.id] if parent.id is not None else [],
                motivation=f"Mutated from {parent.name}",
                code=new_code,
                score=new_score,
                results={"score": new_score},
                analysis=analyzer_feedback,
            )

            node_id = self._database.add(new_node)
            is_new_sota = self._best_snapshot.update_if_better(new_node, f"step_{gen}_gen", working_dir / "workflow")

            # --- Tree: record generation experiment + result ---
            if _tree is not None:

                def _write_gen(
                    _gen=gen,
                    _node=new_node,
                    _nid=node_id,
                    _sota=is_new_sota,
                    _parent=parent,
                ) -> None:
                    # Resolve parent tree node; fall back to root if unknown
                    parent_tree_id: Optional[str] = None
                    if _parent is not None and _parent.id is not None:
                        parent_tree_id = db_to_tree.get(_parent.id)
                    if parent_tree_id is None:
                        root = _tree.get_root()
                        parent_tree_id = root["node_id"] if root else None

                    exp_id = _tree.add_experiment(
                        label=_node.name,
                        content=f"Motivation: {_node.motivation}\nAnalysis: {_node.analysis[:500] if _node.analysis else ''}",
                        parent_id=parent_tree_id,
                        status="completed",
                        metadata={"gen": _gen, "db_node_id": _nid, "sota": _sota},
                    )
                    _tree.add_result(
                        label=f"Score: {_node.score}",
                        parent_id=exp_id,
                        status="completed",
                        metadata={"metric_name": "score", "value": _node.score, "gen": _gen},
                    )
                    db_to_tree[_nid] = exp_id

                self._tree_safe(_write_gen)

            sota_text = "🏆 NEW STATE-OF-THE-ART!" if is_new_sota else "📉 Did not beat best."

            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=f"\n\n📊 **Generation {gen} Complete!**\nNew Score: {new_score} {sota_text}\nSaved to DB as Node {node_id}.\n\n"
                        )
                    ],
                ),
                turn_complete=True,
            )

        # Evolution Complete
        best_node = max(self._database.get_all(), key=lambda n: n.score)

        # --- Tree: mark best node's experiment ---
        if _tree is not None:

            def _mark_best(_bn=best_node) -> None:
                if _bn.id is not None:
                    exp_id = db_to_tree.get(_bn.id)
                    if exp_id:
                        _tree.update_node_status(exp_id, "completed", metadata_patch={"best": True})

            self._tree_safe(_mark_best)

        # --- Tree: close connection ---
        if _tree is not None:
            self._tree_safe(_tree.close)

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=f"\n\n🏁 **EVOLUTION COMPLETE**\nBest Architecture found in {best_node.name} with score {best_node.score}!\n\n"
                    )
                ],
            ),
            turn_complete=True,
        )

    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported for EvolutionLoopAgent.")

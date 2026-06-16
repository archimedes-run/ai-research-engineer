"""
Evolutionary loop orchestrator for AI Research Engineer.
This module provides a custom ADK agent that runs the AI Research Engineer mutation loop,
sampling past code nodes, mutating them via Claude, and storing the results.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr

from ai_research_engineer.evolve.database import Database
from ai_research_engineer.evolve.utils.structures import Node
from ai_research_engineer.evolve.utils.best_snapshot import BestSnapshotManager

logger = logging.getLogger(__name__)

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

    def _read_current_code(self, working_dir: Path) -> str:
        """Helper to extract the current evaluator code."""
        code_file = working_dir / "workflow" / "code" # Assuming generic naming, adjust if needed (e.g. train.py)
        if not code_file.exists():
            code_file = working_dir / "workflow" / "initial_program.py"
        
        if code_file.exists():
            return code_file.read_text(encoding="utf-8")
        return ""

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
                parts=[types.Part(text=f"\n\n🧬 **INITIALIZING EVOLUTION ENGINE**\nTargeting {self._max_generations} Generations.\n\n")]
            ),
            turn_complete=True,
        )

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
                analysis="Baseline initialized."
            )
            self._database.add(node0)
            self._best_snapshot.update_if_better(node0, "step_0_baseline", working_dir / "workflow")

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
                    parts=[types.Part(text=f"\n\n🔄 **GENERATION {gen}**\nSampled Parent: {parent.name} (Score: {parent.score})\nMutating...\n\n")]
                ),
                partial=False,
            )

            # 2. Inject Mutation Prompt to Claude's State
            state["implementation_task"] = (
                f"EVOLUTIONARY OPTIMIZATION TASK - GENERATION {gen}\n\n"
                f"You are optimizing the current script to improve its empirical score.\n"
                f"The parent code achieved a score of {parent.score}.\n\n"
                f"Parent Motivation: {parent.motivation}\n"
                f"Parent Analysis: {parent.analysis}\n\n"
                f"Your task:\n"
                f"1. Surgically edit the code to improve performance (tune hyperparams, change optimizers, etc.).\n"
                f"2. Run the `eval.sh` script to test your changes.\n"
                f"3. Ensure the new score is written to `results.json`."
            )

            # 3. Run Claude (Mutation)
            try:
                async for event in self._coding_agent.run_async(ctx):
                    yield event
            except Exception as e:
                logger.error(f"[EvolutionLoop] Claude mutation failed on Gen {gen}: {e}")
                continue

            # 4. Extract Results
            new_code = self._read_current_code(working_dir)
            new_score = self._read_current_score(working_dir)

            # 5. Run Analyzer (Stage Reflector acting as Analyzer)
            # We spoof the state so the reflector evaluates the mutation
            state["high_level_stages"] = [{"title": f"Generation {gen}", "description": "Evolutionary mutation step"}]
            state["stage_implementations"] = [{"implementation_summary": f"Parent score: {parent.score}, New score: {new_score}"}]
            
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

            # 6. Save new Node
            new_node = Node(
                name=f"Generation_{gen}",
                parent=[parent.id] if parent.id is not None else [],
                motivation=f"Mutated from {parent.name}",
                code=new_code,
                score=new_score,
                results={"score": new_score},
                analysis=analyzer_feedback
            )
            
            node_id = self._database.add(new_node)
            is_new_sota = self._best_snapshot.update_if_better(new_node, f"step_{gen}_gen", working_dir / "workflow")

            sota_text = "🏆 NEW STATE-OF-THE-ART!" if is_new_sota else "📉 Did not beat best."

            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"\n\n📊 **Generation {gen} Complete!**\nNew Score: {new_score} {sota_text}\nSaved to DB as Node {node_id}.\n\n")]
                ),
                turn_complete=True,
            )

        # Evolution Complete
        best_node = max(self._database.get_all(), key=lambda n: n.score)
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"\n\n🏁 **EVOLUTION COMPLETE**\nBest Architecture found in {best_node.name} with score {best_node.score}!\n\n")]
            ),
            turn_complete=True,
        )

    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported for EvolutionLoopAgent.")
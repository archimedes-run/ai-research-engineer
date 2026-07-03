"""Unit tests for the intake router (S0-5)."""

import pytest

from ai_research_engineer.core.intake import classify_intent, reconcile_mode


class TestClassifyIntent:
    @pytest.mark.parametrize(
        "prompt",
        [
            "Replicate tabular Q-learning on FrozenLake and reproduce the reported success rate.",
            "Please reproduce the results from the paper.",
            "Re-implement the transformer exactly as described.",
            "Faithfully implement the algorithm from Figure 2.",
        ],
    )
    def test_replicate(self, prompt):
        assert classify_intent(prompt) == "replicate"

    @pytest.mark.parametrize(
        "prompt",
        [
            "Maximize the accuracy on CIFAR-10.",
            "Optimize the Sharpe ratio of the strategy.",
            "Improve the score however you can.",
            "Evolve the architecture to beat the baseline.",
        ],
    )
    def test_optimize(self, prompt):
        assert classify_intent(prompt) == "optimize"

    def test_novel(self):
        assert classify_intent("Invent a novel method for graph pooling.") == "novel"

    def test_ambiguous(self):
        assert classify_intent("Do some machine learning on this dataset.") == "ambiguous"
        assert classify_intent("") == "ambiguous"

    def test_replicate_takes_precedence_over_optimize(self):
        # Contains both "reproduce" and "optimize" -> replicate wins (most specific).
        assert classify_intent("Reproduce the paper, then optimize the score.") == "replicate"

    def test_llm_fallback_flag_defaults_ambiguous(self):
        # No live model wired -> fallback returns None -> ambiguous.
        assert classify_intent("something unclear", use_llm_fallback=True) == "ambiguous"


class TestReconcileMode:
    def test_conflict_autonomous_switches(self):
        # replicate intent under novelty mode, autonomous -> switch to replication.
        assert reconcile_mode("replicate", "novelty", hitl_enabled=False) == ("replication", "switch")

    def test_conflict_hitl_pauses(self):
        assert reconcile_mode("replicate", "novelty", hitl_enabled=True) == ("novelty", "pause")

    def test_no_conflict_proceeds(self):
        assert reconcile_mode("replicate", "replication") == ("replication", "proceed")
        assert reconcile_mode("optimize", "evolve") == ("evolve", "proceed")

    def test_ambiguous_warns_and_keeps_mode(self):
        assert reconcile_mode("ambiguous", "novelty") == ("novelty", "warn")


class TestHITLIntakePauseHalts:
    """In HITL mode an intake mismatch (action=pause) must HALT before the
    workflow is built — never silently proceed on the original mode. The
    pre-workflow resume handshake is deferred to Stage 7 (see STAGE0_BASELINE)."""

    def test_intake_hitl_pause_halts_not_proceeds(self, tmp_path, monkeypatch):
        import asyncio
        from datetime import datetime

        import ai_research_engineer.core.api as api_mod
        import ai_research_engineer.server.app as app_mod
        from ai_research_engineer.server.run_store import RunStore

        RunStore.init(db_path=tmp_path / "t.db")
        monkeypatch.setattr(RunStore, "DATA_DIR", tmp_path)
        RunStore.save_session(
            {
                "session_id": "sess-intake-pause",
                "status": "running",
                "title": "T",
                "topic": "x",
                "agent_type": "adk",
                "started_at": datetime.now().isoformat(),
            }
        )

        built = {"n": 0}

        class _NoBuild:
            def __init__(self, *args, **kwargs):
                built["n"] += 1
                raise AssertionError("workflow must NOT be built after a HITL intake pause")

        monkeypatch.setattr(api_mod, "AIEngineer", _NoBuild)

        queue = asyncio.Queue()
        app_mod._active_sessions["sess-intake-pause"] = queue

        # replicate intent + novelty mode + hitl_enabled=True -> action=pause -> HALT.
        asyncio.run(
            app_mod._run_agent(
                "sess-intake-pause",
                "Replicate tabular Q-learning on FrozenLake and reproduce the reported success rate.",
                "adk",  # agent_type
                "aiml",  # domain
                "novelty",  # research_mode
                "NeurReps_2024_Template",  # template
                False,  # use_graphify
                True,  # hitl_enabled
                queue,
            )
        )

        # The workflow was never constructed.
        assert built["n"] == 0

        events = RunStore.get_events("sess-intake-pause")
        types_ = [e.get("type") for e in events]
        assert "intake_decision" in types_
        assert any(e.get("type") == "message" and "resume not yet supported" in e.get("content", "") for e in events), (
            "a terminal halt message must be emitted"
        )
        # Session halted (terminal), not left running.
        assert RunStore.get_session("sess-intake-pause")["status"] == "failed"

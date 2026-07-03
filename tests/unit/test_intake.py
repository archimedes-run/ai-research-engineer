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

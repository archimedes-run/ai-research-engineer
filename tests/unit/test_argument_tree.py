"""Unit tests for the argument tree (core/argument_tree.py)."""

import pytest

from ai_research_engineer.core.argument_tree import VALID_NODE_TYPES, TreeBuilder


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def tree(tmp_path):
    db = tmp_path / "tree_test.db"
    t = TreeBuilder(run_id="run-1", db_path=db)
    yield t
    t.close()


# ---------------------------------------------------------------------------
# Basic node creation & retrieval
# ---------------------------------------------------------------------------


def test_add_root_and_get(tree):
    node_id = tree.add_root("My research question", content="Details here")
    root = tree.get_root()
    assert root is not None
    assert root["node_id"] == node_id
    assert root["type"] == "root"
    assert root["label"] == "My research question"
    assert root["status"] == "active"


def test_add_experiment_under_root(tree):
    root_id = tree.add_root("Topic")
    exp_id = tree.add_experiment(
        label="Stage 0: Setup",
        parent_id=root_id,
        status="pending",
        metadata={"stage_index": 0, "title": "Setup"},
    )
    children = tree.get_children(root_id)
    assert len(children) == 1
    assert children[0]["node_id"] == exp_id
    assert children[0]["type"] == "experiment"
    assert children[0]["metadata"]["stage_index"] == 0


def test_add_result_under_experiment(tree):
    root_id = tree.add_root("Topic")
    exp_id = tree.add_experiment("Exp", parent_id=root_id)
    res_id = tree.add_result(
        label="Result: stage 0",
        content="accuracy=0.95",
        parent_id=exp_id,
        status="completed",
        metadata={"metric_name": "accuracy", "value": 0.95, "stage_index": 0},
    )
    children = tree.get_children(exp_id)
    assert len(children) == 1
    assert children[0]["node_id"] == res_id
    assert children[0]["metadata"]["metric_name"] == "accuracy"


def test_add_claim_under_root(tree):
    root_id = tree.add_root("Topic")
    claim_id = tree.add_claim(
        label="Model beats baseline",
        parent_id=root_id,
        status="unsupported",
        metadata={"criterion_index": 0},
    )
    claims = tree.get_nodes_by_type("claim")
    assert len(claims) == 1
    assert claims[0]["node_id"] == claim_id
    assert claims[0]["status"] == "unsupported"


def test_all_new_node_types_round_trip(tree):
    root_id = tree.add_root("Root")
    artifact_id = tree.add_artifact("output.csv", parent_id=root_id, metadata={"path": "results/output.csv"})
    hyp_id = tree.add_hypothesis("Hypothesis A", parent_id=root_id)
    assert tree.get_node(artifact_id)["type"] == "artifact"
    assert tree.get_node(hyp_id)["type"] == "hypothesis"
    assert tree.get_node(artifact_id)["metadata"]["path"] == "results/output.csv"


def test_all_seeker_node_types_present():
    seeker_originals = {"root", "claim", "evidence", "question", "objection", "response", "premise", "inference"}
    assert seeker_originals.issubset(VALID_NODE_TYPES)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


def test_get_stats_counts_by_type(tree):
    root_id = tree.add_root("Topic")
    tree.add_experiment("E1", parent_id=root_id)
    tree.add_experiment("E2", parent_id=root_id)
    tree.add_claim("C1", parent_id=root_id)
    stats = tree.get_stats()
    assert stats["total_nodes"] == 4
    assert stats["by_type"]["root"] == 1
    assert stats["by_type"]["experiment"] == 2
    assert stats["by_type"]["claim"] == 1


def test_get_stats_empty_tree(tree):
    stats = tree.get_stats()
    assert stats["total_nodes"] == 0
    assert stats["by_type"] == {}


# ---------------------------------------------------------------------------
# find_gaps
# ---------------------------------------------------------------------------


def test_find_gaps_unanswered_question(tree):
    root_id = tree.add_root("Topic")
    tree.add_question("What is X?", parent_id=root_id)
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "unanswered_question" in kinds


def test_find_gaps_answered_question_not_flagged(tree):
    root_id = tree.add_root("Topic")
    q_id = tree.add_question("What is X?", parent_id=root_id)
    # Add a response as child — question is no longer a leaf
    tree.add_response("Because Y", parent_id=q_id)
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "unanswered_question" not in kinds


def test_find_gaps_unsupported_claim(tree):
    root_id = tree.add_root("Topic")
    tree.add_claim("We outperform baseline", parent_id=root_id, status="unsupported")
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "unsupported_claim" in kinds


def test_find_gaps_supported_claim_not_flagged(tree):
    root_id = tree.add_root("Topic")
    tree.add_claim("We outperform baseline", parent_id=root_id, status="supported")
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "unsupported_claim" not in kinds


def test_find_gaps_experiment_without_result(tree):
    root_id = tree.add_root("Topic")
    tree.add_experiment("Exp with no result", parent_id=root_id)
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "experiment_without_result" in kinds


def test_find_gaps_experiment_with_result_not_flagged(tree):
    root_id = tree.add_root("Topic")
    exp_id = tree.add_experiment("Exp", parent_id=root_id)
    tree.add_result("Result", parent_id=exp_id)
    gaps = tree.find_gaps()
    kinds = [g["kind"] for g in gaps]
    assert "experiment_without_result" not in kinds


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


def test_update_node_status(tree):
    root_id = tree.add_root("Topic")
    claim_id = tree.add_claim("Claim", parent_id=root_id, status="unsupported")
    tree.update_node_status(claim_id, "supported")
    assert tree.get_node(claim_id)["status"] == "supported"


def test_update_node_status_with_metadata_patch(tree):
    root_id = tree.add_root("Topic")
    exp_id = tree.add_experiment("Exp", parent_id=root_id, metadata={"stage_index": 0})
    tree.update_node_status(exp_id, "completed", metadata_patch={"completed": True})
    node = tree.get_node(exp_id)
    assert node["status"] == "completed"
    assert node["metadata"]["completed"] is True
    assert node["metadata"]["stage_index"] == 0  # existing key preserved


# ---------------------------------------------------------------------------
# Run isolation
# ---------------------------------------------------------------------------


def test_separate_runs_are_isolated(tmp_path):
    db = tmp_path / "shared.db"
    t1 = TreeBuilder(run_id="run-A", db_path=db)
    t2 = TreeBuilder(run_id="run-B", db_path=db)
    t1.add_root("Root A")
    t2.add_root("Root B")
    assert t1.get_root()["label"] == "Root A"
    assert t2.get_root()["label"] == "Root B"
    assert t1.get_stats()["total_nodes"] == 1
    assert t2.get_stats()["total_nodes"] == 1
    t1.close()
    t2.close()


# ---------------------------------------------------------------------------
# to_context
# ---------------------------------------------------------------------------


def test_to_context_empty(tree):
    ctx = tree.to_context()
    assert "empty" in ctx.lower()


def test_to_context_non_empty(tree):
    root_id = tree.add_root("Topic")
    tree.add_experiment("Exp", parent_id=root_id)
    ctx = tree.to_context()
    assert "ROOT" in ctx
    assert "EXPERIMENT" in ctx

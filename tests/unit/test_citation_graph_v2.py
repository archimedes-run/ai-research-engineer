"""S1-4: citation graph v2 — multi-seed union, rank-before-truncate, similarity,
persistence + summary above 60 nodes, single-seed backward compat.

All Semantic Scholar (S2) responses are mocked — no network in tests.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np

from ai_research_engineer.tools.research_ops import build_citation_graph


# --------------------------------------------------------------------------- #
# S2 mock helpers
# --------------------------------------------------------------------------- #
def _neighbor(paper_id, title, year, infl):
    """A references[]/citations[] item. Every ranked attribute is set explicitly
    so a MagicMock's auto-attributes never leak into the sort key."""
    n = MagicMock()
    n.paperId = paper_id
    n.title = title
    n.year = year
    n.influentialCitationCount = infl
    return n


def _paper(paper_id, title, year, refs=(), cites=(), infl=0):
    p = MagicMock()
    p.paperId = paper_id
    p.title = title
    p.year = year
    p.influentialCitationCount = infl
    p.references = list(refs)
    p.citations = list(cites)
    return p


def _dispatch(papers: dict):
    """side_effect that returns the mock paper for the requested id."""

    def _get(paper_id, fields=None):
        return papers.get(paper_id)

    return _get


def _run(papers, seed_ids, tmp_path, **kwargs):
    with (
        patch("ai_research_engineer.tools.research_ops.enforce_rate_limit"),
        patch("ai_research_engineer.tools.research_ops.sch") as mock_sch,
    ):
        mock_sch.get_paper.side_effect = _dispatch(papers)
        out = build_citation_graph(seed_ids, str(tmp_path), **kwargs)
    return out


def _saved_graph(tmp_path):
    files = list((tmp_path / "knowledge_base" / "graphs").glob("graph_*.json"))
    assert len(files) == 1, f"expected one persisted graph, found {files}"
    return json.loads(files[0].read_text())


# --------------------------------------------------------------------------- #
# 1. multi-seed union dedupes a shared neighbor
# --------------------------------------------------------------------------- #
def test_multi_seed_union_dedupes_shared_neighbor(tmp_path):
    shared = _neighbor("SHARED", "Shared Ancestor", 2019, infl=10)
    papers = {
        "S1": _paper("S1", "Seed One", 2021, refs=[shared]),
        "S2": _paper("S2", "Seed Two", 2022, refs=[shared]),
    }
    _run(papers, ["S1", "S2"], tmp_path, hops=1)
    graph = _saved_graph(tmp_path)

    ids = [n["id"] for n in graph["nodes"]]
    assert ids.count("SHARED") == 1  # shared neighbor appears exactly once
    assert {"S1", "S2"}.issubset(set(ids))
    # Both seeds point an edge at the one shared node.
    assert {"source": "SHARED", "target": "S1"} in graph["edges"]
    assert {"source": "SHARED", "target": "S2"} in graph["edges"]


# --------------------------------------------------------------------------- #
# 2. ranking by influence x recency happens BEFORE truncation
# --------------------------------------------------------------------------- #
def test_ranking_before_truncation(tmp_path):
    # Arbitrary API order != ranked order. per_node_limit=2 must keep the two
    # highest (influence, then recency), NOT the first two as delivered.
    #   A: infl=1,   year=2025   (front of the list, but lowest influence)
    #   B: infl=100, year=2018
    #   C: infl=100, year=2023   (ties B on influence, wins on recency)
    #   D: infl=5,   year=2024
    # Ranked desc -> [C, B, D, A]; top-2 -> {C, B}.
    refs = [
        _neighbor("A", "A", 2025, infl=1),
        _neighbor("B", "B", 2018, infl=100),
        _neighbor("C", "C", 2023, infl=100),
        _neighbor("D", "D", 2024, infl=5),
    ]
    papers = {"SEED": _paper("SEED", "Seed", 2020, refs=refs)}
    _run(papers, "SEED", tmp_path, hops=1, per_node_limit=2)
    graph = _saved_graph(tmp_path)

    kept = {n["id"] for n in graph["nodes"] if n["group"] == "ancestor"}
    assert kept == {"C", "B"}  # influence filters D/A; recency ranks C over B
    assert "A" not in kept and "D" not in kept  # first-in-list A did NOT survive

    # Proof the ordering actually differs: naive "first per_node_limit" would
    # have kept {A, B}, which is not what a rank-before-truncate build produces.
    assert kept != {"A", "B"}


# --------------------------------------------------------------------------- #
# 3. similarity annotation present iff query_text supplied
# --------------------------------------------------------------------------- #
def test_similarity_annotation_present_with_query_text(tmp_path):
    refs = [_neighbor("A1", "Ancestor", 2019, infl=3)]
    cites = [_neighbor("D1", "Descendant", 2024, infl=7)]
    papers = {"SEED": _paper("SEED", "Seed", 2021, refs=refs, cites=cites)}

    # Deterministic 4-dim embeddings for [query, *titles]; every node gets one.
    def _fake_embed(texts, model_name=None):
        return np.array([[float(i + 1), 0.0, 0.0, 0.0] for i in range(len(texts))], dtype=np.float32)

    with patch("ai_research_engineer.core.embeddings.embed_texts", side_effect=_fake_embed):
        _run(papers, "SEED", tmp_path, hops=1, query_text="attention mechanisms")
    graph = _saved_graph(tmp_path)

    assert all("similarity" in n for n in graph["nodes"])  # every node annotated
    # Collinear vectors -> cosine 1.0 for each node.
    assert all(abs(n["similarity"] - 1.0) < 1e-6 for n in graph["nodes"])


def test_no_similarity_without_query_text(tmp_path):
    papers = {"SEED": _paper("SEED", "Seed", 2021, refs=[_neighbor("A1", "A", 2019, 3)])}
    _run(papers, "SEED", tmp_path, hops=1)
    graph = _saved_graph(tmp_path)
    assert all("similarity" not in n for n in graph["nodes"])


# --------------------------------------------------------------------------- #
# 4. persisted + compact summary (not full JSON) above 60 nodes
# --------------------------------------------------------------------------- #
def test_large_graph_returns_summary_not_full_json(tmp_path):
    refs = [_neighbor(f"R{i}", f"Ref {i}", 2000 + (i % 20), infl=i) for i in range(70)]
    papers = {"SEED": _paper("SEED", "Seed", 2021, refs=refs)}
    out = _run(papers, "SEED", tmp_path, hops=1, per_node_limit=100)

    graph = _saved_graph(tmp_path)
    assert graph["node_count"] > 60  # 1 seed + 70 refs

    # Returned text is a compact summary + path, NOT the full node dump.
    assert "too large to inline" in out
    assert "graph_" in out and ".json" in out
    assert '"group_breakdown"' in out
    # A representative ref title must NOT be inlined in the returned summary...
    assert "Ref 42" not in out
    # ...but it IS present in the persisted full graph on disk.
    assert any(n["label"] == "Ref 42" for n in graph["nodes"])


def test_small_graph_inlines_full_json(tmp_path):
    refs = [_neighbor("A1", "Ancestor One", 2019, infl=3)]
    papers = {"SEED": _paper("SEED", "Seed", 2021, refs=refs)}
    out = _run(papers, "SEED", tmp_path, hops=1)
    assert "Ancestor One" in out  # small graph inlines the full JSON
    assert "too large to inline" not in out


# --------------------------------------------------------------------------- #
# 5. single-seed call still works (backward compatible)
# --------------------------------------------------------------------------- #
def test_single_seed_backward_compatible(tmp_path):
    refs = [_neighbor("A1", "Ancestor", 2019, infl=3)]
    cites = [_neighbor("D1", "Descendant", 2025, infl=9)]
    papers = {"SEED": _paper("SEED", "Root Paper", 2021, refs=refs, cites=cites)}

    out = _run(papers, "SEED", tmp_path, hops=1)  # str seed, not a list
    assert "Root Paper" in out

    graph = _saved_graph(tmp_path)
    groups = {n["id"]: n["group"] for n in graph["nodes"]}
    assert groups["SEED"] == "seed"
    assert groups["A1"] == "ancestor"
    assert groups["D1"] == "descendant"
    assert {"source": "A1", "target": "SEED"} in graph["edges"]  # ancestor -> seed
    assert {"source": "SEED", "target": "D1"} in graph["edges"]  # seed -> descendant


def test_two_hop_expansion_reaches_grandneighbors(tmp_path):
    # Seed -> A1 (ancestor); A1 -> A2 (grand-ancestor). hops=2 must include A2.
    a2 = _neighbor("A2", "Grand Ancestor", 2015, infl=2)
    a1 = _neighbor("A1", "Ancestor", 2019, infl=3)
    papers = {
        "SEED": _paper("SEED", "Seed", 2021, refs=[a1]),
        "A1": _paper("A1", "Ancestor", 2019, refs=[a2]),
    }
    _run(papers, "SEED", tmp_path, hops=2)
    graph = _saved_graph(tmp_path)
    ids = {n["id"] for n in graph["nodes"]}
    assert {"SEED", "A1", "A2"} == ids
    assert {"source": "A2", "target": "A1"} in graph["edges"]

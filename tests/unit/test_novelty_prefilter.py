"""S2-2: embedding prefilter — cosine ranking with recency tiebreak.

Adversarial fixture: input order != similarity order != recency order, and a
genuine cosine tie is broken by recency (same discipline as the S1-4 ranking
test). Embeddings are stubbed so cosines are exact and the tie is real.
"""

import json
from unittest.mock import patch

import numpy as np

from ai_research_engineer.core.novelty import prefilter
from ai_research_engineer.core.novelty.recall import Candidate


def _cand(cid, year):
    return Candidate(id=cid, title=cid, abstract_or_readme=cid, source_channel="test", year=year, url=f"http://{cid}")


# Input order A, B, C, D. Embeddings (idea first) engineered so:
#   A: cos 1.0, year 2018
#   B: cos 1.0, year 2022   -> ties A on cosine; newer -> ranks ABOVE A
#   C: cos ~0.29, year 2025 -> newest, but lowest similarity -> ranks LAST
#   D: cos ~0.90, year 2019
# similarity order -> [B, A, D, C]; input order (A,B,C,D) and recency order
# (C,B,D,A) both differ.
_VECS = np.array([
    [1.0, 0.0, 0.0, 0.0],   # idea
    [1.0, 0.0, 0.0, 0.0],   # A  cos 1.0
    [1.0, 0.0, 0.0, 0.0],   # B  cos 1.0 (tie with A)
    [0.3, 0.95, 0.0, 0.0],  # C  low cos
    [0.9, 0.44, 0.0, 0.0],  # D  cos ~0.9
], dtype=np.float32)


def _fake_embed(texts, model_name=None):
    return _VECS  # aligned to [idea, A, B, C, D]


IDEA = {"title": "sparse attention", "description": "learned per-head sparsity"}
CANDS = [_cand("A", 2018), _cand("B", 2022), _cand("C", 2025), _cand("D", 2019)]


def test_ranks_by_cosine_then_recency_tiebreak():
    with patch.object(prefilter, "embed_texts", side_effect=_fake_embed):
        ranked = prefilter.top_similar(IDEA, CANDS, k=3)

    ids = [r["id"] for r in ranked]
    # B before A (recency breaks the cosine tie); D third; C excluded at k=3.
    assert ids == ["B", "A", "D"]
    assert ids != ["A", "B", "C"]          # not input order
    assert ids != ["C", "B", "D"]          # not recency order
    # Scores are descending and attached.
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert abs(ranked[0]["score"] - 1.0) < 1e-6
    assert abs(ranked[1]["score"] - 1.0) < 1e-6


def test_prefilter_persists_into_recall_report(tmp_path):
    with patch.object(prefilter, "embed_texts", side_effect=_fake_embed):
        prefilter.top_similar(IDEA, CANDS, k=2, working_dir=str(tmp_path))

    from ai_research_engineer.core.novelty.recall import _idea_id
    path = tmp_path / "knowledge_base" / "novelty" / f"recall_{_idea_id(IDEA)}.json"
    report = json.loads(path.read_text())
    assert len(report["prefilter"]) == 2
    assert report["prefilter"][0]["id"] == "B"  # top-ranked persisted first
    assert "score" in report["prefilter"][0]


def test_empty_candidates_returns_empty():
    with patch.object(prefilter, "embed_texts", side_effect=_fake_embed):
        assert prefilter.top_similar(IDEA, [], k=3) == []

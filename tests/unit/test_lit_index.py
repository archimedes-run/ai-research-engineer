"""S1-5: per-session literature index — round trip, dedupe, persistence,
auto-upsert hook, and the search_session_literature tool.

Embeddings are stubbed with a deterministic hashing vectorizer so the tests are
fast and don't load a real model, while keeping query similarity meaningful.
"""

import hashlib
import re
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ai_research_engineer.core import lit_index
from ai_research_engineer.core.lit_index import LitIndex, get_lit_index, reset_session
from ai_research_engineer.tools.lit_ops import search_session_literature


_DIM = 64


def _fake_embed(texts, model_name=None):
    """Hashing bag-of-words vectorizer: same/overlapping words -> high cosine."""
    if isinstance(texts, str):
        texts = [texts]
    out = []
    for t in texts:
        v = np.zeros(_DIM, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", (t or "").lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % _DIM] += 1.0
        out.append(v)
    return np.array(out, dtype=np.float32)


@pytest.fixture(autouse=True)
def _isolate_session():
    reset_session()
    yield
    reset_session()


@pytest.fixture
def patched_embed():
    with patch.object(lit_index, "embed_texts", side_effect=_fake_embed):
        yield


# --------------------------------------------------------------------------- #
# round trip + dedupe
# --------------------------------------------------------------------------- #
def test_upsert_query_round_trip(tmp_path, patched_embed):
    idx = LitIndex(str(tmp_path))
    added = idx.upsert(
        {"id": "p1", "title": "Attention Is All You Need",
         "abstract": "transformer self attention model", "source": "semantic_scholar",
         "url": "http://x", "year": 2017}
    )
    assert added is True
    hits = idx.query("attention transformer", top_k=5)
    assert [h["id"] for h in hits] == ["p1"]
    assert hits[0]["title"] == "Attention Is All You Need"
    assert "score" in hits[0]


def test_dedupe_by_id_across_sources(tmp_path, patched_embed):
    idx = LitIndex(str(tmp_path))
    assert idx.upsert({"id": "same", "title": "Paper A", "abstract": "alpha",
                       "source": "semantic_scholar"}) is True
    # Same id seen again from a DIFFERENT source is deduped (first write wins).
    assert idx.upsert({"id": "same", "title": "Paper A (dup)", "abstract": "beta",
                       "source": "openalex"}) is False
    assert idx.size == 1
    hits = idx.query("Paper A", top_k=5)
    assert len(hits) == 1
    assert hits[0]["source"] == "semantic_scholar"


def test_ranks_more_relevant_doc_first(tmp_path, patched_embed):
    idx = LitIndex(str(tmp_path))
    idx.upsert({"id": "gnn", "title": "graph neural networks for molecules",
                "abstract": "message passing graphs", "source": "s"})
    idx.upsert({"id": "rl", "title": "deep reinforcement learning for games",
                "abstract": "policy gradient rewards", "source": "s"})
    top = idx.query("graph neural networks", top_k=2)[0]
    assert top["id"] == "gnn"


def test_persists_and_reloads_from_disk(tmp_path, patched_embed):
    LitIndex(str(tmp_path)).upsert(
        {"id": "p1", "title": "graph neural networks", "abstract": "gnn", "source": "s"}
    )
    reloaded = LitIndex(str(tmp_path))  # fresh instance reads faiss + docs.jsonl
    assert reloaded.size == 1
    assert reloaded.query("graph neural", top_k=3)[0]["id"] == "p1"


def test_skips_doc_without_id_or_text(tmp_path, patched_embed):
    idx = LitIndex(str(tmp_path))
    assert idx.upsert({"id": None, "title": "no id"}) is False
    assert idx.upsert({"id": "x", "title": None, "abstract": None}) is False
    assert idx.size == 0


# --------------------------------------------------------------------------- #
# auto-upsert hook fires from a (mocked) semantic search
# --------------------------------------------------------------------------- #
def test_auto_upsert_from_semantic_search_papers(tmp_path, patched_embed):
    from ai_research_engineer.tools import semantic_scholar_ops

    paper = MagicMock()
    paper.paperId = "S2ID"
    paper.title = "Deep Residual Learning for Image Recognition"
    paper.year = 2016
    paper.citationCount = 120000
    paper.authors = []
    paper.abstract = "residual networks resnet skip connections"
    paper.url = "http://example.com/resnet"
    paper.citationStyles = None

    with (
        patch.object(semantic_scholar_ops, "sch") as mock_sch,
        patch.object(semantic_scholar_ops, "_enforce_1_rps_limit"),
    ):
        mock_sch.search_paper.return_value = [paper]
        semantic_scholar_ops.search_papers("resnet", working_dir=str(tmp_path))

    # The hook upserted the result into this working_dir's session index.
    idx = get_lit_index(str(tmp_path))
    assert idx.size == 1
    assert idx.query("residual networks", top_k=3)[0]["id"] == "S2ID"


# --------------------------------------------------------------------------- #
# search_session_literature tool
# --------------------------------------------------------------------------- #
def test_search_session_literature_registered():
    from ai_research_engineer.core.tool_registry import registered_names, requirements

    assert "search_session_literature" in registered_names()
    assert requirements("search_session_literature") == []  # local, no requirements


def test_search_session_literature_returns_results(tmp_path, patched_embed):
    idx = get_lit_index(str(tmp_path))  # creates + activates the session index
    idx.upsert({"id": "p1", "title": "sparse attention transformers",
                "abstract": "efficient attention", "source": "s"})

    out = search_session_literature("attention", top_k=5)
    assert "p1" in out and "sparse attention transformers" in out


def test_search_session_literature_empty_when_no_index():
    reset_session()  # no active index
    assert "No session literature" in search_session_literature("anything")

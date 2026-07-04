"""S2-1: multi-channel prior-work recall. All channels mocked with recorded
fixture payloads — no network.

Embeddings are stubbed (deterministic hashing vectorizer) so LitIndex upserts
are fast and don't load a model.
"""

import hashlib
import json
import re
from unittest.mock import Mock, patch

import numpy as np
import pytest

from ai_research_engineer.core import lit_index
from ai_research_engineer.core.lit_index import get_lit_index, reset_session
from ai_research_engineer.core.novelty import recall
from ai_research_engineer.tools import research_ops, search_ops, semantic_scholar_ops


IDEA = {
    "id": "idea-001",
    "title": "Sparse attention for long-context reasoning",
    "description": "We study whether sparse attention mechanisms can match dense "
    "transformers on long-context reasoning while cutting quadratic memory cost.",
}

# --- recorded channel fixtures (tool output shapes) ------------------------- #
OPENALEX = json.dumps([
    {"title": "Attention Is All You Need", "year": 2017, "abstract": "the transformer uses self attention",
     "doi": "https://doi.org/10.5555/x", "cited_by_count": 95000},
])
# A distinct OpenAlex paper (different title) for the all-channels test, so it
# isn't merged into the S2 "Attention Is All You Need" entry by title-dedupe.
OPENALEX_DISTINCT = json.dumps([
    {"title": "Efficient Transformers: A Survey", "year": 2022, "abstract": "survey of efficient attention",
     "doi": "https://doi.org/10.5555/eff", "cited_by_count": 1200},
])
S2 = json.dumps([
    {"paperId": "S2AIAYN", "title": "Attention is all you need", "year": 2017,
     "abstract": "attention based sequence model", "url": "https://s2/aiayn", "citations": 95000, "authors": []},
])
ARXIV = json.dumps([
    {"arxiv_id": "2004.05150", "title": "Longformer: The Long-Document Transformer",
     "published": "2020-04-10", "authors": [], "categories": ["cs.CL"], "summary": "sparse attention for long docs"},
])
GITHUB = json.dumps([
    {"full_name": "google-research/bert", "url": "https://github.com/google-research/bert",
     "stars": 37000, "description": "TensorFlow code for BERT"},
])
PWC = json.dumps([
    {"title": "BERT (Papers with Code)", "url": "https://paperswithcode.com/paper/bert",
     "published": "2018", "repo_url": "https://github.com/google-research/bert", "repo_stars": 37000, "framework": "tf"},
])
README_HEAD = "# BERT\nPretraining of deep bidirectional transformers for language understanding."


def _fake_embed(texts, model_name=None):
    if isinstance(texts, str):
        texts = [texts]
    dim = 64
    out = []
    for t in texts:
        v = np.zeros(dim, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", (t or "").lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim] += 1.0
        out.append(v)
    return np.array(out, dtype=np.float32)


@pytest.fixture(autouse=True)
def _isolate():
    reset_session()
    yield
    reset_session()


@pytest.fixture
def patched_env():
    """Stub embeddings, README fetch, and the citation-graph step (network)."""
    with (
        patch.object(lit_index, "embed_texts", side_effect=_fake_embed),
        patch.object(recall, "_fetch_readme_head", return_value=README_HEAD),
        patch.object(research_ops, "build_citation_graph", return_value=""),
    ):
        yield


def _patch_all_channels(pwc=PWC):
    """Patch every channel tool to return recorded fixtures."""
    return [
        patch.object(semantic_scholar_ops, "search_papers", return_value=S2),
        patch.object(research_ops, "search_papers", return_value=ARXIV),
        patch.object(search_ops, "openalex_search", return_value=OPENALEX_DISTINCT),
        patch.object(search_ops, "github_search", return_value=GITHUB),
        patch.object(search_ops, "paperswithcode_search", return_value=pwc),
    ]


# --------------------------------------------------------------------------- #
# Query generation fallback
# --------------------------------------------------------------------------- #
def test_query_fallback_produces_4_to_6_distinct():
    qs = recall.generate_queries(IDEA)  # no model_call -> deterministic fallback
    assert 4 <= len(qs) <= 6
    assert len(set(q.lower() for q in qs)) == len(qs)  # all distinct


# --------------------------------------------------------------------------- #
# All channels flow into candidates + report + LitIndex
# --------------------------------------------------------------------------- #
def test_all_channels_recorded_and_persisted(tmp_path, patched_env):
    with patch.object(recall, "_pwc_alive", return_value=True):
        for p in _patch_all_channels():
            p.start()
        try:
            cands = recall.recall_prior_work(IDEA, str(tmp_path))
        finally:
            patch.stopall()

    channels = {c.source_channel for c in cands}
    assert {"semantic_scholar", "arxiv", "openalex", "github", "paperswithcode"} <= channels

    # Report persisted with per-channel counts + channel_status.
    report = json.loads((tmp_path / "knowledge_base" / "novelty" / "recall_idea-001.json").read_text())
    assert report["per_channel_counts"]["arxiv"] == 1
    assert report["channel_status"]["paperswithcode"] == "ok"
    assert report["candidate_count"] == len(cands)

    # Candidates upserted into the session LitIndex.
    assert get_lit_index(str(tmp_path)).size == len(cands)


# --------------------------------------------------------------------------- #
# Union dedupe: same paper from S2 and OpenAlex -> one candidate
# --------------------------------------------------------------------------- #
def test_union_dedupes_s2_and_openalex(tmp_path, patched_env):
    with (
        patch.object(recall, "_pwc_alive", return_value=False),
        patch.object(semantic_scholar_ops, "search_papers", return_value=S2),
        patch.object(search_ops, "openalex_search", return_value=OPENALEX),
        patch.object(research_ops, "search_papers", return_value="[]"),
        patch.object(search_ops, "github_search", return_value="[]"),
    ):
        cands = recall.recall_prior_work(IDEA, str(tmp_path))

    aiayn = [c for c in cands if "attention" in c.title.lower() and "need" in c.title.lower()]
    assert len(aiayn) == 1  # "Attention Is All You Need" merged across S2 + OpenAlex

    report = json.loads((tmp_path / "knowledge_base" / "novelty" / "recall_idea-001.json").read_text())
    assert report["per_channel_counts"]["semantic_scholar"] == 1
    assert report["per_channel_counts"]["openalex"] == 1


# --------------------------------------------------------------------------- #
# GitHub candidate carries README-head text and survives dedupe
# --------------------------------------------------------------------------- #
def test_github_candidate_has_readme_and_survives(tmp_path, patched_env):
    with (
        patch.object(recall, "_pwc_alive", return_value=False),
        patch.object(search_ops, "github_search", return_value=GITHUB),
        patch.object(semantic_scholar_ops, "search_papers", return_value="[]"),
        patch.object(research_ops, "search_papers", return_value="[]"),
        patch.object(search_ops, "openalex_search", return_value="[]"),
    ):
        cands = recall.recall_prior_work(IDEA, str(tmp_path))

    gh = [c for c in cands if c.source_channel == "github"]
    assert len(gh) == 1
    assert gh[0].title == "google-research/bert"
    assert "bidirectional transformers" in gh[0].abstract_or_readme  # README head attached
    assert "TensorFlow code for BERT" in gh[0].abstract_or_readme    # description attached


# --------------------------------------------------------------------------- #
# PwC probe: live JSON vs dead HTML/non-JSON
# --------------------------------------------------------------------------- #
def _mock_get(json_data=None, raises_json=False, text=""):
    r = Mock()
    r.status_code = 200
    r.raise_for_status = Mock()
    r.text = text
    if raises_json:
        r.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    else:
        r.json.return_value = json_data
    return r


def test_pwc_probe_live_json_flows_candidates(tmp_path, patched_env):
    # A JSON HTTP response -> probe passes -> PwC contributes candidates.
    pwc_api = {"results": [{"paper": {"title": "BERT", "url_abs": "https://pwc/bert", "published": "2018"},
                            "repository": {"url": "https://github.com/x/bert", "stars": 1, "framework": "tf"}}]}
    with (
        patch.object(search_ops.requests, "get", return_value=_mock_get(json_data=pwc_api)),
        patch.object(semantic_scholar_ops, "search_papers", return_value="[]"),
        patch.object(research_ops, "search_papers", return_value="[]"),
        patch.object(search_ops, "openalex_search", return_value="[]"),
        patch.object(search_ops, "github_search", return_value="[]"),
    ):
        cands = recall.recall_prior_work(IDEA, str(tmp_path))

    report = json.loads((tmp_path / "knowledge_base" / "novelty" / "recall_idea-001.json").read_text())
    assert report["channel_status"]["paperswithcode"] == "ok"
    assert any(c.source_channel == "paperswithcode" for c in cands)


def test_pwc_probe_dead_html_marks_channel_dead(tmp_path, patched_env):
    # A non-JSON (HTML) response -> probe fails -> channel skipped, marked dead,
    # zero candidates, NO exception raised.
    html = _mock_get(raises_json=True, text="<!DOCTYPE html><html>down</html>")
    with (
        patch.object(search_ops.requests, "get", return_value=html),
        patch.object(semantic_scholar_ops, "search_papers", return_value="[]"),
        patch.object(research_ops, "search_papers", return_value="[]"),
        patch.object(search_ops, "openalex_search", return_value="[]"),
        patch.object(search_ops, "github_search", return_value="[]"),
    ):
        cands = recall.recall_prior_work(IDEA, str(tmp_path))  # must not raise

    report = json.loads((tmp_path / "knowledge_base" / "novelty" / "recall_idea-001.json").read_text())
    assert report["channel_status"]["paperswithcode"] == "dead"
    assert report["per_channel_counts"]["paperswithcode"] == 0
    assert not any(c.source_channel == "paperswithcode" for c in cands)

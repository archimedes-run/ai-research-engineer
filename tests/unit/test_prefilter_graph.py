"""S2-2 (live graph): the PrefilterAgent hands the scorer the top-k prefiltered
works — the same top_similar the tested pipeline uses.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ai_research_engineer.agents.adk import review_confirmation as rc
from ai_research_engineer.agents.adk.review_confirmation import create_prefilter_agent


def _fake_embed(texts, model_name=None):
    # idea first, then each candidate; give each a distinct, deterministic vector
    # so cosine ordering is stable (values don't matter, only that ranking runs).
    if isinstance(texts, str):
        texts = [texts]
    out = []
    for i, _t in enumerate(texts):
        v = np.zeros(4, dtype=np.float32)
        v[i % 4] = 1.0
        v[0] += 1.0 / (i + 1)  # everyone has some similarity to the idea
        out.append(v)
    return np.array(out, dtype=np.float32)


def _candidates(n):
    return [{"id": f"C{i}", "title": f"cand {i}", "abstract_or_readme": f"text {i}",
             "source_channel": "openalex", "year": 2000 + i, "url": f"http://c{i}"} for i in range(n)]


class ScorerSpy:
    """Captures the prefiltered_works the scorer would receive."""

    def __init__(self):
        self.captured = None

    async def run_async(self, ctx):
        self.captured = ctx.session.state.get("prefiltered_works")
        return
        yield  # async generator marker


def _drain(agen):
    async def _run():
        return [e async for e in agen]
    return asyncio.run(_run())


def _run_prefilter_then_scorer(candidates, k=None):
    state = {"generated_ideas": "sparse attention for long-context reasoning",
             "recall_candidates": json.dumps(candidates)}
    ctx = SimpleNamespace(session=SimpleNamespace(state=state))
    scorer = ScorerSpy()
    with patch("ai_research_engineer.core.novelty.prefilter.embed_texts", side_effect=_fake_embed):
        _drain(create_prefilter_agent(k=k)._run_async_impl(ctx))
        _drain(scorer.run_async(ctx))
    return scorer, state


# --------------------------------------------------------------------------- #
# 30 recall candidates -> scorer sees exactly 12
# --------------------------------------------------------------------------- #
def test_prefilter_hands_scorer_top_12_of_30():
    scorer, state = _run_prefilter_then_scorer(_candidates(30))  # k defaults to config (12)
    captured = json.loads(scorer.captured)
    assert len(captured) == 12
    # every entry carries a similarity score and a candidate id
    assert all("score" in row and "id" in row for row in captured)


# --------------------------------------------------------------------------- #
# config novelty.prefilter_k = 8 -> scorer sees 8
# --------------------------------------------------------------------------- #
def test_prefilter_k_from_config(monkeypatch):
    monkeypatch.setenv("NOVELTY_PREFILTER_K", "8")  # env override of config
    from ai_research_engineer.core.config import get_prefilter_k
    assert get_prefilter_k() == 8

    scorer, _ = _run_prefilter_then_scorer(_candidates(30))  # k=None -> reads config
    assert len(json.loads(scorer.captured)) == 8


def test_prefilter_handles_no_recall_candidates():
    scorer, state = _run_prefilter_then_scorer([], k=12)
    assert json.loads(scorer.captured) == []


# --------------------------------------------------------------------------- #
# One shared top_similar implementation — exactly two call sites
# --------------------------------------------------------------------------- #
def test_top_similar_called_from_exactly_two_modules():
    src = Path("src/ai_research_engineer")
    prefilter_mod = src / "core" / "novelty" / "prefilter.py"
    callers = []
    for p in src.rglob("*.py"):
        if p == prefilter_mod:
            continue  # the definition site, not a caller
        text = p.read_text(encoding="utf-8", errors="ignore")
        # a real call site imports top_similar AND invokes it
        if "import top_similar" in text and "top_similar(" in text:
            callers.append(p.name)
    assert sorted(callers) == ["pipeline.py", "review_confirmation.py"], callers


def test_review_confirmation_uses_shared_prefilter():
    # The PrefilterAgent calls the shared top_similar (not a private copy).
    assert rc.top_similar is __import__(
        "ai_research_engineer.core.novelty.prefilter", fromlist=["top_similar"]
    ).top_similar

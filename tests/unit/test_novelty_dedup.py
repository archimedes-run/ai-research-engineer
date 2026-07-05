"""S2-5: idea dedup — auto-reject near-duplicates of rejected ideas, no scorer."""

import math
from unittest.mock import MagicMock

from ai_research_engineer.core import config
from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
from ai_research_engineer.core.novelty.pipeline import evaluate_idea


# Unit vectors with a controlled cosine to a reference [1, 0].
def _unit_at_cosine(cos: float):
    return [cos, math.sqrt(max(0.0, 1.0 - cos * cos))]


REJECTED = {"title": "rejected idea", "description": "prior work already did this"}
PROBE = {"title": "probe idea", "description": "candidate to test"}


def _embed_fn(cos_for_probe):
    """Return an embed function: the rejected idea maps to [1,0]; the probe maps
    to a unit vector at the requested cosine from it."""
    ref = [1.0, 0.0]
    probe_vec = _unit_at_cosine(cos_for_probe)

    def embed(text):
        return probe_vec if text.startswith("probe idea") else ref

    return embed


def _table_row():
    return [{"work_id": "W0", "overlap_summary": "s", "differs_because": "d", "overlap_severity": "none"}]


def test_threshold_is_read_from_config():
    assert config.get_dedup_threshold() == 0.92  # default from config/archimedes.yaml


def test_duplicate_above_threshold_autorejects_without_scorer():
    store = RejectedIdeaStore(state={}, embed_fn=_embed_fn(0.93))
    store.record_rejection(REJECTED, "already published (core overlap)")

    score_fn = MagicMock()   # must NOT be called
    falsify_fn = MagicMock()

    result = evaluate_idea(PROBE, [], score_fn=score_fn, falsify_fn=falsify_fn, k=1, store=store)

    assert result["approved"] is False
    assert result["deduped"] is True
    assert result["reason"] == "already published (core overlap)"  # prior reason carried
    assert result["cosine"] > 0.92
    score_fn.assert_not_called()   # ZERO scorer invocations
    falsify_fn.assert_not_called()


def test_below_threshold_proceeds_to_scoring():
    store = RejectedIdeaStore(state={}, embed_fn=_embed_fn(0.90))
    store.record_rejection(REJECTED, "already published")

    # Not a duplicate (0.90 < 0.92) -> the scorer runs. Approve with a clean
    # single-row table, and the falsifier passes clean twice.
    score_fn = MagicMock(return_value={"verdict": "approve", "differentiation_table": _table_row()})
    falsify_fn = MagicMock(return_value={"found": False, "searched": ["q"]})

    result = evaluate_idea(PROBE, [], score_fn=score_fn, falsify_fn=falsify_fn, k=1, store=store)

    score_fn.assert_called()          # proceeded to scoring
    assert result.get("deduped") is not True


def test_threshold_override_argument(monkeypatch):
    store = RejectedIdeaStore(state={}, embed_fn=_embed_fn(0.91))
    store.record_rejection(REJECTED, "prior")
    # 0.91 is below the 0.92 default -> not a duplicate...
    assert store.find_duplicate(PROBE) is None
    # ...but with an explicit lower threshold it is caught.
    assert store.find_duplicate(PROBE, threshold=0.90)["reason"] == "prior"


def test_store_survives_across_rounds_via_state():
    state = {}
    RejectedIdeaStore(state=state, embed_fn=_embed_fn(0.5)).record_rejection(REJECTED, "r1")
    # A fresh wrapper over the same state sees the earlier rejection.
    store2 = RejectedIdeaStore(state=state, embed_fn=_embed_fn(0.93))
    assert store2.find_duplicate(PROBE)["reason"] == "r1"

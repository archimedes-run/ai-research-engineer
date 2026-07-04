"""Idea dedup (S2-5).

Before spending scorer tokens, embed the idea and compare it to the embeddings
of ideas already REJECTED this session. If the cosine exceeds
``novelty.dedup_threshold`` (config), the idea is auto-rejected with the prior
rejection's reason — no scorer call.

The rejected-idea store is a small per-session structure (a plain list of
``{embedding, reason}``) that lives in the run state; ``RejectedIdeaStore``
wraps a state dict so the same store survives across ideation rounds.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

import numpy as np

from ai_research_engineer.core.config import get_dedup_threshold
from ai_research_engineer.core.embeddings import embed_texts


logger = logging.getLogger(__name__)

_STATE_KEY = "_rejected_idea_embeddings"


def idea_text(idea: dict) -> str:
    return f"{(idea.get('title') or '').strip()}\n\n{(idea.get('description') or '').strip()}".strip()


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class RejectedIdeaStore:
    """Per-session store of rejected-idea embeddings + reasons, backed by state."""

    def __init__(self, state: Optional[dict] = None, embed_fn: Optional[Callable] = None):
        self._state = state if state is not None else {}
        self._embed = embed_fn or (lambda t: embed_texts([t])[0])
        if not isinstance(self._state.get(_STATE_KEY), list):
            self._state[_STATE_KEY] = []

    @property
    def _entries(self) -> List[dict]:
        return self._state[_STATE_KEY]

    def _vec(self, idea: dict) -> np.ndarray:
        out = self._embed(idea_text(idea))
        arr = np.asarray(out, dtype=np.float32)
        return arr[0] if arr.ndim == 2 else arr

    def record_rejection(self, idea: dict, reason: str) -> None:
        """Remember a rejected idea so near-duplicates are caught cheaply later."""
        self._entries.append({"embedding": self._vec(idea).tolist(), "reason": reason})

    def find_duplicate(self, idea: dict, threshold: Optional[float] = None) -> Optional[dict]:
        """Return ``{reason, cosine}`` for the closest prior rejection above the
        threshold, or None. Threshold defaults to config ``novelty.dedup_threshold``."""
        thr = get_dedup_threshold() if threshold is None else threshold
        if not self._entries:
            return None
        vec = self._vec(idea)
        best, best_cos = None, -1.0
        for entry in self._entries:
            cos = _cosine(vec, np.asarray(entry["embedding"], dtype=np.float32))
            if cos > best_cos:
                best, best_cos = entry, cos
        if best is not None and best_cos > thr:
            return {"reason": best["reason"], "cosine": round(best_cos, 4)}
        return None

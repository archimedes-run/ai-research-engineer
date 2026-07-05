"""Stage B — embedding prefilter (S2-2).

``top_similar(idea, candidates, k=12)`` ranks recall candidates by cosine
similarity to the idea (``title + description``) using the shared core
embeddings, breaking ties by recency (newer first). The top-k with scores is
returned and, when ``working_dir`` is given, written into the idea's recall
report so the scorer (S2-3), the benchmark (S2-7), and the UI (S2-9) read it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from ai_research_engineer.core.embeddings import embed_texts
from ai_research_engineer.core.novelty.recall import _idea_id


logger = logging.getLogger(__name__)


def _idea_text(idea: dict) -> str:
    return f"{(idea.get('title') or '').strip()}\n\n{(idea.get('description') or '').strip()}".strip()


def _get(cand, field: str):
    return getattr(cand, field, None) if not isinstance(cand, dict) else cand.get(field)


def _cand_text(cand) -> str:
    title = _get(cand, "title") or ""
    body = _get(cand, "abstract_or_readme")
    if body is None:
        body = _get(cand, "abstract") or ""
    return f"{title}\n\n{body}".strip()


def _year_key(cand) -> float:
    """Recency tiebreak value; unknown/garbage years sort oldest."""
    y = _get(cand, "year")
    try:
        return float(str(y)[:4])
    except (TypeError, ValueError):
        return -1.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def top_similar(idea: dict, candidates: list, k: int = 12, working_dir: Optional[str] = None) -> List[dict]:
    """Return the ``k`` candidates most similar to ``idea`` as dicts with a
    ``score`` field, ranked by cosine desc then recency desc."""
    if not candidates:
        if working_dir:
            _persist_prefilter(idea, working_dir, [])
        return []

    vecs = embed_texts([_idea_text(idea)] + [_cand_text(c) for c in candidates])
    idea_vec = np.asarray(vecs[0], dtype=np.float32)

    scored = []
    for i, cand in enumerate(candidates):
        score = _cosine(idea_vec, np.asarray(vecs[i + 1], dtype=np.float32))
        scored.append((score, _year_key(cand), cand))

    # Rank by (cosine desc, recency desc) BEFORE truncation — ties on similarity
    # are broken by the newer paper.
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

    ranked = []
    for score, _yr, cand in scored[:k]:
        ranked.append(
            {
                "id": _get(cand, "id"),
                "title": _get(cand, "title"),
                "abstract": _get(cand, "abstract_or_readme") if not isinstance(cand, dict)
                else (cand.get("abstract_or_readme") or cand.get("abstract")),
                "url": _get(cand, "url"),
                "source": _get(cand, "source_channel") or _get(cand, "source"),
                "year": _get(cand, "year"),
                "score": round(score, 4),
            }
        )

    if working_dir:
        _persist_prefilter(idea, working_dir, ranked)
    return ranked


def _persist_prefilter(idea: dict, working_dir: str, ranked: List[dict]) -> None:
    """Write the prefilter top-k into the idea's recall report (creating a
    minimal report if recall hasn't run)."""
    path = Path(working_dir) / "knowledge_base" / "novelty" / f"recall_{_idea_id(idea)}.json"
    report = {}
    if path.exists():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("[prefilter] recall report unreadable, recreating: %s", exc)
            report = {}
    report["prefilter"] = ranked
    report.setdefault("idea_id", _idea_id(idea))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

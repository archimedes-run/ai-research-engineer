#!/usr/bin/env python3
"""Retrieval recall rubric (S1-8).

Ten (paraphrased query -> known target paper) pairs are run through the
multi-source search union (OpenAlex + Papers with Code + Semantic Scholar). For
each query we check whether the target paper appears in the top-10 of the merged
results, and record which source(s) surfaced it.

Reports overall top-10 recall (target >= 9/10) and per-source recall/attribution.
Results are written to ``benchmarks/knowledge/results/retrieval_recall_<ts>.json``.

Usage:
  uv run python -m benchmarks.knowledge.retrieval_recall
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

from ai_research_engineer.tools import search_ops
from ai_research_engineer.tools.semantic_scholar_ops import search_papers as s2_search


# (paraphrased query, canonical target title). The target match is a normalized
# substring test, so the canonical title must appear (case/punct-insensitive)
# inside the returned title.
PAIRS = [
    ("neural sequence transduction based entirely on attention mechanisms", "attention is all you need"),
    ("deep bidirectional transformer pretraining for language understanding", "bert"),
    ("residual learning framework to train very deep image recognition networks", "deep residual learning for image recognition"),
    ("generative adversarial networks with a generator and a discriminator", "generative adversarial"),
    ("adaptive moment estimation method for stochastic optimization", "adam"),
    ("scaling language models to 175 billion parameters enables few-shot learning", "language models are few-shot learners"),
    ("denoising diffusion probabilistic models for image synthesis", "denoising diffusion probabilistic models"),
    ("pure transformer applied to image patches for image recognition at scale", "an image is worth 16x16 words"),
    ("compound scaling of depth width and resolution for convolutional networks", "efficientnet"),
    ("reducing internal covariate shift with batch normalization", "batch normalization"),
]

_NORM = re.compile(r"[^a-z0-9 ]+")


def _norm(text: str) -> str:
    return _NORM.sub(" ", (text or "").lower()).strip()


def _matches(target: str, title: str) -> bool:
    """A result matches if the canonical target title is a normalized substring
    of the result title (or vice-versa for very short targets)."""
    t, r = _norm(target), _norm(title)
    if not t or not r:
        return False
    if t in r or r in t:
        return True
    # token-set fallback: all target tokens present in the result title.
    ttoks = set(t.split())
    return len(ttoks) >= 2 and ttoks.issubset(set(r.split()))


def _titles_from(json_str: str, key: str = "title") -> list[str]:
    try:
        data = json.loads(json_str)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item.get(key, "")) for item in data if isinstance(item, dict)]


def _source_titles(query: str, limit: int) -> dict[str, list[str]]:
    """Run each source; return {source: [titles]}. Failures -> empty list."""
    out: dict[str, list[str]] = {}
    try:
        out["openalex"] = _titles_from(search_ops.openalex_search(query, limit=limit))
    except Exception:
        out["openalex"] = []
    try:
        out["paperswithcode"] = _titles_from(search_ops.paperswithcode_search(query, limit=limit))
    except Exception:
        out["paperswithcode"] = []
    try:
        out["semantic_scholar"] = _titles_from(s2_search(query, limit=limit))
    except Exception:
        out["semantic_scholar"] = []
    return out


def run(limit: int = 10) -> dict:
    started = time.time()
    sources = ["openalex", "paperswithcode", "semantic_scholar"]
    rows = []
    per_source_hits = {s: 0 for s in sources}
    union_hits = 0

    for query, target in PAIRS:
        titles = _source_titles(query, limit)
        found_by = []
        for s in sources:
            top = titles[s][:limit]
            if any(_matches(target, t) for t in top):
                found_by.append(s)
                per_source_hits[s] += 1
        in_union = bool(found_by)
        union_hits += int(in_union)
        rows.append({"query": query, "target": target, "found": in_union, "found_by": found_by})
        print(f"  {'HIT ' if in_union else 'MISS'} {target[:40]:<40} via {found_by}", flush=True)

    n = len(PAIRS)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_s": round(time.time() - started, 1),
        "n_queries": n,
        "overall_recall_top10": f"{union_hits}/{n}",
        "per_source_recall": {s: f"{per_source_hits[s]}/{n}" for s in sources},
        "rows": rows,
    }


def _print_table(summary: dict) -> None:
    print("\n=== Retrieval Recall (top-10 union) ===")
    print(f"overall recall: {summary['overall_recall_top10']}  (target >=9/10)")
    print("per-source recall/attribution:")
    for s, r in summary["per_source_recall"].items():
        print(f"  {s:<18} {r}")
    print(f"\n{'target':<42}{'found':>7}  sources")
    for row in summary["rows"]:
        print(f"{row['target'][:40]:<42}{str(row['found']):>7}  {row['found_by']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 1 retrieval recall rubric (S1-8)")
    ap.add_argument("--limit", type=int, default=10, help="top-k per source (default 10)")
    args = ap.parse_args()

    summary = run(limit=args.limit)

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"retrieval_recall_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_table(summary)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()

"""Stage A — multi-channel prior-work recall (S2-1).

``recall_prior_work(idea, working_dir)`` casts a wide net for prior work across
several search channels, unions in citation-graph neighbors, dedupes, records
everything into the session literature index, and persists a **recall report**
(``knowledge_base/novelty/recall_<idea_id>.json``) with per-channel counts and a
``channel_status`` map. The report is what the prefilter (S2-2), the benchmark
(S2-7), and the UI (S2-9) read.

Design notes:
- Every channel is wrapped so a dead/rate-limited source degrades gracefully:
  it contributes zero candidates and is marked in ``channel_status`` — never a
  silent zero that looks healthy.
- Papers with Code is probed once at the start (its public API is frequently
  down and returns HTML); if the probe isn't JSON the channel is skipped and
  marked ``"dead"``.
- Query generation uses the agent model when available and falls back to a
  deterministic keyword expansion so tests and offline runs work.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional

import requests

from ai_research_engineer.core import tool_registry
from ai_research_engineer.core.lit_index import record_papers
from ai_research_engineer.tools import research_ops, search_ops, semantic_scholar_ops


logger = logging.getLogger(__name__)

_TIMEOUT = 15
_PWC_PROBE_QUERY = "transformer"
_README_HEAD_CHARS = 800

# Minimal stopword set for the deterministic query fallback.
_STOP = {
    "a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "with", "using",
    "via", "based", "we", "our", "this", "that", "is", "are", "how", "what", "does",
    "do", "from", "by", "as", "at", "its", "into", "over", "about", "can", "be",
    "whether", "which", "such", "than", "more", "less", "when", "while",
}

_NORM = re.compile(r"[^a-z0-9 ]+")


@dataclass
class Candidate:
    id: str
    title: str
    abstract_or_readme: str
    source_channel: str
    year: Optional[object]
    url: Optional[str]

    def as_doc(self) -> dict:
        """Shape expected by the session LitIndex."""
        return {
            "id": self.id,
            "title": self.title,
            "abstract": self.abstract_or_readme,
            "source": self.source_channel,
            "url": self.url,
            "year": self.year,
        }


# --------------------------------------------------------------------------- #
# Query generation
# --------------------------------------------------------------------------- #
def _keywords(text: str) -> List[str]:
    out, seen = [], set()
    for tok in re.findall(r"[a-z0-9][a-z0-9\-]+", (text or "").lower()):
        if len(tok) <= 2 or tok in _STOP or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _dedupe_str(items: List[str]) -> List[str]:
    out, seen = [], set()
    for s in items:
        s = (s or "").strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _fallback_queries(idea: dict) -> List[str]:
    """Deterministic keyword expansion → 4-6 distinct paraphrase-ish queries."""
    title = (idea.get("title") or "").strip()
    desc = (idea.get("description") or "").strip()
    kws = _keywords(f"{title} {desc}")

    cands: List[str] = []
    if title:
        cands.append(title)
    if desc:
        cands.append(desc if len(desc) <= 200 else desc[:200])
    if len(kws) >= 3:
        cands.append(" ".join(kws[:6]))
    if len(kws) >= 4:
        cands.append(" ".join(kws[:3]))
    if len(kws) >= 8:
        cands.append(" ".join(kws[4:9]))
    # Pad toward >=4 distinct for sparse ideas by pairing keywords.
    for i in range(0, max(0, len(kws) - 1), 2):
        if len(cands) >= 6:
            break
        cands.append(f"{kws[i]} {kws[i + 1]}")

    return _dedupe_str(cands)[:6]


def generate_queries(idea: dict, model_call: Optional[Callable[[str], str]] = None) -> List[str]:
    """4-6 varied queries from the idea. Uses ``model_call`` (agent model) when
    given; always falls back to the deterministic expansion."""
    if model_call is not None:
        try:
            raw = model_call(_query_prompt(idea))
            parsed = _dedupe_str([ln.strip("-* \t") for ln in (raw or "").splitlines() if ln.strip()])
            if len(parsed) >= 4:
                return parsed[:6]
        except Exception as exc:  # model failure must never break recall
            logger.debug("[recall] model query-gen failed, using fallback: %s", exc)
    return _fallback_queries(idea)


def _query_prompt(idea: dict) -> str:
    return (
        "Generate 5 diverse search queries (one per line, no numbering) to find "
        "prior work that could overlap with this research idea.\n\n"
        f"Title: {idea.get('title', '')}\nDescription: {idea.get('description', '')}"
    )


# --------------------------------------------------------------------------- #
# Channel helpers
# --------------------------------------------------------------------------- #
def _parse_list(payload: str) -> list:
    try:
        data = json.loads(payload)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _pwc_alive() -> bool:
    """Cheap probe: a live PwC API returns JSON; a dead one returns HTML, which
    ``paperswithcode_search`` reports as a 'search error/failed' string."""
    try:
        probe = search_ops.paperswithcode_search(_PWC_PROBE_QUERY, limit=1)
    except Exception:
        return False
    return not probe.startswith("Papers with Code search ")


def _fetch_readme_head(full_name: str, max_chars: int = _README_HEAD_CHARS) -> str:
    """First ``max_chars`` of a repo's README (main then master). Best-effort."""
    if not full_name:
        return ""
    for branch in ("main", "master"):
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md",
                timeout=_TIMEOUT,
            )
            if r.status_code == 200 and r.text:
                return r.text[:max_chars]
        except Exception:
            continue
    return ""


def _from_openalex(items: list) -> List[Candidate]:
    return [
        Candidate(
            id=str(it.get("doi") or it.get("title") or ""),
            title=it.get("title") or "",
            abstract_or_readme=it.get("abstract") or "",
            source_channel="openalex",
            year=it.get("year"),
            url=it.get("doi"),
        )
        for it in items
        if it.get("title")
    ]


def _from_semantic_scholar(items: list) -> List[Candidate]:
    return [
        Candidate(
            id=str(it.get("paperId") or it.get("title") or ""),
            title=it.get("title") or "",
            abstract_or_readme=it.get("abstract") or "",
            source_channel="semantic_scholar",
            year=it.get("year"),
            url=it.get("url"),
        )
        for it in items
        if it.get("title")
    ]


def _from_arxiv(items: list) -> List[Candidate]:
    out = []
    for it in items:
        if not it.get("title"):
            continue
        aid = it.get("arxiv_id")
        out.append(
            Candidate(
                id=str(aid or it.get("title")),
                title=it.get("title") or "",
                abstract_or_readme=it.get("summary") or "",
                source_channel="arxiv",
                year=(str(it.get("published"))[:4] if it.get("published") else None),
                url=(f"https://arxiv.org/abs/{aid}" if aid else None),
            )
        )
    return out


def _from_github(items: list) -> List[Candidate]:
    out = []
    for it in items:
        full_name = it.get("full_name") or it.get("repo")
        if not full_name:
            continue
        desc = it.get("description") or ""
        readme = _fetch_readme_head(full_name)
        text = "\n\n".join(p for p in (desc, readme) if p).strip()
        out.append(
            Candidate(
                id=str(it.get("url") or full_name),
                title=full_name,
                abstract_or_readme=text,
                source_channel="github",
                year=None,
                url=it.get("url"),
            )
        )
    return out


def _from_pwc(items: list) -> List[Candidate]:
    return [
        Candidate(
            id=str(it.get("url") or it.get("title") or ""),
            title=it.get("title") or "",
            abstract_or_readme="",
            source_channel="paperswithcode",
            year=it.get("published"),
            url=it.get("url"),
        )
        for it in items
        if it.get("title")
    ]


# --------------------------------------------------------------------------- #
# Dedupe
# --------------------------------------------------------------------------- #
def _norm_title(title: str) -> str:
    return _NORM.sub(" ", (title or "").lower()).strip()


def _dedupe_key(c: Candidate):
    # repos dedupe by URL; papers merge across channels by normalized title.
    if c.source_channel == "github" and c.url:
        return ("repo", c.url.lower().rstrip("/"))
    nt = _norm_title(c.title)
    if nt:
        return ("title", nt)
    return ("id", (c.id or "").lower())


def _dedupe(cands: List[Candidate]) -> List[Candidate]:
    """Keep first occurrence per key, but upgrade to the richer text if a later
    duplicate carries a longer abstract/readme."""
    kept: dict = {}
    order: List[object] = []
    for c in cands:
        key = _dedupe_key(c)
        if key not in kept:
            kept[key] = c
            order.append(key)
        elif len(c.abstract_or_readme or "") > len(kept[key].abstract_or_readme or ""):
            existing = kept[key]
            existing.abstract_or_readme = c.abstract_or_readme
    return [kept[k] for k in order]


# --------------------------------------------------------------------------- #
# Citation-graph union
# --------------------------------------------------------------------------- #
def _citation_graph_candidates(seeds: List[str], idea: dict, working_dir: str) -> List[Candidate]:
    if not seeds:
        return []
    try:
        research_ops.build_citation_graph(
            seeds, working_dir, hops=2, query_text=idea.get("description") or idea.get("title") or ""
        )
    except Exception as exc:
        logger.debug("[recall] citation graph failed: %s", exc)
        return []
    graphs_dir = Path(working_dir) / "knowledge_base" / "graphs"
    files = sorted(graphs_dir.glob("graph_*.json"))
    if not files:
        return []
    try:
        data = json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for n in data.get("nodes", []):
        if n.get("group") == "seed" or not n.get("label"):
            continue
        out.append(
            Candidate(
                id=str(n.get("id") or n.get("label")),
                title=n.get("label") or "",
                abstract_or_readme=n.get("label") or "",
                source_channel="citation_graph",
                year=n.get("year"),
                url=None,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _idea_id(idea: dict) -> str:
    if idea.get("id"):
        return str(idea["id"])
    basis = (idea.get("title") or "") + (idea.get("description") or "")
    return "idea_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]


def _registry_ok(name: str) -> bool:
    """A registered channel is usable only if its requirements are met; unknown
    (unregistered) channels are assumed usable and guarded by try/except."""
    if name in tool_registry.registered_names():
        return tool_registry.is_available(name)
    return True


def recall_prior_work(
    idea: dict,
    working_dir: str,
    max_candidates: int = 80,
    model_call: Optional[Callable[[str], str]] = None,
) -> List[Candidate]:
    """Multi-channel prior-work recall for one idea. Returns deduped candidates
    and persists the recall report."""
    queries = generate_queries(idea, model_call=model_call)

    per_channel_counts: dict = {}
    channel_status: dict = {}
    collected: List[Candidate] = []

    # channel_status vocabulary (counts are only meaningful for "live"):
    #   "live"        — channel ran; per_channel_counts is its unique-find count
    #                   (a live channel with 0 results is still "live", count 0),
    #   "unavailable" — registry requirements unmet (network off / key missing);
    #                   channel never attempted,
    #   "dead"        — PwC only: the probe reached the API but got non-JSON,
    #   "error"       — channel was available but raised mid-run.
    def _run(name: str, fn, mapper, enabled: bool = True):
        if not enabled or not _registry_ok(name):
            channel_status[name] = "unavailable"
            per_channel_counts[name] = 0
            return
        got: List[Candidate] = []
        try:
            for q in queries:
                got.extend(mapper(_parse_list(fn(q))))
            channel_status[name] = "live"
        except Exception as exc:
            logger.debug("[recall] channel %s errored: %s", name, exc)
            channel_status[name] = "error"
        # Dedupe within the channel so the count reflects unique finds, not the
        # number of queries that echoed the same paper.
        got = _dedupe(got)
        per_channel_counts[name] = len(got)
        collected.extend(got)

    # Paper channels.
    _run("semantic_scholar", lambda q: semantic_scholar_ops.search_papers(q, working_dir=working_dir),
         _from_semantic_scholar)
    _run("arxiv", lambda q: research_ops.search_papers(q), _from_arxiv)
    _run("openalex", lambda q: search_ops.openalex_search(q), _from_openalex)
    _run("github", lambda q: search_ops.github_search(q, mode="repositories"), _from_github)

    # Papers with Code. Distinguish registry-unavailable from probe-dead: only
    # probe when the registry says the channel is usable, so a network-off run is
    # "unavailable", not mislabeled "dead".
    if not _registry_ok("paperswithcode"):
        channel_status["paperswithcode"] = "unavailable"
        per_channel_counts["paperswithcode"] = 0
    elif _pwc_alive():
        _run("paperswithcode", lambda q: search_ops.paperswithcode_search(q), _from_pwc)
    else:
        channel_status["paperswithcode"] = "dead"
        per_channel_counts["paperswithcode"] = 0

    # Citation-graph union: top-3 candidates so far as seeds.
    seeds = [c.id for c in collected[:3] if c.id]
    graph_cands = _citation_graph_candidates(seeds, idea, working_dir)
    if graph_cands:
        channel_status["citation_graph"] = "live"
        per_channel_counts["citation_graph"] = len(graph_cands)
        collected.extend(graph_cands)

    candidates = _dedupe(collected)[:max_candidates]

    # Feed the session literature index.
    record_papers([c.as_doc() for c in candidates], working_dir=working_dir)

    _persist_report(idea, working_dir, queries, per_channel_counts, channel_status, candidates)
    return candidates


def _persist_report(idea, working_dir, queries, per_channel_counts, channel_status, candidates) -> Path:
    from datetime import datetime

    report = {
        "idea_id": _idea_id(idea),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "queries": queries,
        "per_channel_counts": per_channel_counts,
        "channel_status": channel_status,
        "candidate_count": len(candidates),
        "candidates": [asdict(c) for c in candidates],
    }
    out_dir = Path(working_dir) / "knowledge_base" / "novelty"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"recall_{_idea_id(idea)}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path

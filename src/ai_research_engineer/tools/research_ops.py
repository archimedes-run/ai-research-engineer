"""
Advanced Research operations for the AI Research Engineer.
Combines Semantic Scholar for impact-filtering, findpapers for omni-search,
and ArXiv for full-text ingestion.
Implements rate-limiting, HTML-first downloading, and local paper listing.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import arxiv
import findpapers

from ai_research_engineer.tools.semantic_scholar import client as sch, enforce_rate_limit


logger = logging.getLogger(__name__)

# Unified Semantic Scholar access (S0-8): shared client + shared limiter (also
# used by semantic_scholar_ops). `sch` name is retained for the call sites and
# for tests that patch it.



# Common words dropped when turning a natural-language query into the findpapers DSL.
_FINDPAPERS_STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "with", "using",
    "via", "based", "we", "our", "this", "that", "is", "are", "how", "what",
    "does", "do", "from", "by", "as", "at", "its", "into", "over", "about",
}

# Detected synonyms -> emit an OR group so either term matches.
_FINDPAPERS_SYNONYMS = {
    "optimization": ["optimisation"],
    "rl": ["reinforcement learning"],
    "cnn": ["convolutional neural network"],
    "llm": ["large language model"],
    "nlp": ["natural language processing"],
}


def _to_findpapers_query(query: str) -> str:
    """Convert a natural-language query into a valid findpapers boolean query.

    findpapers requires its own DSL: terms wrapped in ``[ ]`` joined by AND/OR
    (e.g. ``[dropout] AND [regularization]``). We split the query into keywords,
    drop stopwords, and emit ``[kw1] AND [kw2] ...`` — with ``([kw] OR [syn])``
    OR-groups for detected synonyms. A DSL query (already contains ``[``) passes
    through unchanged.
    """
    q = (query or "").strip()
    if "[" in q and "]" in q:
        return q

    tokens = re.findall(r"[A-Za-z0-9\-]+", q.lower())
    keywords = [t for t in tokens if t not in _FINDPAPERS_STOPWORDS]
    if not keywords:
        return "[research]"

    groups = []
    for kw in keywords:
        synonyms = _FINDPAPERS_SYNONYMS.get(kw)
        if synonyms:
            alternatives = " OR ".join(f"[{term}]" for term in [kw, *synonyms])
            groups.append(f"({alternatives})")
        else:
            groups.append(f"[{kw}]")
    return " AND ".join(groups)


def omni_search_papers(query: str, limit: int = 10) -> str:
    """
    Search for research papers across ALL major databases
    (arXiv, PubMed, IEEE, ACM, Scopus) simultaneously using findpapers.
    """
    import tempfile

    from findpapers.utils import persistence_util

    fp_query = _to_findpapers_query(query)
    logger.info(f"[Tool:omni_search] Querying all databases for: '{query}' (findpapers: {fp_query})")
    try:
        # findpapers.search()'s FIRST positional arg is the output path — it writes
        # results to disk and returns None. The query must be passed as a keyword.
        with tempfile.TemporaryDirectory(prefix="omni_search_") as tmp:
            outputpath = os.path.join(tmp, "search.json")
            findpapers.search(outputpath, query=fp_query, limit_per_database=limit)
            search_result = persistence_util.load(outputpath)

        results = []
        for paper in search_result.papers:
            authors = paper.authors or []
            # findpapers authors may be plain strings or objects with `.name`
            author_names = [getattr(a, "name", a) for a in authors]
            results.append({
                "title": paper.title,
                "authors": author_names,
                "year": paper.publication_date.year if paper.publication_date else "Unknown",
                "abstract": paper.abstract[:500] + "..." if paper.abstract else "No abstract",
                "databases": list(paper.databases) if paper.databases else [],
                "urls": list(paper.urls) if paper.urls else [],
            })

        if not results:
            return f"No papers found for query '{query}'. Try semantic_search_papers or arxiv_search_papers instead."
        return json.dumps(results[:limit], indent=2)
    except Exception as e:
        return f"Error in Omni-Search: {e}. Tip: use semantic_search_papers or arxiv_search_papers for keyword queries."


# Semantic Scholar fields needed to rank neighbors by influence and recency.
_GRAPH_FIELDS = [
    "title", "year", "influentialCitationCount",
    "references.title", "references.paperId", "references.year",
    "references.influentialCitationCount",
    "citations.title", "citations.paperId", "citations.year",
    "citations.influentialCitationCount",
]

# Above this many nodes the full JSON is too large to inline for the LLM; we
# return a compact summary + the on-disk path instead.
_GRAPH_INLINE_NODE_LIMIT = 60


def _normalize_seed_id(paper_id: str) -> str:
    """Auto-fix a bare arXiv id (e.g. ``1706.03762``) into Semantic Scholar's
    ``ARXIV:<id>`` form; pass everything else through untouched."""
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", paper_id):
        return f"ARXIV:{paper_id.split('v')[0]}"
    return paper_id


def _neighbor_rank_key(item):
    """Sort key: (influentialCitationCount, recency), each defaulting to 0."""
    infl = getattr(item, "influentialCitationCount", None) or 0
    year = getattr(item, "year", None) or 0
    return (infl, year)


def _rank_neighbors(items: list) -> list:
    """Rank a neighbor list by influence then recency, descending.

    Applied BEFORE truncation to ``per_node_limit`` so the cap keeps the most
    influential and recent neighbors — not an arbitrary API-order prefix.
    """
    return sorted(items, key=_neighbor_rank_key, reverse=True)


def _annotate_similarity(nodes: dict, query_text: str) -> None:
    """Annotate every node with its cosine similarity to ``query_text`` using the
    shared core embeddings (single batched call)."""
    import numpy as np

    from ai_research_engineer.core.embeddings import embed_texts

    ids = list(nodes.keys())
    titles = [nodes[i].get("label") or "" for i in ids]
    vecs = embed_texts([query_text] + titles)
    q = vecs[0]
    q_norm = float(np.linalg.norm(q)) or 1.0
    for offset, node_id in enumerate(ids):
        v = vecs[offset + 1]
        v_norm = float(np.linalg.norm(v)) or 1.0
        nodes[node_id]["similarity"] = round(float(np.dot(q, v)) / (q_norm * v_norm), 4)


def build_citation_graph(
    seed_ids,
    working_dir: str,
    hops: int = 2,
    per_node_limit: int = 25,
    query_text: Optional[str] = None,
) -> str:
    """Citation graph v2 (S1-4): multi-seed, ranked-before-truncation.

    Parameters
    ----------
    seed_ids:
        One paper id (``str``, backward compatible) or a list of ids. Multiple
        seeds are unioned into one graph; a neighbor shared by two seeds appears
        exactly once.
    working_dir:
        Workspace root; the graph is persisted under
        ``knowledge_base/graphs/graph_<timestamp>.json``.
    hops:
        How many expansion rounds outward from the seeds.
    per_node_limit:
        Max neighbors kept per node, applied AFTER ranking each node's neighbors
        by ``(influentialCitationCount, recency)``.
    query_text:
        If given, every node is annotated with its cosine similarity to this text
        via the core embeddings.

    Above 60 nodes a compact summary + the file path is returned instead of the
    full JSON dump.
    """
    seeds = [seed_ids] if isinstance(seed_ids, str) else list(seed_ids)
    seeds = [_normalize_seed_id(s) for s in seeds]
    logger.info(
        f"[Tool:build_citation_graph] Mapping ecosystem for {len(seeds)} seed(s), "
        f"hops={hops}, per_node_limit={per_node_limit}"
    )
    try:
        nodes: dict = {}
        edges: list = []
        edge_set = set()

        def _add_node(pid, label, year, group, infl):
            if pid not in nodes:
                nodes[pid] = {
                    "id": pid,
                    "label": label or "Unknown Title",
                    "year": year,
                    "group": group,
                    "influential_citations": infl or 0,
                }
            elif group == "seed":
                nodes[pid]["group"] = "seed"  # a seed label always wins

        def _add_edge(src, dst):
            key = (src, dst)
            if src != dst and key not in edge_set:
                edge_set.add(key)
                edges.append({"source": src, "target": dst})

        seed_set = set(seeds)
        frontier = list(dict.fromkeys(seeds))  # unique, order-preserving
        visited = set()

        for _hop in range(max(1, hops)):
            next_frontier = []
            for node_id in frontier:
                if node_id in visited:
                    continue
                visited.add(node_id)
                enforce_rate_limit()
                try:
                    p = sch.get_paper(node_id, fields=_GRAPH_FIELDS)
                except Exception as fetch_e:
                    logger.warning(
                        f"[Tool:build_citation_graph] fetch failed for {node_id}: {fetch_e}"
                    )
                    continue
                if not p:
                    continue

                pid = getattr(p, "paperId", None) or node_id
                group = "seed" if node_id in seed_set else nodes.get(pid, {}).get("group", "neighbor")
                _add_node(
                    pid,
                    getattr(p, "title", None),
                    getattr(p, "year", None),
                    group,
                    getattr(p, "influentialCitationCount", None),
                )

                # References (ancestors) and citations (descendants): rank each
                # list, THEN truncate to the per-node budget.
                refs = _rank_neighbors(list(getattr(p, "references", None) or []))[:per_node_limit]
                for ref in refs:
                    rid = getattr(ref, "paperId", None)
                    if not rid:
                        continue
                    _add_node(rid, getattr(ref, "title", None), getattr(ref, "year", None),
                              "ancestor", getattr(ref, "influentialCitationCount", None))
                    _add_edge(rid, pid)  # ancestor -> node
                    if rid not in visited:
                        next_frontier.append(rid)

                cites = _rank_neighbors(list(getattr(p, "citations", None) or []))[:per_node_limit]
                for cite in cites:
                    cid = getattr(cite, "paperId", None)
                    if not cid:
                        continue
                    _add_node(cid, getattr(cite, "title", None), getattr(cite, "year", None),
                              "descendant", getattr(cite, "influentialCitationCount", None))
                    _add_edge(pid, cid)  # node -> descendant
                    if cid not in visited:
                        next_frontier.append(cid)
            frontier = next_frontier

        if query_text:
            _annotate_similarity(nodes, query_text)

        graph_data = {
            "seeds": list(seeds),
            "hops": hops,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes.values()),
            "edges": edges,
        }
        json_str = json.dumps(graph_data, indent=2)

        graph_path = None
        if working_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            graph_path = Path(working_dir) / "knowledge_base" / "graphs" / f"graph_{ts}.json"
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            graph_path.write_text(json_str, encoding="utf-8")

        # Above the inline limit, return a compact summary instead of the dump.
        if len(nodes) > _GRAPH_INLINE_NODE_LIMIT:
            groups: dict = {}
            for n in nodes.values():
                groups[n["group"]] = groups.get(n["group"], 0) + 1
            summary = {
                "seeds": list(seeds),
                "hops": hops,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "group_breakdown": groups,
                "graph_path": str(graph_path) if graph_path else None,
            }
            saved = graph_path.name if graph_path else "N/A"
            return (
                f"Citation graph built: {len(nodes)} nodes, {len(edges)} edges "
                f"(too large to inline). Saved to {saved}.\n\n"
                + json.dumps(summary, indent=2)
            )

        if graph_path:
            return f"Citation graph built and saved to {graph_path.name}:\n\n{json_str}"
        return json_str

    except Exception as e:
        return f"Error building citation graph: {e}"


def discover_high_impact_papers(query: str, limit: int = 5, min_citations: int = 10) -> str:
    """
    Search Semantic Scholar to discover highly cited papers and extract their arXiv IDs.
    """
    logger.info(f"[Tool:discover_high_impact] Query: '{query}'")
    try:
        enforce_rate_limit()
        results = sch.search_paper(
            query, limit=limit * 3, fields=['title', 'authors', 'year', 'citationCount', 'externalIds']
        )
        
        if not results:
            return "No papers found."
            
        papers = []
        for p in results:
            if p.citationCount is not None and p.citationCount >= min_citations:
                arxiv_id = p.externalIds.get('ArXiv') if p.externalIds else None
                if arxiv_id:
                    papers.append({
                        "title": p.title,
                        "citations": p.citationCount,
                        "year": p.year,
                        "arxiv_id": arxiv_id
                    })
                    if len(papers) >= limit:
                        break
                        
        return json.dumps(papers, indent=2)
    except Exception as e:
        return f"Error discovering papers: {e}"


def search_papers(
    query: str, 
    max_results: int = 10, 
    date_from: Optional[str] = None,
    categories: Optional[List[str]] = None,
    sort_by: str = "relevance"
) -> str:
    """
    Search arXiv with optional category, date, and boolean filters. 
    Enforces arXiv's 3-second rate limit automatically.
    """
    logger.info(f"[Tool:search_papers] Query: '{query}'")
    
    # Construct advanced query with categories
    advanced_query = query
    if categories:
        cat_query = " OR ".join([f"cat:{c}" for c in categories])
        advanced_query = f"({advanced_query}) AND ({cat_query})"
        
    sort_criterion = arxiv.SortCriterion.Relevance
    if sort_by.lower() == "date":
        sort_criterion = arxiv.SortCriterion.SubmittedDate
        
    try:
        # Enforce arXiv's rate limit natively
        client = arxiv.Client(page_size=max_results, delay_seconds=3.0, num_retries=3)
        search = arxiv.Search(query=advanced_query, max_results=max_results, sort_by=sort_criterion)
        
        results = []
        for paper in client.results(search):
            # Apply date filtering manually if date_from is provided (format: YYYY-MM-DD)
            if date_from:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                if paper.published.date() < date_from_obj:
                    continue
            
            results.append({
                "arxiv_id": paper.get_short_id(),
                "title": paper.title,
                "published": str(paper.published.date()),
                "authors": [a.name for a in paper.authors],
                "categories": paper.categories,
                "summary": paper.summary
            })
            
            if len(results) >= max_results:
                break
            
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching arXiv: {e}"


def download_paper(paper_id: str, working_dir: str) -> str:
    """
    Download a paper by its arXiv ID. Tries HTML first, falls back to PDF. 
    Stores the paper locally for read_paper.
    """
    logger.info(f"[Tool:download_paper] Fetching arXiv ID: '{paper_id}'")
    try:
        work_path = Path(working_dir).resolve()
        papers_dir = work_path / "literature"
        papers_dir.mkdir(parents=True, exist_ok=True)
        
        html_file = papers_dir / f"{paper_id}.html"
        pdf_file = papers_dir / f"{paper_id}.pdf"
        
        # 1. Try HTML first (faster, token-friendly)
        html_url = f"https://arxiv.org/html/{paper_id}"
        try:
            req = urllib.request.Request(html_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode('utf-8')
                html_file.write_text(html_content, encoding='utf-8')
                return f"Successfully downloaded HTML version of {paper_id} to {html_file}. You can now use read_paper."
        except urllib.error.HTTPError:
            pass # HTML not available, fallback to PDF
            
        # 2. Fallback to PDF
        client = arxiv.Client()
        search = arxiv.Search(id_list=[paper_id])
        paper = next(client.results(search))
        
        paper.download_pdf(dirpath=str(papers_dir), filename=f"{paper_id}.pdf")
        return f"HTML not available. Successfully downloaded PDF version of '{paper.title}' to {pdf_file}. You can now use read_paper."
        
    except StopIteration:
        return f"Error: No paper found on arXiv with ID '{paper_id}'."
    except Exception as e:
        return f"Error downloading paper {paper_id}: {e}"


def list_papers(working_dir: str) -> str:
    """
    List all papers downloaded locally. Returns arXiv IDs.
    """
    work_path = Path(working_dir).resolve()
    papers_dir = work_path / "literature"
    
    if not papers_dir.exists():
        return "No papers downloaded yet."
        
    papers = []
    for f in papers_dir.iterdir():
        if f.suffix in [".pdf", ".html"]:
            papers.append(f.name)
            
    return json.dumps({"downloaded_papers": papers}, indent=2)


# read_paper moved to tools/ingestion.py (S1-2): section-aware ingestion with no
# length-capped truncation, replacing the old regex tag-stripper and blob path.
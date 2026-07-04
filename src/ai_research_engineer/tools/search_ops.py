"""Multi-source literature/code search tools (S1-3).

OpenAlex, Papers with Code, GitHub, and a provider-pluggable web search. Each
returns a JSON string (or a short graceful message on empty results / HTTP
errors / rate limits). All are registered with the Stage 1 tool registry with
their ``requires`` so the agent's toolbelt is built from what the environment
actually provides.
"""

import json
import logging
import os
from typing import Optional

import requests

from ai_research_engineer.core.config import get_web_provider
from ai_research_engineer.core.tool_registry import register_tool


logger = logging.getLogger(__name__)

_TIMEOUT = 30


def _record_session_literature(docs: list) -> None:
    """S1-5 auto-upsert: record results into the active session literature index.

    These tools have no working_dir, so they target the active session index set
    at agent construction. Best-effort and a no-op when no session is active.
    """
    try:
        from ai_research_engineer.core.lit_index import record_papers

        record_papers(docs)
    except Exception as exc:  # never let indexing break a search
        logger.debug("[search_ops] session literature record failed: %s", exc)


# --------------------------------------------------------------------------- #
# OpenAlex
# --------------------------------------------------------------------------- #
def _reconstruct_inverted_abstract(inverted_index: Optional[dict]) -> str:
    """Rebuild an abstract from OpenAlex's ``abstract_inverted_index``."""
    if not inverted_index:
        return ""
    positioned = []
    for word, positions in inverted_index.items():
        for pos in positions:
            positioned.append((pos, word))
    positioned.sort(key=lambda pw: pw[0])
    return " ".join(word for _, word in positioned)


def openalex_search(query: str, limit: int = 10, year_from: Optional[int] = None) -> str:
    """Search OpenAlex works (no API key). Returns title/year/abstract/doi/cited_by_count."""
    try:
        params = {"search": query, "per-page": max(1, min(int(limit), 200))}
        if year_from:
            params["filter"] = f"from_publication_date:{int(year_from)}-01-01"
        resp = requests.get(
            "https://api.openalex.org/works",
            params=params,
            headers={"User-Agent": "ai-research-engineer"},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 429:
            return "OpenAlex rate limit reached (HTTP 429). Please retry shortly."
        resp.raise_for_status()
        data = resp.json()
        results = []
        for work in (data.get("results") or [])[:limit]:
            results.append(
                {
                    "title": work.get("title"),
                    "year": work.get("publication_year"),
                    "abstract": _reconstruct_inverted_abstract(work.get("abstract_inverted_index")),
                    "doi": work.get("doi"),
                    "cited_by_count": work.get("cited_by_count", 0),
                }
            )
        if not results:
            return f"No OpenAlex results for '{query}'."
        _record_session_literature(
            [
                {"id": r.get("doi") or r.get("title"), "title": r.get("title"),
                 "abstract": r.get("abstract"), "source": "openalex",
                 "url": r.get("doi"), "year": r.get("year")}
                for r in results
            ]
        )
        return json.dumps(results, indent=2)
    except requests.exceptions.RequestException as e:
        return f"OpenAlex search failed (network error): {e}"
    except Exception as e:
        return f"OpenAlex search error: {e}"


# --------------------------------------------------------------------------- #
# Papers with Code
# --------------------------------------------------------------------------- #
def paperswithcode_search(query: str, limit: int = 10) -> str:
    """Search Papers with Code for papers and their linked repositories."""
    try:
        resp = requests.get(
            "https://paperswithcode.com/api/v1/search/",
            params={"q": query, "items_per_page": max(1, min(int(limit), 100))},
            headers={"Accept": "application/json", "User-Agent": "ai-research-engineer"},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 429:
            return "Papers with Code rate limit reached (HTTP 429). Please retry shortly."
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in (data.get("results") or [])[:limit]:
            paper = item.get("paper") or {}
            repo = item.get("repository") or {}
            results.append(
                {
                    "title": paper.get("title"),
                    "url": paper.get("url_abs") or paper.get("url_pdf"),
                    "published": paper.get("published"),
                    "repo_url": repo.get("url"),
                    "repo_stars": repo.get("stars"),
                    "framework": repo.get("framework"),
                }
            )
        if not results:
            return f"No Papers with Code results for '{query}'."
        _record_session_literature(
            [
                {"id": r.get("url") or r.get("title"), "title": r.get("title"),
                 "abstract": None, "source": "paperswithcode",
                 "url": r.get("url"), "year": r.get("published")}
                for r in results
            ]
        )
        return json.dumps(results, indent=2)
    except requests.exceptions.RequestException as e:
        return f"Papers with Code search failed (network error): {e}"
    except Exception as e:
        return f"Papers with Code search error: {e}"


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #
def github_search(query: str, limit: int = 10, mode: str = "repositories") -> str:
    """Search GitHub repositories or code. Honors GITHUB_TOKEN; degrades to the
    lower unauthenticated rate limit (and a graceful message) without it."""
    try:
        if mode not in ("repositories", "code"):
            mode = "repositories"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-research-engineer"}
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # Unauthenticated search has a much lower budget — ask for fewer.
        per_page = max(1, min(int(limit), 100 if token else 30))
        resp = requests.get(
            f"https://api.github.com/search/{mode}",
            params={"q": query, "per_page": per_page},
            headers=headers,
            timeout=_TIMEOUT,
        )
        if resp.status_code in (403, 429):
            hint = "" if token else " Set GITHUB_TOKEN to raise the unauthenticated limit."
            return f"GitHub search rate limit reached (HTTP {resp.status_code}).{hint}"
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in (data.get("items") or [])[:limit]:
            if mode == "repositories":
                results.append(
                    {
                        "full_name": item.get("full_name"),
                        "url": item.get("html_url"),
                        "stars": item.get("stargazers_count"),
                        "description": item.get("description"),
                    }
                )
            else:
                repo = item.get("repository") or {}
                results.append({"repo": repo.get("full_name"), "path": item.get("path"), "url": item.get("html_url")})
        if not results:
            return f"No GitHub {mode} results for '{query}'."
        return json.dumps(results, indent=2)
    except requests.exceptions.RequestException as e:
        return f"GitHub search failed (network error): {e}"
    except Exception as e:
        return f"GitHub search error: {e}"


# --------------------------------------------------------------------------- #
# Web search (provider-pluggable)
# --------------------------------------------------------------------------- #
def web_search(query: str, limit: int = 10) -> str:
    """Provider-pluggable web search (config search.web_provider). Registered only
    when a provider is configured; still guards at call time."""
    provider = get_web_provider()
    if provider == "none":
        return "Web search is not configured (search.web_provider=none)."
    try:
        if provider == "tavily":
            key = os.getenv("TAVILY_API_KEY", "").strip()
            if not key:
                return "Web search provider 'tavily' selected but TAVILY_API_KEY is not set."
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": int(limit)},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                return "Web search (tavily) rate limit reached (HTTP 429)."
            resp.raise_for_status()
            data = resp.json()
            results = [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
                for r in (data.get("results") or [])[:limit]
            ]
            if not results:
                return f"No web results for '{query}'."
            return json.dumps(results, indent=2)
        # brave / searxng share the same shape; wired as providers are enabled.
        return f"Web search provider '{provider}' is configured but not yet wired in this build."
    except requests.exceptions.RequestException as e:
        return f"Web search failed (network error): {e}"
    except Exception as e:
        return f"Web search error: {e}"


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
register_tool("openalex_search", openalex_search, requires=["network"])
register_tool("paperswithcode_search", paperswithcode_search, requires=["network"])
register_tool("github_search", github_search, requires=["network"])
register_tool("web_search", web_search, requires=["network", "config:search.web_provider"])


__all__ = ["openalex_search", "paperswithcode_search", "github_search", "web_search"]

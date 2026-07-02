"""
Reference/citation verification for AI Research Engineer.

Verification chain (non-blocking, fail-soft throughout):
  1. Crossref by DOI      — primary; keyless; polite-pool via User-Agent + mailto param
  2. Crossref title search — fallback when no DOI
  3. OpenAlex             — optional; only runs when OPENALEX_API_KEY is set; fail-soft on 401/403/409
  4. URL HEAD             — last resort for url-only entries; gated by web_ops SSRF deny-list

Any network/parse error marks the reference "unverified" and continues.
Results are cached in a SQLite table (reference_verifications) to avoid
re-hitting APIs across re-runs within the same working directory.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus

import requests


logger = logging.getLogger(__name__)

_CROSSREF_BASE = "https://api.crossref.org/works"
_OPENALEX_BASE = "https://api.openalex.org/works"
_REQUEST_TIMEOUT = 10   # seconds per individual call
_BACKOFF_SECONDS = 5    # sleep on 429 before one retry

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_verifications (
    cache_key   TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    method      TEXT NOT NULL,
    detail      TEXT,
    checked_at  TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _entry_cache_key(entry: Dict[str, Any]) -> str:
    doi = (entry.get("doi") or "").strip().lower()
    title = (entry.get("title") or "").strip().lower()
    return hashlib.sha256((doi or title).encode()).hexdigest()


def _open_cache(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(_CACHE_SCHEMA)
    con.commit()
    return con


# ---------------------------------------------------------------------------
# BibTeX parsing — tolerant regex, no external dep required
# ---------------------------------------------------------------------------

# Matches both brace-quoted and double-quoted field values (single nesting level).
_BIB_FIELD_RE = re.compile(
    r"""\b(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)")""",
    re.MULTILINE,
)


def parse_bib(bib_path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse a .bib file into {cite_key: {doi, title, authors, year, url}}.

    Tolerant of unknown field names, nested braces, and encoding issues.
    Returns {} if the file does not exist or cannot be read.
    """
    try:
        text = bib_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for block in re.split(r"(?=@\w+\s*\{)", text):
        m = re.match(r"@\w+\s*\{([^,]+),", block.strip())
        if not m:
            continue
        key = m.group(1).strip()
        fields: Dict[str, str] = {}
        for fm in _BIB_FIELD_RE.finditer(block):
            fields[fm.group(1).lower()] = (fm.group(2) or fm.group(3) or "").strip()
        result[key] = {
            "doi": fields.get("doi") or None,
            "title": fields.get("title") or None,
            "authors": fields.get("author") or None,
            "year": int(fields["year"]) if fields.get("year", "").isdigit() else None,
            "url": fields.get("url") or None,
        }
    return result


# ---------------------------------------------------------------------------
# Citation key extraction from manuscript text
# ---------------------------------------------------------------------------

# Handles: \cite{k}, \citep{k}, \citet{k}, \cite*{k}, comma-separated \cite{a,b},
#          and Pandoc markdown [@key], [@key1, @key2].
_CITE_RE = re.compile(r"\\cite[pt]?\*?\{([^}]+)\}|\[@([^\]]+)\]")


def find_cite_keys(text: str) -> Set[str]:
    """Extract all citation keys from LaTeX / Markdown manuscript text."""
    keys: Set[str] = set()
    for m in _CITE_RE.finditer(text):
        raw = m.group(1) or m.group(2) or ""
        for part in raw.split(","):
            k = part.strip().lstrip("@")
            if k:
                keys.add(k)
    return keys


def find_unknown_cite_keys(manuscript_text: str, bib_keys: Set[str]) -> Set[str]:
    """Return cite keys used in manuscript text that have no matching .bib entry.

    These are hallucinated citations — the worst failure mode; detected at
    zero network cost by pure text comparison.
    """
    return find_cite_keys(manuscript_text) - bib_keys


# ---------------------------------------------------------------------------
# Crossref polite-pool helpers
# ---------------------------------------------------------------------------


def _polite_params() -> Dict[str, str]:
    mailto = os.environ.get("CROSSREF_MAILTO", "")
    return {"mailto": mailto} if mailto else {}


def _ua() -> str:
    mailto = os.environ.get("CROSSREF_MAILTO", "")
    return f"Archimedes/0.1 (mailto:{mailto})" if mailto else "Archimedes/0.1"


def _get(url: str, params: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
    """GET with 429 back-off (one retry). Returns None on any exception."""
    headers = {"User-Agent": _ua()}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=_REQUEST_TIMEOUT)
        if resp.status_code == 429:
            time.sleep(_BACKOFF_SECONDS)
            resp = requests.get(url, params=params, headers=headers, timeout=_REQUEST_TIMEOUT)
        return resp
    except Exception as exc:
        logger.debug("[references] GET %s failed: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Individual verification steps
# ---------------------------------------------------------------------------


def _crossref_doi(doi: str) -> Optional[Dict[str, Any]]:
    resp = _get(f"{_CROSSREF_BASE}/{quote_plus(doi)}", params=_polite_params())
    if resp is None:
        return None
    if resp.status_code == 200:
        return {"status": "verified", "method": "crossref_doi", "detail": f"DOI {doi} confirmed via Crossref"}
    if resp.status_code == 404:
        return {"status": "not_found", "method": "crossref_doi", "detail": f"DOI {doi} not found in Crossref"}
    return None  # other status → fall through


def _crossref_title(title: str) -> Optional[Dict[str, Any]]:
    resp = _get(_CROSSREF_BASE, params={**_polite_params(), "query.bibliographic": title, "rows": "1"})
    if resp is None or resp.status_code != 200:
        return None
    try:
        items = resp.json().get("message", {}).get("items", [])
        if items:
            matched = ((items[0].get("title") or [""])[0])[:80]
            return {"status": "verified", "method": "crossref_title", "detail": f"Crossref title match: {matched}"}
        return {"status": "not_found", "method": "crossref_title", "detail": "no Crossref results for title"}
    except Exception:
        return None


def _openalex(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """OpenAlex lookup — only when OPENALEX_API_KEY is set; fail-soft on all auth/quota errors."""
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if not api_key:
        return None
    doi = (entry.get("doi") or "").strip()
    title = (entry.get("title") or "").strip()
    try:
        if doi:
            url = f"{_OPENALEX_BASE}/https://doi.org/{quote_plus(doi)}"
            resp = requests.get(url, params={"api_key": api_key}, headers={"User-Agent": _ua()}, timeout=_REQUEST_TIMEOUT)
        elif title:
            resp = requests.get(
                _OPENALEX_BASE,
                params={"search": title, "per_page": "1", "api_key": api_key},
                headers={"User-Agent": _ua()},
                timeout=_REQUEST_TIMEOUT,
            )
        else:
            return None
        # Fail-soft on any auth / quota / transition error
        if resp.status_code in (401, 403, 409, 429):
            logger.debug("[references] OpenAlex status %s — skipping (fail-soft)", resp.status_code)
            return None
        if resp.status_code == 200:
            if doi:
                return {"status": "verified", "method": "openalex_doi", "detail": f"OpenAlex confirmed DOI {doi}"}
            results = resp.json().get("results", [])
            if results:
                return {
                    "status": "verified",
                    "method": "openalex_title",
                    "detail": f"OpenAlex match: {results[0].get('display_name', '')[:80]}",
                }
            return {"status": "not_found", "method": "openalex_title", "detail": "no OpenAlex match for title"}
    except Exception as exc:
        logger.debug("[references] OpenAlex fail-soft: %s", exc)
    return None


def _url_head(url: str) -> Optional[Dict[str, Any]]:
    """HEAD request gated by the existing web_ops SSRF deny-list. Never raises."""
    from ai_research_engineer.tools.web_ops import _check_url_for_ssrf

    ssrf = _check_url_for_ssrf(url)
    if ssrf:
        return {"status": "unverified", "method": "url_head", "detail": f"SSRF blocked: {ssrf}"}
    try:
        resp = requests.head(url, timeout=_REQUEST_TIMEOUT, allow_redirects=True, headers={"User-Agent": _ua()})
        if resp.status_code < 400:
            return {"status": "verified", "method": "url_head", "detail": f"HEAD {url} → {resp.status_code}"}
        return {"status": "not_found", "method": "url_head", "detail": f"HEAD {url} → {resp.status_code}"}
    except Exception as exc:
        logger.debug("[references] URL HEAD failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def verify_reference(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a single bib entry via the Crossref→OpenAlex→URL-HEAD chain.

    Returns {"status": "verified"|"not_found"|"unverified", "method": str, "detail": str}.
    Never raises — any exception yields status="unverified".
    """
    try:
        doi = (entry.get("doi") or "").strip()
        title = (entry.get("title") or "").strip()
        url = (entry.get("url") or "").strip()

        if doi:
            r = _crossref_doi(doi)
            if r is not None:
                return r

        if title:
            r = _crossref_title(title)
            if r is not None:
                return r

        r = _openalex(entry)
        if r is not None:
            return r

        if url:
            r = _url_head(url)
            if r is not None:
                return r

        return {"status": "unverified", "method": "none", "detail": "no verifiable identifier (DOI/title/URL) found"}
    except Exception as exc:
        logger.warning("[references] verify_reference fail-soft: %s", exc)
        return {"status": "unverified", "method": "error", "detail": str(exc)}


def verify_online(
    entries: Dict[str, Dict[str, Any]],
    cache_db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Verify all .bib entries online with a SQLite cache to avoid redundant API calls.

    Parameters
    ----------
    entries:
        {cite_key: {doi, title, authors, year, url}} as returned by parse_bib()
    cache_db_path:
        Path to the SQLite cache file; defaults to .data/pipeline.db relative to CWD.

    Returns
    -------
    List of {key, status, method, detail, cached} dicts — one per entry.
    """
    db_path = cache_db_path or (Path(".data") / "pipeline.db")
    con = _open_cache(db_path)
    results: List[Dict[str, Any]] = []
    try:
        for key, entry in entries.items():
            ck = _entry_cache_key(entry)
            row = con.execute(
                "SELECT status, method, detail FROM reference_verifications WHERE cache_key = ?",
                (ck,),
            ).fetchone()
            if row:
                results.append({"key": key, "status": row[0], "method": row[1], "detail": row[2], "cached": True})
                continue
            result = verify_reference(entry)
            con.execute(
                "INSERT OR REPLACE INTO reference_verifications "
                "(cache_key, status, method, detail, checked_at) VALUES (?, ?, ?, ?, ?)",
                (ck, result["status"], result["method"], result.get("detail", ""), datetime.now(timezone.utc).isoformat()),
            )
            con.commit()
            results.append({"key": key, **result, "cached": False})
    finally:
        con.close()
    return results

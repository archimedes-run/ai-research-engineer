"""Section-aware paper ingestion v2 (S1-2).

Parses a downloaded paper (arXiv HTML or PDF) into section-aware structured
output — a list of ``{section_path, title, markdown}`` preserving headings,
tables (as markdown), and math (LaTeX kept verbatim inline) — and persists it to
``literature/<paper_id>/{sections.json, full.md}``. Nothing is ever truncated.

Tools:
- ``read_paper(paper_id, working_dir, section=None)`` — with a section, return
  only that section (fuzzy title match); without, return a table of contents +
  abstract + first section (never a giant truncated blob).
- ``search_paper(paper_id, query, working_dir, top_k=5)`` — embedding retrieval
  over the paper's section chunks, index cached per paper.
"""

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


# --------------------------------------------------------------------------- #
# HTML -> markdown (arXiv / ar5iv structure)
# --------------------------------------------------------------------------- #
def _table_to_markdown(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * ncols) + " |"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _inline_math(soup) -> None:
    """Replace <math>/ltx_Math with their LaTeX (``alttext``) inline, verbatim."""
    from bs4 import NavigableString

    for math in soup.find_all("math"):
        latex = math.get("alttext") or math.get_text(strip=True)
        math.replace_with(NavigableString(f"${latex}$"))
    for span in soup.find_all("span", class_="ltx_Math"):
        latex = span.get("alttext") or span.get_text(strip=True)
        span.replace_with(NavigableString(f"${latex}$"))


def _emit_markdown(node, parts: List[str]) -> None:
    from bs4 import Tag

    for child in node.children:
        if not isinstance(child, Tag):
            continue
        name = (child.name or "").lower()
        if name in ("script", "style"):
            continue
        classes = child.get("class") or []
        if re.fullmatch(r"h[1-6]", name):
            level = int(name[1])
            title = re.sub(r"\s+", " ", child.get_text(" ", strip=True))
            if "ltx_title_abstract" in classes or title.lower() == "abstract":
                level = 2  # normalize the abstract to a section-level heading
            if title:
                parts.append(f"\n{'#' * level} {title}\n")
        elif name == "table":
            md = _table_to_markdown(child)
            if md:
                parts.append("\n" + md + "\n")
        elif name == "p":
            text = re.sub(r"[ \t]+", " ", child.get_text(" ", strip=True))
            if text:
                parts.append(text + "\n")
        else:
            _emit_markdown(child, parts)


def html_to_markdown(html: str) -> str:
    """Convert arXiv/ar5iv HTML into markdown (headings, tables, inline LaTeX)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    _inline_math(soup)
    root = soup.body or soup
    parts: List[str] = []
    _emit_markdown(root, parts)
    md = "\n".join(parts)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF into markdown using pymupdf4llm (replaces PyPDF2)."""
    import pymupdf4llm

    return pymupdf4llm.to_markdown(str(pdf_path))


# --------------------------------------------------------------------------- #
# markdown -> sections
# --------------------------------------------------------------------------- #
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def split_markdown_into_sections(md: str) -> List[Dict[str, Any]]:
    """Split markdown into ``{section_path, title, markdown}`` at heading lines."""
    sections: List[Dict[str, Any]] = []
    stack: List[Tuple[int, str]] = []
    cur_path: Optional[List[str]] = None
    cur_lines: List[str] = []

    def _flush() -> None:
        if cur_path is not None:
            sections.append(
                {"section_path": list(cur_path), "title": cur_path[-1], "markdown": "\n".join(cur_lines).strip()}
            )

    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            _flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur_path = [t for _, t in stack]
            cur_lines = []
        elif cur_path is not None:
            cur_lines.append(line)
    _flush()
    return sections


# --------------------------------------------------------------------------- #
# ingestion + persistence
# --------------------------------------------------------------------------- #
def _paper_dir(paper_id: str, working_dir: str) -> Path:
    return Path(working_dir).resolve() / "literature" / paper_id


def ingest_paper(paper_id: str, working_dir: str) -> Optional[List[Dict[str, Any]]]:
    """Parse the downloaded paper into sections and persist sections.json + full.md.

    Returns the sections list, or ``None`` if no downloaded file exists.
    """
    lit = Path(working_dir).resolve() / "literature"
    html_path = lit / f"{paper_id}.html"
    pdf_path = lit / f"{paper_id}.pdf"

    if html_path.exists():
        md = html_to_markdown(html_path.read_text(encoding="utf-8"))
    elif pdf_path.exists():
        md = pdf_to_markdown(pdf_path)
    else:
        return None

    sections = split_markdown_into_sections(md)
    if not sections:
        # No headings detected (e.g. some PDFs) — keep the whole document as one section.
        sections = [{"section_path": ["Full Text"], "title": "Full Text", "markdown": md.strip()}]

    out_dir = _paper_dir(paper_id, working_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sections.json").write_text(json.dumps(sections, indent=2), encoding="utf-8")
    (out_dir / "full.md").write_text(md, encoding="utf-8")
    logger.info("[ingestion] %s -> %d sections", paper_id, len(sections))

    # S1-5: auto-upsert this paper's abstract into the session literature index.
    try:
        abstract = next(
            (s["markdown"] for s in sections if s["title"].lower() == "abstract"),
            sections[0]["markdown"],
        )
        from ai_research_engineer.core.lit_index import record_papers

        record_papers(
            [{"id": paper_id, "title": paper_id, "abstract": abstract,
              "source": "ingested", "url": None, "year": None}],
            working_dir=working_dir,
        )
    except Exception as exc:  # indexing is best-effort
        logger.debug("[ingestion] session literature record failed: %s", exc)

    return sections


def _load_or_ingest(paper_id: str, working_dir: str) -> Optional[List[Dict[str, Any]]]:
    sections_path = _paper_dir(paper_id, working_dir) / "sections.json"
    if sections_path.exists():
        try:
            return json.loads(sections_path.read_text(encoding="utf-8"))
        except Exception:  # corrupt cache — re-ingest
            pass
    return ingest_paper(paper_id, working_dir)


def _fuzzy_find_section(sections: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    q = query.lower().strip()
    for s in sections:  # substring on title or any path component wins
        if q in s["title"].lower() or any(q in p.lower() for p in s["section_path"]):
            return s
    best, best_ratio = None, 0.0
    for s in sections:
        ratio = SequenceMatcher(None, q, s["title"].lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = s, ratio
    return best if best_ratio >= 0.5 else None


def read_paper(paper_id: str, working_dir: str, section: Optional[str] = None) -> str:
    """Read a locally downloaded paper (S1-2).

    With ``section``: return only that section (fuzzy title match). Without: a
    table of contents + abstract + first section — never a truncated blob.
    """
    try:
        sections = _load_or_ingest(paper_id, working_dir)
        if sections is None:
            return f"Error: Paper {paper_id} not found locally. Call download_paper first."
        if not sections:
            return f"Paper {paper_id} was ingested but no content could be extracted."

        if section:
            match = _fuzzy_find_section(sections, section)
            if match is None:
                toc = "\n".join(f"- {s['title']}" for s in sections)
                return f"Section '{section}' not found in {paper_id}. Available sections:\n{toc}"
            return f"# {match['title']}\n\n{match['markdown']}"

        # Table-of-contents mode.
        toc = "\n".join(f"{i + 1}. {s['title']}" for i, s in enumerate(sections))
        abstract = next(
            (
                s
                for s in sections
                if s["title"].lower() == "abstract" or "abstract" in [p.lower() for p in s["section_path"]]
            ),
            None,
        )
        first = next((s for s in sections if s is not abstract), sections[0])
        parts = [f"# {paper_id}", "", "## Table of contents", toc]
        if abstract:
            parts += ["", "## Abstract", abstract["markdown"]]
        parts += ["", f"## {first['title']}", first["markdown"]]
        parts += [
            "",
            f"_Use read_paper('{paper_id}', section='<title>') for a full section, "
            f"or search_paper('{paper_id}', '<query>') to search within the paper._",
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Error reading paper {paper_id}: {e}"


# --------------------------------------------------------------------------- #
# per-paper embedding search
# --------------------------------------------------------------------------- #
def _chunk_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    for s in sections:
        text = (s.get("markdown") or "").strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            piece = text[start : start + CHUNK_SIZE]
            chunks.append({"title": s["title"], "section_path": s["section_path"], "text": piece})
            if start + CHUNK_SIZE >= len(text):
                break
            start += step
    return chunks


def _load_or_build_chunk_index(index_dir: Path, sections: List[Dict[str, Any]]):
    chunks_path = index_dir / "chunks.json"
    vecs_path = index_dir / "embeddings.npy"
    if chunks_path.exists() and vecs_path.exists():
        try:
            chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
            vecs = np.load(vecs_path)
            if len(chunks) == len(vecs):
                return chunks, vecs
        except Exception:
            pass

    from ai_research_engineer.core.embeddings import embed_texts

    chunks = _chunk_sections(sections)
    if not chunks:
        return [], np.zeros((0, 0), dtype=np.float32)
    vecs = embed_texts([c["text"] for c in chunks])
    index_dir.mkdir(parents=True, exist_ok=True)
    chunks_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    np.save(vecs_path, vecs)
    return chunks, vecs


def search_paper(paper_id: str, query: str, working_dir: str, top_k: int = 5) -> str:
    """Embedding retrieval over a paper's section chunks (S1-2).

    The per-paper chunk index is built lazily via core embeddings and cached
    under ``literature/<paper_id>/index/``.
    """
    try:
        from ai_research_engineer.core.embeddings import embed_texts, get_faiss_index

        sections = _load_or_ingest(paper_id, working_dir)
        if sections is None:
            return f"Error: Paper {paper_id} not found locally. Call download_paper first."

        index_dir = _paper_dir(paper_id, working_dir) / "index"
        chunks, vecs = _load_or_build_chunk_index(index_dir, sections)
        if not chunks:
            return f"No searchable content found in {paper_id}."

        faiss = get_faiss_index(paper_id, int(vecs.shape[1]))
        for i, vec in enumerate(vecs):
            faiss.add(i, np.asarray(vec, dtype=np.float32))

        q_vec = np.asarray(embed_texts([query])[0], dtype=np.float32)
        hits = faiss.search(q_vec, top_k=top_k)
        if not hits:
            return f"No results for '{query}' in {paper_id}."

        out = [f"Top {len(hits)} matches for '{query}' in {paper_id}:", ""]
        for rank, (idx, score) in enumerate(hits, 1):
            chunk = chunks[idx]
            out.append(f"### {rank}. [{chunk['title']}] (score {score:.3f})")
            out.append(chunk["text"])
            out.append("")
        return "\n".join(out)
    except Exception as e:
        return f"Error searching paper {paper_id}: {e}"


__all__ = [
    "ingest_paper",
    "read_paper",
    "search_paper",
    "html_to_markdown",
    "pdf_to_markdown",
    "split_markdown_into_sections",
]

"""
Semantic Scholar operations for the AI Research Engineer.
Implements deep paper discovery, author analysis, recommendations, and session tracking.
"""

import json
import logging
import os      # FIXED: Added missing import
import time    # FIXED: Added missing import
from pathlib import Path
from typing import Optional, List, Dict, Any

from semanticscholar import SemanticScholar

logger = logging.getLogger(__name__)

# Initialize Semantic Scholar client
api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
sch = SemanticScholar(api_key=api_key)

_last_semanticscholar_call = 0.0

def _enforce_1_rps_limit():
    """Ensures at least 1.0 second passes between API calls."""
    global _last_semanticscholar_call
    current_time = time.time()
    time_since_last = current_time - _last_semanticscholar_call
    
    if time_since_last < 1.0:
        # Sleep for the remainder of the second to strictly respect the 1 RPS limit
        time.sleep(1.0 - time_since_last)
        
    _last_semanticscholar_call = time.time()

# --- Helper for Session Tracking ---
def _track_paper(working_dir: str, paper_data: dict, source_tool: str):
    """Internal helper to track papers retrieved during the session."""
    try:
        work_path = Path(working_dir).resolve()
        track_file = work_path / ".tracked_papers.json"
        
        tracked = []
        if track_file.exists():
            with open(track_file, "r") as f:
                tracked = json.load(f)
                
        # Avoid exact duplicates by paperId
        if not any(p.get("paperId") == paper_data.get("paperId") for p in tracked):
            paper_data["_source_tool"] = source_tool
            tracked.append(paper_data)
            
        with open(track_file, "w") as f:
            json.dump(tracked, f)
    except Exception as e:
        logger.warning(f"Failed to track paper: {e}")

# ==========================================
# PAPERS
# ==========================================

def search_papers(query: str, year: Optional[str] = None, min_citations: int = 0, limit: int = 10, working_dir: str = "") -> str:
    """Search papers by keyword with filters."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        results = sch.search_paper(query, year=year, limit=limit * 3, fields=['title', 'authors', 'year', 'abstract', 'citationCount', 'url', 'externalIds', 'citationStyles'])
        
        papers = []
        for p in results:
            if p.citationCount is not None and p.citationCount >= min_citations:
                paper_dict = {
                    "paperId": p.paperId,
                    "title": p.title,
                    "year": p.year,
                    "citations": p.citationCount,
                    "authors": [a.name for a in p.authors] if p.authors else [],
                    "abstract": p.abstract[:500] + "..." if p.abstract else None,
                    "url": p.url,
                    "bibtex": p.citationStyles.get("bibtex") if p.citationStyles else None
                }
                papers.append(paper_dict)
                if working_dir: _track_paper(working_dir, paper_dict, "search_papers")
                
                if len(papers) >= limit: break
                
        return json.dumps(papers, indent=2)
    except Exception as e:
        return f"Error: {e}"

def get_paper_details(paper_id: str, working_dir: str = "") -> str:
    """Get full metadata for a specific paper using its ID or DOI."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        p = sch.get_paper(paper_id, fields=['title', 'authors', 'year', 'abstract', 'citationCount', 'referenceCount', 'influentialCitationCount', 'url', 'tldr', 'citationStyles'])
        paper_dict = {
            "paperId": p.paperId,
            "title": p.title,
            "year": p.year,
            "tldr": p.tldr.get("text") if p.tldr else None,
            "abstract": p.abstract,
            "citations": p.citationCount,
            "references": p.referenceCount,
            "influentialCitations": p.influentialCitationCount,
            "authors": [{"authorId": a.authorId, "name": a.name} for a in p.authors] if p.authors else [],
            "url": p.url,
            "bibtex": p.citationStyles.get("bibtex") if p.citationStyles else None
        }
        if working_dir: _track_paper(working_dir, paper_dict, "get_paper_details")
        return json.dumps(paper_dict, indent=2)
    except Exception as e:
        return f"Error getting paper details: {e}"

def get_paper_citations(paper_id: str, limit: int = 10) -> str:
    """Find papers that cite a given paper."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        p = sch.get_paper(paper_id, fields=['citations.title', 'citations.authors', 'citations.year', 'citations.citationCount'])
        citations = []
        for cite in getattr(p, 'citations', [])[:limit]:
            citations.append({
                "paperId": cite.paperId,
                "title": cite.title,
                "year": cite.year,
                "citations": cite.citationCount
            })
        return json.dumps(citations, indent=2)
    except Exception as e:
        return f"Error: {e}"

def get_paper_references(paper_id: str, limit: int = 10) -> str:
    """Find papers a given paper cites."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        p = sch.get_paper(paper_id, fields=['references.title', 'references.authors', 'references.year', 'references.citationCount'])
        refs = []
        for ref in getattr(p, 'references', [])[:limit]:
            refs.append({
                "paperId": ref.paperId,
                "title": ref.title,
                "year": ref.year,
                "citations": ref.citationCount
            })
        return json.dumps(refs, indent=2)
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# AUTHORS
# ==========================================

def search_authors(query: str, limit: int = 5) -> str:
    """Search researchers by name."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        results = sch.search_author(query, limit=limit, fields=['name', 'affiliations', 'paperCount', 'citationCount', 'hIndex'])
        authors = [{"authorId": a.authorId, "name": a.name, "hIndex": a.hIndex, "paperCount": a.paperCount, "citations": a.citationCount, "affiliations": a.affiliations} for a in results]
        return json.dumps(authors, indent=2)
    except Exception as e:
        return f"Error: {e}"

def get_author_details(author_id: str) -> str:
    """Get author profile and publications."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        a = sch.get_author(author_id, fields=['name', 'affiliations', 'paperCount', 'citationCount', 'hIndex', 'url'])
        details = {
            "authorId": a.authorId,
            "name": a.name,
            "affiliations": a.affiliations,
            "metrics": {"hIndex": a.hIndex, "papers": a.paperCount, "citations": a.citationCount},
            "url": a.url
        }
        return json.dumps(details, indent=2)
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# RECOMMENDATIONS
# ==========================================

def get_recommendations(paper_id: str, limit: int = 5) -> str:
    """ML-based similar paper discovery."""
    try:
        _enforce_1_rps_limit() # FIXED: Rate limit enforced
        results = sch.get_recommended_papers(paper_id, limit=limit, fields=['title', 'authors', 'year', 'citationCount'])
        recs = [{"paperId": p.paperId, "title": p.title, "year": p.year, "citations": p.citationCount} for p in results]
        return json.dumps(recs, indent=2)
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# SESSION & EXPORT
# ==========================================

def list_tracked_papers(working_dir: str, source_tool: Optional[str] = None) -> str:
    """View papers retrieved this session."""
    try:
        track_file = Path(working_dir).resolve() / ".tracked_papers.json"
        if not track_file.exists(): return "No papers tracked yet."
        
        with open(track_file, "r") as f:
            tracked = json.load(f)
            
        if source_tool:
            tracked = [p for p in tracked if p.get("_source_tool") == source_tool]
            
        summary = [{"paperId": p.get("paperId"), "title": p.get("title")} for p in tracked]
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error: {e}"

def export_bibtex(working_dir: str, file_name: str = "references.bib") -> str:
    """Export tracked papers to a BibTeX file."""
    try:
        work_path = Path(working_dir).resolve()
        track_file = work_path / ".tracked_papers.json"
        if not track_file.exists(): return "No papers to export."
        
        with open(track_file, "r") as f:
            tracked = json.load(f)
            
        bibtex_entries = [p.get("bibtex") for p in tracked if p.get("bibtex")]
        
        if not bibtex_entries:
            return "No BibTeX data available for the tracked papers."
            
        out_file = work_path / file_name
        with open(out_file, "w") as f:
            f.write("\n\n".join(bibtex_entries))
            
        return f"Successfully exported {len(bibtex_entries)} citations to {out_file.name}"
    except Exception as e:
        return f"Error exporting BibTeX: {e}"
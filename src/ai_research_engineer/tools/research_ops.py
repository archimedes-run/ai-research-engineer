"""
Advanced Research operations for the AI Research Engineer.
Combines Semantic Scholar for impact-filtering, findpapers for omni-search,
and ArXiv for full-text ingestion.
Implements rate-limiting, HTML-first downloading, and local paper listing.
"""

import os
import re
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import arxiv
import findpapers
from semanticscholar import SemanticScholar

logger = logging.getLogger(__name__)

# Initialize Semantic Scholar
api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
sch = SemanticScholar(api_key=api_key)



def omni_search_papers(query: str, limit: int = 10) -> str:
    """
    Search for research papers across ALL major databases 
    (arXiv, PubMed, IEEE, ACM, Scopus) simultaneously using findpapers.
    """
    logger.info(f"[Tool:omni_search] Querying all databases for: '{query}'")
    try:
        search_result = findpapers.search(query, limit_per_database=limit)
        
        results = []
        for paper in search_result.papers:
            results.append({
                "title": paper.title,
                "authors": [a.name for a in paper.authors],
                "year": paper.publication_date.year if paper.publication_date else "Unknown",
                "abstract": paper.abstract[:500] + "..." if paper.abstract else "No abstract",
                "databases": list(paper.databases),
                "urls": list(paper.urls)
            })
            
        return json.dumps(results[:limit], indent=2)
    except Exception as e:
        return f"Error in Omni-Search: {e}"


def build_citation_graph(paper_id: str, working_dir: str) -> str:
    """
    Builds a structured JSON citation graph including cross-connections
    between the target paper's references and citations (like Consensus).
    """
    import re
    import json
    from pathlib import Path
    
    logger.info(f"[Tool:build_citation_graph] Mapping ecosystem for {paper_id}")
    try:
        # 1. Auto-fix bare arXiv IDs for Semantic Scholar
        if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', paper_id):
            paper_id = f"ARXIV:{paper_id.split('v')[0]}" 

        # 2. Fetch the target paper
        p = sch.get_paper(
            paper_id, 
            fields=['title', 'year', 'references.title', 'references.paperId', 'references.year', 
                    'citations.title', 'citations.paperId', 'citations.year']
        )
        
        target_id = p.paperId
        safe_title = getattr(p, 'title', 'Unknown Title') or 'Unknown Title'
        target_year = getattr(p, 'year', 2024) or 2024
        
        nodes = {}
        edges = []
        
        # Add target node
        nodes[target_id] = {
            "id": target_id,
            "label": safe_title,
            "year": target_year,
            "group": "target"
        }
        
        # 3. Extract References (Ancestors)
        refs = getattr(p, 'references', [])
        ref_ids = []
        if refs:
            for ref in refs[:30]:  # Top 30 references
                pid = getattr(ref, 'paperId', None)
                if not pid: continue
                title = getattr(ref, 'title', 'Unknown Title') or 'Unknown Title'
                year = getattr(ref, 'year', None)
                
                nodes[pid] = {"id": pid, "label": title, "year": year, "group": "ancestor"}
                edges.append({"source": pid, "target": target_id}) # Ref -> Target
                ref_ids.append(pid)
                
        # 4. Extract Citations (Descendants)
        cites = getattr(p, 'citations', [])
        cite_ids = []
        if cites:
            for cite in cites[:20]:  # Top 20 citations
                pid = getattr(cite, 'paperId', None)
                if not pid: continue
                title = getattr(cite, 'title', 'Unknown Title') or 'Unknown Title'
                year = getattr(cite, 'year', None)
                
                nodes[pid] = {"id": pid, "label": title, "year": year, "group": "descendant"}
                edges.append({"source": target_id, "target": pid}) # Target -> Cite
                cite_ids.append(pid)
                
        # 5. FIND CROSS-CONNECTIONS! (The Consensus Magic)
        # We do ONE batch call to see if any of our 50 neighbors cite each other
        all_neighbor_ids = ref_ids + cite_ids
        if all_neighbor_ids:
            try:
                neighbors_data = sch.get_papers(all_neighbor_ids, fields=['citations.paperId'])
                for neighbor in neighbors_data:
                    if not neighbor: continue
                    n_id = neighbor.paperId
                    n_cites = getattr(neighbor, 'citations', [])
                    if n_cites:
                        for c in n_cites:
                            c_id = getattr(c, 'paperId', None)
                            # If this neighbor cites another paper in our graph, draw an edge!
                            if c_id and c_id in nodes and c_id != target_id:
                                edges.append({"source": n_id, "target": c_id})
            except Exception as batch_e:
                logger.warning(f"[Tool:build_citation_graph] Could not fetch cross-connections: {batch_e}")

        # 6. Format Final JSON
        graph_data = {
            "nodes": list(nodes.values()),
            "edges": edges
        }
        
        json_str = json.dumps(graph_data, indent=2)
        
        # Save to disk
        if working_dir:
            safe_id = paper_id.replace(':', '_').replace('/', '_')
            graph_path = Path(working_dir) / "knowledge_base" / f"citation_graph_{safe_id[:15]}.json"
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            graph_path.write_text(json_str, encoding='utf-8')
            
            # We return the JSON string directly to the LLM. It's incredibly token-dense and easy to read.
            return f"Citation graph built with cross-connections and saved to {graph_path.name}:\n\n{json_str}"
            
        return json_str
        
    except Exception as e:
        return f"Error building citation graph: {e}"


def discover_high_impact_papers(query: str, limit: int = 5, min_citations: int = 10) -> str:
    """
    Search Semantic Scholar to discover highly cited papers and extract their arXiv IDs.
    """
    logger.info(f"[Tool:discover_high_impact] Query: '{query}'")
    try:
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


def read_paper(paper_id: str, working_dir: str) -> str:
    """
    Read the full text of a locally downloaded paper in markdown. 
    Requires download_paper to be called first.
    """
    try:
        work_path = Path(working_dir).resolve()
        html_path = work_path / "literature" / f"{paper_id}.html"
        pdf_path = work_path / "literature" / f"{paper_id}.pdf"
        
        # Parse HTML if it exists
        if html_path.exists():
            html_content = html_path.read_text(encoding='utf-8')
            # Strip tags to create basic markdown-friendly text
            text = re.sub(r'<style.*?</style>', '', html_content, flags=re.DOTALL)
            text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\n\s*\n', '\n\n', text).strip()
            
            if len(text) > 40000:
                text = text[:40000] + "\n\n...[TRUNCATED DUE TO LENGTH]..."
            return text
            
        # Parse PDF if HTML doesn't exist
        elif pdf_path.exists():
            try:
                import PyPDF2
                text = []
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text.append(page.extract_text())
                        
                full_text = "\n\n".join(text)
                if len(full_text) > 40000:
                    full_text = full_text[:40000] + "\n\n...[TRUNCATED DUE TO LENGTH]..."
                return full_text
            except ImportError:
                return "Error: PyPDF2 is required to read PDFs. Please run `uv add PyPDF2` in your terminal to extract text."
                
        else:
            return f"Error: Paper {paper_id} not found locally. Call download_paper first."
            
    except Exception as e:
        return f"Error reading paper: {e}"
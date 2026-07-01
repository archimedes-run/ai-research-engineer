"""
Tools for AI Research Engineer agents.
Provides file system, web fetch, arXiv, Semantic Scholar, Code Graph, and LaTeX tools.
All file operations are read-only and enforce working_dir sandboxing.
"""

# Import Code Graph tools
from ai_research_engineer.tools.code_graph_ops import (
    build_knowledge_graph,
    get_code_blast_radius,
    get_code_context,
    query_code_structure,
    search_code_semantically,
)
from ai_research_engineer.tools.data_ops import get_schema, query_duckdb
from ai_research_engineer.tools.file_ops import (
    directory_tree,
    get_file_info,
    list_directory,
    read_file,
    read_media_file,
    search_files,
    write_file,
)

# Import LaTeX tools
from ai_research_engineer.tools.latex_ops import compile_latex_to_pdf

# Import ArXiv tools
from ai_research_engineer.tools.research_ops import (
    build_citation_graph,
    discover_high_impact_papers,
    download_paper,
    list_papers as list_arxiv_papers,
    omni_search_papers,
    read_paper,
    search_papers as arxiv_search_papers,
)

# Import Semantic Scholar tools
from ai_research_engineer.tools.semantic_scholar_ops import (
    export_bibtex,
    get_author_details,
    get_paper_citations,
    get_paper_details,
    get_paper_references,
    get_recommendations,
    list_tracked_papers,
    search_authors,
    search_papers as semantic_search_papers,
)
from ai_research_engineer.tools.web_ops import fetch_url


__all__ = [
    # Base tools
    "read_file",
    "read_media_file",
    "list_directory",
    "directory_tree",
    "search_files",
    "get_file_info",
    "fetch_url",
    "write_file",
    
    # Semantic Scholar tools
    "semantic_search_papers",
    "get_paper_details",
    "get_paper_citations",
    "get_paper_references",
    "search_authors",
    "get_author_details",
    "get_recommendations",
    "list_tracked_papers",
    "export_bibtex",
    
    # ArXiv tools
    "discover_high_impact_papers",
    "arxiv_search_papers",
    "download_paper",
    "list_arxiv_papers",
    "read_paper",
    "omni_search_papers",
    "build_citation_graph",
    
    # Code Graph tools
    "build_knowledge_graph",
    "get_code_context",
    "get_code_blast_radius",
    "query_code_structure",
    "search_code_semantically",

    # Data tools
    "query_duckdb",
    "get_schema",

    # LaTeX tools
    "compile_latex_to_pdf",
]
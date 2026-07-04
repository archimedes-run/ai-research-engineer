"""Session literature tool (S1-5).

``search_session_literature`` queries the active per-session literature index —
the first place to look before hitting the network, since it already holds every
paper surfaced this run (Semantic Scholar, OpenAlex, Papers with Code, ingested
abstracts). Registered in the Stage 1 tool registry with no external
requirements (it is a local, offline lookup).
"""

import json
import logging

from ai_research_engineer.core.lit_index import get_active_index
from ai_research_engineer.core.tool_registry import register_tool


logger = logging.getLogger(__name__)


def search_session_literature(query: str, top_k: int = 10) -> str:
    """Search papers already gathered this session by semantic similarity.

    Look here BEFORE calling network search tools — it returns papers previously
    found via Semantic Scholar / OpenAlex / Papers with Code or ingested from a
    downloaded paper, with a relevance ``score`` per hit.
    """
    index = get_active_index()
    if index is None or index.size == 0:
        return "No session literature indexed yet. Use the search tools first."
    results = index.query(query, top_k=top_k or 10)
    if not results:
        return "No matching papers in the session literature index."
    return json.dumps(results, indent=2)


register_tool("search_session_literature", search_session_literature, requires=[])

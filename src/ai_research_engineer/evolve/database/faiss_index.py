"""Re-export shim (S1-1).

``FAISSIndex`` moved to ``ai_research_engineer.core.faiss_index``. This shim is
kept for one release for backward compatibility — import from core instead.
"""

from ai_research_engineer.core.faiss_index import FAISS_AVAILABLE, FAISSIndex


__all__ = ["FAISSIndex", "FAISS_AVAILABLE"]

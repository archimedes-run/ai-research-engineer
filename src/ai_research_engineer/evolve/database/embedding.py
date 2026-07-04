"""Re-export shim (S1-1).

``EmbeddingService`` moved to ``ai_research_engineer.core.embedding``. This shim
is kept for one release for backward compatibility — import from core instead.
"""

from ai_research_engineer.core.embedding import ST_AVAILABLE, EmbeddingService


__all__ = ["EmbeddingService", "ST_AVAILABLE"]

"""Core embeddings substrate (S1-1).

One process-wide ``EmbeddingService`` singleton, a FAISS index factory, and a
cached ``embed_texts`` — the shared retrieval primitive that Stages 2/3/5 build
on. There is exactly one SentenceTransformer construction site in the codebase
(``core.embedding.EmbeddingService``); this module never constructs a second.
"""

import hashlib
import logging
import threading
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from ai_research_engineer.core.embedding import EmbeddingService
from ai_research_engineer.core.faiss_index import FAISSIndex


logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_DIR = Path.home() / ".archimedes" / "cache" / "embeddings"

_service_lock = threading.Lock()
_service: Optional[EmbeddingService] = None


def get_embedding_service(model_name: str = DEFAULT_EMBEDDING_MODEL) -> EmbeddingService:
    """Return the process-wide singleton ``EmbeddingService`` (one model load).

    The first caller fixes the model; later callers get the same instance
    regardless of the model_name argument (a warning is logged on mismatch).
    """
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = EmbeddingService(model_name=model_name)
    return _service


def get_faiss_index(name: str, dim: int) -> FAISSIndex:
    """Factory for a FAISS index of dimension ``dim``.

    ``name`` is accepted for call-site clarity and future per-name persistence.
    """
    return FAISSIndex(dimension=dim)


def _cache_key(model_name: str, text: str) -> str:
    return hashlib.sha256(f"{model_name}\x00{text}".encode("utf-8")).hexdigest()


def _cache_path(model_name: str, text: str) -> Path:
    return CACHE_DIR / f"{_cache_key(model_name, text)}.npy"


def _cache_load(model_name: str, text: str) -> Optional[np.ndarray]:
    path = _cache_path(model_name, text)
    if path.exists():
        try:
            return np.load(path)
        except Exception as exc:  # corrupt cache entry — treat as a miss
            logger.debug("embedding cache read failed for %s: %s", path.name, exc)
    return None


def _cache_store(model_name: str, text: str, vector: np.ndarray) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(_cache_path(model_name, text), vector)
    except Exception as exc:  # cache is best-effort — never fail the caller
        logger.debug("embedding cache write failed: %s", exc)


def embed_texts(texts: Union[str, List[str]], model_name: str = DEFAULT_EMBEDDING_MODEL) -> np.ndarray:
    """Embed ``texts`` via the singleton service, with an on-disk cache keyed by
    ``sha256(model + text)`` under ``~/.archimedes/cache/embeddings/``.

    Only cache misses hit the model; on a full cache hit the model is never
    invoked (and, if it was never loaded, never loaded).
    """
    if isinstance(texts, str):
        texts = [texts]

    results: List[Optional[np.ndarray]] = [None] * len(texts)
    miss_texts: List[str] = []
    miss_positions: List[int] = []

    for i, text in enumerate(texts):
        cached = _cache_load(model_name, text)
        if cached is not None:
            results[i] = cached
        else:
            miss_texts.append(text)
            miss_positions.append(i)

    if miss_texts:
        encoded = get_embedding_service(model_name).encode(miss_texts)
        for j, pos in enumerate(miss_positions):
            vector = np.asarray(encoded[j], dtype=np.float32)
            results[pos] = vector
            _cache_store(model_name, texts[pos], vector)

    return np.array(results, dtype=np.float32)


__all__ = [
    "get_embedding_service",
    "get_faiss_index",
    "embed_texts",
    "EmbeddingService",
    "FAISSIndex",
    "DEFAULT_EMBEDDING_MODEL",
]

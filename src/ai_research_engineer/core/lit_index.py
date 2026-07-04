"""Per-session literature index (S1-5).

A small FAISS index + JSONL metadata store, scoped to one run's working
directory (``<working_dir>/.data/lit_index/``). Every paper the agent sees —
from Semantic Scholar, OpenAlex, Papers with Code, or an ingested abstract —
is upserted here, so ``search_session_literature`` can answer "have we already
found something on X?" without another network round trip.

Documents are ``{id, title, abstract, source, url, year}``; ``id`` is the dedupe
key across sources (a paper found twice is indexed once). Embeddings come from
the shared core substrate (``embed_texts``), so the index dimension follows the
configured model.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ai_research_engineer.core.config import get_embeddings_model
from ai_research_engineer.core.embeddings import embed_texts
from ai_research_engineer.core.faiss_index import FAISSIndex


logger = logging.getLogger(__name__)

_DOC_FIELDS = ("id", "title", "abstract", "source", "url", "year")


class LitIndex:
    """A per-session FAISS index with a JSONL metadata sidecar."""

    def __init__(self, working_dir: str, model_name: Optional[str] = None):
        self.root = Path(working_dir).resolve() / ".data" / "lit_index"
        self.root.mkdir(parents=True, exist_ok=True)
        self.docs_path = self.root / "docs.jsonl"
        self.meta_path = self.root / "meta.json"
        self.model_name = model_name or get_embeddings_model()

        self._docs: Dict[str, dict] = {}
        self._intid_to_id: Dict[int, str] = {}
        self._next_int = 0
        self._dim: Optional[int] = None
        self._index: Optional[FAISSIndex] = None
        self._load()

    # -- persistence -------------------------------------------------------- #
    def _load(self) -> None:
        if self.meta_path.exists():
            try:
                self._dim = json.loads(self.meta_path.read_text()).get("dim")
            except Exception as exc:  # corrupt meta — rebuild lazily
                logger.debug("[lit_index] meta read failed: %s", exc)

        if self.docs_path.exists():
            for line in self.docs_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                int_id, doc = rec.get("int_id"), rec.get("doc") or {}
                doc_id = doc.get("id")
                if int_id is None or not doc_id:
                    continue
                self._docs[doc_id] = doc
                self._intid_to_id[int_id] = doc_id
                self._next_int = max(self._next_int, int_id + 1)

        # A persisted dim means a persisted FAISS index — reconstruct it (its
        # constructor loads faiss.index/faiss_meta.pkl from storage_path).
        if self._dim:
            self._index = FAISSIndex(dimension=self._dim, index_type="IP", storage_path=self.root)

    def _ensure_index(self, dim: int) -> FAISSIndex:
        if self._index is None:
            self._dim = dim
            self._index = FAISSIndex(dimension=dim, index_type="IP", storage_path=self.root)
            self.meta_path.write_text(json.dumps({"dim": dim, "model": self.model_name}))
        return self._index

    # -- helpers ------------------------------------------------------------ #
    @staticmethod
    def _normalize(doc: dict) -> dict:
        out = {k: doc.get(k) for k in _DOC_FIELDS}
        out["id"] = "" if out["id"] is None else str(out["id"])
        return out

    @staticmethod
    def _text_for(doc: dict) -> str:
        title = (doc.get("title") or "").strip()
        abstract = (doc.get("abstract") or "").strip()
        return f"{title}\n\n{abstract}".strip()

    @staticmethod
    def _vec(text: str) -> np.ndarray:
        arr = np.asarray(embed_texts(text), dtype=np.float32)
        return arr[0] if arr.ndim == 2 else arr

    # -- public API --------------------------------------------------------- #
    def upsert(self, doc: dict) -> bool:
        """Index ``doc`` ({id,title,abstract,source,url,year}).

        Returns True if newly indexed, False if skipped (duplicate id or no
        embeddable text). Dedupe is by ``id`` across all sources.
        """
        doc = self._normalize(doc)
        doc_id = doc["id"]
        if not doc_id or doc_id in self._docs:
            return False
        text = self._text_for(doc)
        if not text:
            return False

        vec = self._vec(text)
        index = self._ensure_index(int(vec.shape[0]))
        int_id = self._next_int
        self._next_int += 1
        index.add(int_id, vec)
        index.save()

        self._intid_to_id[int_id] = doc_id
        self._docs[doc_id] = doc
        with self.docs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"int_id": int_id, "doc": doc}) + "\n")
        return True

    def query(self, text: str, top_k: int = 10) -> List[dict]:
        """Return the ``top_k`` most similar indexed docs (each with a ``score``)."""
        if self._index is None or self._index.size == 0 or not (text or "").strip():
            return []
        hits = self._index.search(self._vec(text), top_k=top_k)
        results = []
        for int_id, score in hits:
            doc_id = self._intid_to_id.get(int_id)
            if doc_id and doc_id in self._docs:
                r = dict(self._docs[doc_id])
                r["score"] = round(float(score), 4)
                results.append(r)
        return results

    @property
    def size(self) -> int:
        return len(self._docs)


# --------------------------------------------------------------------------- #
# Session management: one active index per run, cached by working directory.
# --------------------------------------------------------------------------- #
_cache: Dict[str, LitIndex] = {}
_active: Optional[LitIndex] = None


def get_lit_index(working_dir: str, model_name: Optional[str] = None) -> LitIndex:
    """Return (creating+caching) the LitIndex for ``working_dir`` and make it the
    active session index (so working_dir-less callers upsert into it)."""
    global _active
    key = str(Path(working_dir).resolve())
    idx = _cache.get(key)
    if idx is None:
        idx = LitIndex(working_dir, model_name=model_name)
        _cache[key] = idx
    _active = idx
    return idx


def get_active_index() -> Optional[LitIndex]:
    return _active


def set_active_index(index: Optional[LitIndex]) -> None:
    global _active
    _active = index


def reset_session() -> None:
    """Clear the active index and cache (used by tests for isolation)."""
    global _active
    _active = None
    _cache.clear()


def record_papers(docs: List[dict], working_dir: Optional[str] = None) -> int:
    """Auto-upsert hook: upsert ``docs`` into the working_dir index (if given) or
    the active session index. Best-effort — never raises into the caller."""
    index = get_lit_index(working_dir) if working_dir else get_active_index()
    if index is None:
        return 0
    added = 0
    for doc in docs:
        try:
            if index.upsert(doc):
                added += 1
        except Exception as exc:
            logger.debug("[lit_index] upsert failed: %s", exc)
    return added

"""S1-1: core embeddings substrate — singleton, disk cache, single ST site."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from ai_research_engineer.core import embeddings


class TestEmbeddingSingleton:
    def test_singleton_identity_across_call_sites(self, monkeypatch):
        # Avoid a real model load: patch the construction to a fresh Mock.
        monkeypatch.setattr(embeddings, "_service", None)
        monkeypatch.setattr(embeddings, "EmbeddingService", lambda **kwargs: MagicMock(name="svc"))

        # Two independent "call sites".
        def site_a():
            return embeddings.get_embedding_service()

        def site_b():
            return embeddings.get_embedding_service()

        assert site_a() is site_b(), "get_embedding_service must return one process-wide instance"


class TestEmbeddingDiskCache:
    def test_second_embed_hits_disk_cache_no_encode(self, tmp_path, monkeypatch):
        monkeypatch.setattr(embeddings, "CACHE_DIR", tmp_path / "emb")

        fake_service = MagicMock()
        fake_service.encode.return_value = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        monkeypatch.setattr(embeddings, "get_embedding_service", lambda *a, **k: fake_service)

        v1 = embeddings.embed_texts(["hyperparameter tuning"])
        assert fake_service.encode.call_count == 1, "first embed must hit the model (cache miss)"

        v2 = embeddings.embed_texts(["hyperparameter tuning"])
        assert fake_service.encode.call_count == 1, "second embed of same text must NOT call encode (cache hit)"

        assert np.allclose(v1, v2)
        assert any((tmp_path / "emb").glob("*.npy")), "cache entry should be persisted to disk"

    def test_cache_key_is_sha256_of_model_plus_text(self, monkeypatch):
        k_model = embeddings._cache_key("model-a", "text")
        k_model2 = embeddings._cache_key("model-b", "text")
        k_text = embeddings._cache_key("model-a", "other")
        assert k_model != k_model2, "different model -> different cache key"
        assert k_model != k_text, "different text -> different cache key"
        assert k_model == hashlib.sha256(b"model-a\x00text").hexdigest()


class TestSingleSentenceTransformerSite:
    def test_exactly_one_construction_site_under_src(self):
        src = Path(__file__).resolve().parents[2] / "src"
        hits = []
        for py in src.rglob("*.py"):
            for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                if "SentenceTransformer(" in line:
                    hits.append(f"{py.relative_to(src)}:{lineno}")
        assert len(hits) == 1, f"expected exactly one SentenceTransformer() site, found: {hits}"
        assert "core/embedding.py" in hits[0], f"the one site must be in core: {hits}"

"""
Unit tests for Embeddings module.
Verifies deterministic mock embedder, dimension consistency, L2 normalization, and batch generator.
"""

import math
import pytest
from rag.embeddings.embedder import DeterministicMockEmbedder
from rag.embeddings.batch_generator import BatchEmbeddingGenerator
from rag.embeddings.model_registry import EmbeddingModelRegistry
from rag.chunking.metadata import DocumentChunk, ChunkMetadata


def test_deterministic_mock_embedder_dimension_and_norm():
    embedder = DeterministicMockEmbedder(dimension=384)
    assert embedder.dimension == 384

    texts = [
        "The transformer architecture replaces recurrence with attention.",
        "Convolutional networks process spatial features.",
    ]
    embeddings = embedder.embed_documents(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384

    # Check L2 normalization
    norm = math.sqrt(sum(x * x for x in embeddings[0]))
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_deterministic_mock_embedder_similarity():
    embedder = DeterministicMockEmbedder(dimension=384)
    q_vec = embedder.embed_query("transformer self attention mechanism")
    doc1_vec = embedder.embed_query("We introduce the transformer self attention architecture for translation")
    doc2_vec = embedder.embed_query("Cooking recipes for Italian tomato pasta with fresh basil")

    # Cosine dot product
    sim1 = sum(q * d for q, d in zip(q_vec, doc1_vec))
    sim2 = sum(q * d for q, d in zip(q_vec, doc2_vec))

    assert sim1 > sim2, "Semantic document should have higher similarity than unrelated cooking recipe"


def test_batch_embedding_generator(mock_embedder):
    generator = BatchEmbeddingGenerator(mock_embedder, batch_size=2)
    chunks = [
        DocumentChunk(
            text=f"Sample text chunk number {i}",
            metadata=ChunkMetadata(
                chunk_id=f"p1_c{i:04d}_p1-1",
                paper_id="p1",
                document_id="d1",
                page_start=1,
                page_end=1,
                section="Intro",
                chunk_index=i, owner_id="test_user_fixture")
        )
        for i in range(5)
    ]
    vectors = generator.embed_chunks(chunks)
    assert len(vectors) == 5
    for vec in vectors:
        assert len(vec) == 384


def test_embedding_model_registry():
    mock_emb = EmbeddingModelRegistry.get_embedder(provider="mock", dimension=256)
    assert isinstance(mock_emb, DeterministicMockEmbedder)
    assert mock_emb.dimension == 256


def test_fastembedder_uses_in_process_inference_and_hash_cache(tmp_path, monkeypatch):
    from rag.config.settings import settings
    from rag.embeddings.cache import SQLiteEmbeddingCache
    from rag.embeddings.embedder import FastEmbedder

    monkeypatch.setattr(settings, "embedding_batch_size", 2)
    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "embeddings.sqlite3"))

    class FakeVector:
        def tolist(self):
            return [0.5] * 384

    class FakeModel:
        def __init__(self):
            self.calls = []

        def embed(self, texts, **kwargs):
            self.calls.append((list(texts), kwargs))
            return iter(FakeVector() for _ in texts)

    model = FakeModel()
    monkeypatch.setattr(embedder, "_get_model", lambda: model)
    texts = ["first passage", "second passage", "first passage"]

    vectors = embedder.embed_documents(texts)
    assert len(vectors) == 3
    assert all(len(vector) == 384 for vector in vectors)
    assert len(model.calls) == 1
    assert model.calls[0][1] == {"batch_size": 2, "parallel": None}
    assert len(model.calls[0][0]) == 2  # duplicate input is encoded once

    cached_vectors = embedder.embed_documents(texts)
    assert cached_vectors == vectors
    assert len(model.calls) == 1


def test_gemini_embedder_batches_documents_and_uses_query_task():
    from types import SimpleNamespace
    from rag.embeddings.embedder import GeminiEmbedder

    class ModelAPI:
        calls = []
        def embed_content(self, **kwargs):
            self.calls.append(kwargs)
            contents = kwargs["contents"]
            if isinstance(contents, str):
                contents = [contents]
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.25] * 768) for _ in contents])

    models = ModelAPI()
    embedder = GeminiEmbedder(api_key="test-key", model="gemini-embedding-001", client=SimpleNamespace(models=models))
    vectors = embedder.embed_documents(["a", "b"])
    query = embedder.embed_query("question")
    assert len(vectors) == 2 and len(vectors[0]) == 768
    assert len(query) == 768
    assert models.calls[0]["model"] == "gemini-embedding-001"
    assert models.calls[0]["contents"] == ["a", "b"]
    assert models.calls[1]["contents"] == "question"


def test_gemini_embedder_fails_clearly_without_key(monkeypatch):
    from rag.config.settings import settings
    from rag.embeddings.embedder import GeminiEmbedder

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(ValueError, match="Set GEMINI_API_KEY"):
        GeminiEmbedder().embed_documents(["source text"])


def test_gemini_embedding_rate_limit_error_is_actionable_and_redacts_key():
    from types import SimpleNamespace
    from rag.embeddings.embedder import GeminiEmbedder

    class GeminiHttpError(Exception):
        code = 429
        message = "Requests per minute quota exceeded"

    class RateLimitedModels:
        def embed_content(self, **kwargs):
            raise GeminiHttpError("quota exceeded")

    embedder = GeminiEmbedder(
        api_key="never-print-this-key", model="gemini-embedding-001",
        client=SimpleNamespace(models=RateLimitedModels()),
    )
    with pytest.raises(RuntimeError, match="HTTP 429.*quota.*retry") as raised:
        embedder.embed_documents(["evidence"])
    assert "never-print-this-key" not in str(raised.value)

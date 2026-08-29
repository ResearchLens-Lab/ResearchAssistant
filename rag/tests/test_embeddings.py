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
                chunk_index=i,
            )
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

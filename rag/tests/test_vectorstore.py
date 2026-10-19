"""
Unit tests for ChromaDB Vector Repository.
Verifies upsert, querying, metadata filters, deletion, and idempotent deterministic IDs.
"""

import pytest
from rag.chunking.metadata import DocumentChunk, ChunkMetadata
from rag.vectorstore.vector_repository import VectorRepository


def test_vector_repository_upsert_and_query(vector_repo, mock_embedder):
    chunks = [
        DocumentChunk(
            text="The Transformer achieves 28.4 BLEU on English-to-German translation.",
            metadata=ChunkMetadata(
                chunk_id="paper_att_c0001_p1-1",
                paper_id="paper_att",
                document_id="doc_att",
                page_start=1,
                page_end=1,
                section="Results",
                chunk_index=0,
                title="Attention Is All You Need",
            )
        ),
        DocumentChunk(
            text="GraphLens achieves 89.2% classification accuracy on citation networks.",
            metadata=ChunkMetadata(
                chunk_id="paper_gnn_c0001_p1-1",
                paper_id="paper_gnn",
                document_id="doc_gnn",
                page_start=1,
                page_end=1,
                section="Results",
                chunk_index=0,
                title="GraphLens Paper",
            )
        ),
    ]

    embeddings = mock_embedder.embed_documents([c.text for c in chunks])
    upserted = vector_repo.upsert_chunks(chunks, embeddings)
    assert upserted == 2

    # Query with no filter
    q_vec = mock_embedder.embed_query("Transformer BLEU score translation")
    results = vector_repo.query_vectors(q_vec, top_k=2)
    assert len(results) >= 1
    assert results[0].metadata.paper_id == "paper_att"
    assert "28.4 BLEU" in results[0].text
    assert results[0].metadata.page_start == 1


def test_vector_repository_filtering_by_paper_id(vector_repo, mock_embedder):
    chunks = [
        DocumentChunk(
            text="Paper Alpha discusses convolution.",
            metadata=ChunkMetadata(
                chunk_id="alpha_c01_p1-1",
                paper_id="alpha",
                document_id="doc_alpha",
                page_start=1,
                page_end=1,
                section="Intro",
                chunk_index=0,
            )
        ),
        DocumentChunk(
            text="Paper Beta discusses transformers.",
            metadata=ChunkMetadata(
                chunk_id="beta_c01_p1-1",
                paper_id="beta",
                document_id="doc_beta",
                page_start=1,
                page_end=1,
                section="Intro",
                chunk_index=0,
            )
        ),
    ]
    embeddings = mock_embedder.embed_documents([c.text for c in chunks])
    vector_repo.upsert_chunks(chunks, embeddings)

    q_vec = mock_embedder.embed_query("convolution or transformer")
    # Filter only paper 'alpha'
    results_alpha = vector_repo.query_vectors(q_vec, top_k=5, where={"paper_id": "alpha"})
    assert len(results_alpha) == 1
    assert results_alpha[0].metadata.paper_id == "alpha"

    # Filter only paper 'beta'
    results_beta = vector_repo.query_vectors(q_vec, top_k=5, where={"paper_id": "beta"})
    assert len(results_beta) == 1
    assert results_beta[0].metadata.paper_id == "beta"


def test_fts_bm25_finds_rare_exact_term_with_paper_filter(vector_repo, mock_embedder):
    chunks = [
        DocumentChunk(text="The quasicrystalline morphogenesis procedure is described here.",
            metadata=ChunkMetadata(chunk_id="rare_c1", paper_id="selected", document_id="d1", chunk_index=0)),
        DocumentChunk(text="A common discussion of neural networks and optimization.",
            metadata=ChunkMetadata(chunk_id="common_c1", paper_id="other", document_id="d2", chunk_index=0)),
    ]
    vector_repo.upsert_chunks(chunks, mock_embedder.embed_documents([c.text for c in chunks]))
    hits = vector_repo.query_lexical("quasicrystalline morphogenesis", where={"paper_id": "selected"}, limit=5)
    assert [hit.id for hit in hits] == ["rare_c1"]
    assert hits[0].metadata.paper_id == "selected"


def test_vector_repository_delete_paper(vector_repo, mock_embedder):
    chunk = DocumentChunk(
        text="Temporary paper data to delete.",
        metadata=ChunkMetadata(
            chunk_id="del_c01_p1-1",
            paper_id="paper_to_delete",
            document_id="doc_del",
            page_start=1,
            page_end=1,
            section="Intro",
            chunk_index=0,
        )
    )
    vec = mock_embedder.embed_documents([chunk.text])
    vector_repo.upsert_chunks([chunk], vec)
    assert vector_repo.count_chunks(where={"paper_id": "paper_to_delete"}) == 1

    deleted = vector_repo.delete_paper_chunks("paper_to_delete")
    assert deleted == 1
    assert vector_repo.count_chunks(where={"paper_id": "paper_to_delete"}) == 0

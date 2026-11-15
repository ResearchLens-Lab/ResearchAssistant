"""
Unit tests for Retrieval, Filters, Ranking, and Reranking.
"""

import pytest
from rag.retrieval.query import QueryRequest, QueryFilters, RetrievedSource
from rag.retrieval.filters import FilterBuilder
from rag.retrieval.ranking import ResultRanker
from rag.retrieval.reranker import IdentityReranker
from rag.retrieval.retriever import ResearchRetriever
from rag.chunking.metadata import DocumentChunk, ChunkMetadata


def test_filter_builder():
    # Single paper with owner_id
    f1 = FilterBuilder.build_where_filter(owner_id="u1", paper_ids=["p1"])
    assert "$and" in f1
    assert {"owner_id": "u1"} in f1["$and"]
    assert {"paper_id": "p1"} in f1["$and"]

    # Multiple papers with owner_id
    f2 = FilterBuilder.build_where_filter(owner_id="u1", paper_ids=["p1", "p2"])
    assert "$and" in f2
    assert {"owner_id": "u1"} in f2["$and"]
    assert {"paper_id": {"$in": ["p1", "p2"]}} in f2["$and"]

    # Section filter + paper with owner_id
    filters = QueryFilters(sections=["Methodology"])
    f3 = FilterBuilder.build_where_filter(owner_id="u1", paper_ids=["p1"], filters=filters)
    assert "$and" in f3
    assert {"owner_id": "u1"} in f3["$and"]
    assert {"paper_id": "p1"} in f3["$and"]
    assert {"section": "Methodology"} in f3["$and"]


def test_identity_reranker():
    reranker = IdentityReranker()
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c1",
            paper_id="p1",
            document_id="d1",
            page_start=1,
            page_end=1,
            text="Text 1",
            score=0.9,
        ),
        RetrievedSource(
            source_id="S2",
            chunk_id="c2",
            paper_id="p1",
            document_id="d1",
            page_start=2,
            page_end=2,
            text="Text 2",
            score=0.8,
        ),
    ]
    reranked = reranker.rerank(query="test", sources=sources, top_k=1)
    assert len(reranked) == 1
    assert reranked[0].chunk_id == "c1"


def test_research_retriever_end_to_end(vector_repo, mock_embedder):
    chunks = [
        DocumentChunk(
            text="We evaluate Scaled Dot-Product Attention: softmax(QK^T/sqrt(d_k))V in Section 3.",
            metadata=ChunkMetadata(
                chunk_id="att_01",
                paper_id="p_att",
                document_id="d_att",
                page_start=3,
                page_end=3,
                section="Methodology",
                chunk_index=1, owner_id="test_user_fixture")
        )
    ]
    embeddings = mock_embedder.embed_documents([c.text for c in chunks])
    vector_repo.upsert_chunks(chunks, embeddings)

    retriever = ResearchRetriever(embedder=mock_embedder, vector_repo=vector_repo)
    req = QueryRequest(
        question="How is scaled dot product attention computed in methodology?",
        paper_ids=["p_att"],
        top_k=3,
    )
    sources = retriever.retrieve(req, owner_id="test_user_fixture")
    assert len(sources) == 1
    assert sources[0].source_id == "S1"
    assert sources[0].page_start == 3
    assert sources[0].section == "Methodology"
    assert "Scaled Dot-Product Attention" in sources[0].text

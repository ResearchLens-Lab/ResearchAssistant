"""
Targeted tests for Local-First RAG operation without paid LLM/Embedding APIs.
Verifies:
1. Complete retrieval pipeline operates offline with no Gemini/OpenAI/Claude API keys.
2. Honest extractive responses with verbatim citations [S1], physical pages, and document titles.
3. Explicit honest abstention when evidence is insufficient.
4. Zero network or LLM API calls are made in local mode.
5. Hybrid retrieval (BM25 + Dense) functions correctly without external dependencies.
"""

import pytest
import socket
from unittest.mock import patch

from rag.config.settings import settings
from rag.retrieval.query import QueryRequest
from rag.retrieval.retriever import ResearchRetriever
from rag.context.context_builder import ContextBuilder
from rag.pipelines.query_pipeline import QueryPipeline
from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.chunking.chunker import DocumentChunker


SAMPLE_LOCAL_DOC = """
Neural Architecture Search for High-Performance Mobile Devices

Abstract
We present MobileNAS, an efficient neural architecture search approach optimized for mobile edge devices.

1. Introduction
Deploying deep learning on battery-constrained hardware requires balancing accuracy and latency.

2. Hardware Benchmarks
MobileNAS was evaluated on the Snapdragon 888 and Apple A15 Bionic chipsets.
On Snapdragon 888, the model reached 78.6% ImageNet Top-1 accuracy with 14.2 ms inference latency.
On Apple A15 Bionic, latency was measured at 11.8 ms at batch size 1.

3. Energy Consumption
Peak power draw remained strictly under 2.4 Watts during continuous inference.
Thermal throttling was not observed during 60-minute stress testing.

4. Conclusion
MobileNAS establishes that automated neural architecture search can produce production-ready edge models.
"""


def test_local_retrieval_without_api_keys(full_rag_pipeline, monkeypatch):
    """
    Verify complete local RAG flow when all external LLM API keys are absent.
    No network requests or LLM calls must be attempted.
    """
    ingest_p, _ = full_rag_pipeline

    # Enforce strict local configuration with empty API credentials
    monkeypatch.setattr(settings, "rag_mode", "local")
    monkeypatch.setattr(settings, "llm_enabled", False)
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")

    # Ingest document using local pipeline
    ingest_res = ingest_p.ingest_text(
        content=SAMPLE_LOCAL_DOC,
        paper_id="paper_mobilenas_2024",
        metadata={
            "title": "MobileNAS Research Paper",
            "filename": "mobilenas_2024.pdf",
            "year": 2024,
        },
    )
    assert ingest_res.success is True
    assert ingest_res.chunk_count > 0

    # Build local query pipeline
    retriever = ResearchRetriever(
        embedder=ingest_p.embedder,
        vector_repo=ingest_p.vector_repo,
    )
    pipeline = QueryPipeline(
        retriever=retriever,
        context_builder=ContextBuilder(),
    )

    # Disallow all external network sockets
    def forbidden_socket_connect(*args, **kwargs):
        raise AssertionError("Network connection attempted during local-first retrieval!")

    with patch.object(socket.socket, "connect", side_effect=forbidden_socket_connect):
        result = pipeline.answer_question(
            question="What is the inference latency and Top-1 accuracy on Snapdragon 888?",
            user_id="test_user_fixture",
            paper_ids=["paper_mobilenas_2024"],
            top_k=3,
        )

    # Verify extractive source-grounded response
    assert result.answer != ""
    assert "78.6%" in result.answer or "14.2 ms" in result.answer
    assert result.metadata["model_calls"] == 0
    assert result.metadata["answer_mode"] in ("evidence_only", "evidence_fallback")
    assert len(result.sources) > 0

    # Verify exact citation metadata
    top_source = result.sources[0]
    assert top_source.paper_id == "paper_mobilenas_2024"
    assert top_source.source_id.startswith("S")
    assert top_source.page_display or top_source.locator


def test_honest_abstention_on_unanswerable_query(full_rag_pipeline, monkeypatch):
    """
    Verify honest abstention when evidence is insufficient.
    System must not fabricate a fluent answer.
    """
    ingest_p, _ = full_rag_pipeline

    monkeypatch.setattr(settings, "rag_mode", "local")
    monkeypatch.setattr(settings, "llm_enabled", False)
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    ingest_p.ingest_text(
        content=SAMPLE_LOCAL_DOC,
        paper_id="paper_mobilenas_2024",
        metadata={"title": "MobileNAS"},
    )

    retriever = ResearchRetriever(
        embedder=ingest_p.embedder,
        vector_repo=ingest_p.vector_repo,
    )
    pipeline = QueryPipeline(
        retriever=retriever,
        context_builder=ContextBuilder(),
    )

    # Ask for non-existent fact
    result = pipeline.answer_question(
        question="What was the recipe for purple potato soup in Ancient Rome during the Bronze Age?",
        user_id="test_user_fixture",
        paper_ids=["paper_mobilenas_2024"],
        top_k=3,
    )

    assert result.metadata["model_calls"] == 0
    assert "insufficient evidence" in result.answer.lower()
    assert result.metadata["answer_mode"] == "evidence_only"


def test_hybrid_retrieval_combines_dense_and_keyword(full_rag_pipeline, monkeypatch):
    """
    Verify that hybrid retrieval blends BM25 keyword matching and dense vector search.
    """
    ingest_p, _ = full_rag_pipeline

    monkeypatch.setattr(settings, "retrieval_mode", "hybrid")
    monkeypatch.setattr(settings, "rag_mode", "local")
    monkeypatch.setattr(settings, "llm_enabled", False)

    ingest_p.ingest_text(
        content=SAMPLE_LOCAL_DOC,
        paper_id="paper_mobilenas_2024",
        metadata={"title": "MobileNAS"},
    )

    retriever = ResearchRetriever(
        embedder=ingest_p.embedder,
        vector_repo=ingest_p.vector_repo,
    )

    # Keyword specific term query
    req = QueryRequest(
        question="Snapdragon 888 14.2 ms latency",
        paper_ids=["paper_mobilenas_2024"],
        top_k=2,
    )
    retrieved = retriever.retrieve(req, owner_id="test_user_fixture")

    assert len(retrieved) > 0
    assert any("14.2 ms" in r.text or "Snapdragon" in r.text for r in retrieved)
    assert all(r.score > 0 for r in retrieved)


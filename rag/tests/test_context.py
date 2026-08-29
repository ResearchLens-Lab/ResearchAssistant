"""
Unit tests for Context building, deduplication, and token limits.
"""

import pytest
from rag.retrieval.query import RetrievedSource
from rag.context.context_selector import ContextSelector
from rag.context.context_limits import ContextLimitManager
from rag.context.context_builder import ContextBuilder


def test_context_selector_deduplication():
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="chunk_01",
            paper_id="p1",
            document_id="d1",
            page_start=1,
            page_end=1,
            text="Identical snippet of research paper.",
        ),
        RetrievedSource(
            source_id="S2",
            chunk_id="chunk_01",  # duplicate ID
            paper_id="p1",
            document_id="d1",
            page_start=1,
            page_end=1,
            text="Identical snippet of research paper.",
        ),
        RetrievedSource(
            source_id="S3",
            chunk_id="chunk_02",
            paper_id="p1",
            document_id="d1",
            page_start=2,
            page_end=2,
            text="Completely different snippet.",
        ),
    ]
    deduped = ContextSelector.deduplicate(sources)
    assert len(deduped) == 2
    assert [s.chunk_id for s in deduped] == ["chunk_01", "chunk_02"]


def test_context_selector_balance_multi_paper():
    sources = [
        RetrievedSource(source_id=f"S{i}", chunk_id=f"c{i}", paper_id="p1", document_id="d1", page_start=1, page_end=1, text=f"Text {i}")
        for i in range(10)
    ]
    sources.append(
        RetrievedSource(source_id="S11", chunk_id="c11", paper_id="p2", document_id="d2", page_start=1, page_end=1, text="Text Paper 2")
    )
    balanced = ContextSelector.balance_multi_paper(sources, target_paper_ids=["p1", "p2"], max_sources_per_paper=3)
    p1_count = sum(1 for s in balanced if s.paper_id == "p1")
    p2_count = sum(1 for s in balanced if s.paper_id == "p2")
    assert p1_count == 3
    assert p2_count == 1


def test_context_builder_formatting():
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c_01",
            paper_id="paper_transformer",
            document_id="doc_01",
            page_start=2,
            page_end=3,
            section="Methodology",
            text="Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V",
            title="Attention Is All You Need",
        )
    ]
    builder = ContextBuilder()
    ctx = builder.build_context(sources)
    assert ctx.total_sources == 1
    assert "[S1]" in ctx.formatted_context
    assert "Pages 2-3" in ctx.formatted_context
    assert "Section: Methodology" in ctx.formatted_context
    assert "softmax(QK^T / sqrt(d_k))V" in ctx.formatted_context

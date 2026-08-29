"""
Tests for Multi-Paper Querying and Comparison.
"""

import pytest
from rag.tests.conftest import SAMPLE_PAPER_TEXT, SAMPLE_PAPER_2_TEXT


def test_multi_paper_querying_and_comparison(full_rag_pipeline):
    ingest_p, query_p = full_rag_pipeline

    # Ingest Paper 1
    res1 = ingest_p.ingest_text(
        content=SAMPLE_PAPER_TEXT,
        paper_id="paper_transformer_p1",
        metadata={"title": "Attention Is All You Need"},
    )
    assert res1.success is True

    # Ingest Paper 2
    res2 = ingest_p.ingest_text(
        content=SAMPLE_PAPER_2_TEXT,
        paper_id="paper_graphlens_p2",
        metadata={"title": "Graph Neural Networks for Research Paper Representation"},
    )
    assert res2.success is True

    # Comparative Query
    comp_result = query_p.compare_papers(
        paper_ids=["paper_transformer_p1", "paper_graphlens_p2"],
        focus_area="How do the architectures and representations differ between transformers and graph neural networks?",
    )

    assert comp_result.answer is not None
    assert "Comparison" in comp_result.answer or "Differences" in comp_result.answer
    assert len(comp_result.sources) >= 2

    # Verify both papers are cited and present in sources
    found_papers = {s.paper_id for s in comp_result.sources}
    assert "paper_transformer_p1" in found_papers
    assert "paper_graphlens_p2" in found_papers

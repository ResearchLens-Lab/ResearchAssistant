"""
Tests for Grounded Paper Summarization.
"""

import pytest
from rag.tests.conftest import SAMPLE_PAPER_TEXT


def test_summarize_paper(full_rag_pipeline):
    ingest_p, query_p = full_rag_pipeline

    # 1. Ingest paper
    ingest_res = ingest_p.ingest_text(
        content=SAMPLE_PAPER_TEXT,
        paper_id="paper_att_summary",
        metadata={"title": "Attention Is All You Need"},
    )
    assert ingest_res.success is True
    assert ingest_res.chunk_count > 0

    # 2. Summarize paper
    summary_result = query_p.summarize_paper("paper_att_summary", user_id="test_user_fixture")
    assert summary_result.answer is not None
    assert "Overview" in summary_result.answer
    assert "Methodology" in summary_result.answer
    assert "Results" in summary_result.answer
    assert len(summary_result.sources) > 0
    assert summary_result.sources[0].paper_id == "paper_att_summary"

"""
Unit tests for Citation Provenance, Source Tracking, and Formatter.
"""

import pytest
from rag.retrieval.query import RetrievedSource
from rag.citations.source_tracker import SourceTracker
from rag.citations.citation_mapper import CitationMapper, SourceCitation
from rag.citations.citation_formatter import RAGResult


def test_source_tracker_registration():
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="chunk_123",
            paper_id="paper_abc",
            document_id="doc_xyz",
            page_start=4,
            page_end=5,
            section="Methodology",
            text="Evidence text snippet here.",
            score=0.92,
            title="Research Paper Title",
        )
    ]
    tracker = SourceTracker(sources)
    s = tracker.get_by_source_id("S1")
    assert s is not None
    assert s.paper_id == "paper_abc"
    assert s.page_start == 4
    assert s.page_end == 5
    assert s.section == "Methodology"


def test_citation_mapper_prevents_hallucinated_citations():
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c_01",
            paper_id="paper_real",
            document_id="doc_real",
            page_start=2,
            page_end=2,
            section="Results",
            text="Real retrieved text.",
        )
    ]
    tracker = SourceTracker(sources)
    mapper = CitationMapper(tracker)

    # LLM hallucinated S99 which does not exist in retrieved sources
    citations = mapper.map_citations(cited_source_ids=["S99", "S1"])

    assert len(citations) == 1
    assert citations[0].source_id == "S1"
    assert citations[0].paper_id == "paper_real"
    assert citations[0].chunk_id == "c_01"


def test_rag_result_api_and_markdown_serialization():
    cit = SourceCitation(
        source_id="S1",
        paper_id="paper_101",
        document_id="doc_101",
        chunk_id="c_001",
        page_start=3,
        page_end=4,
        section="Methodology",
        text="The attention weight is computed dynamically.",
        score=0.88,
        title="Attention Mechanism",
    )
    result = RAGResult(
        answer="The attention weight is computed dynamically [S1].",
        sources=[cit],
        paper_ids=["paper_101"],
    )

    api_dict = result.to_api_dict()
    assert api_dict["answer"] == result.answer
    assert len(api_dict["sources"]) == 1
    assert api_dict["sources"][0]["page"] == 3
    assert api_dict["sources"][0]["section"] == "Methodology"

    md = result.to_markdown()
    assert "### Supporting Citations & Evidence:" in md
    assert "[S1] Paper paper_101" in md
    assert "Pages 3-4" in md

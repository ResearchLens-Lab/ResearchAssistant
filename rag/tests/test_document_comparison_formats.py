"""Document-level deterministic comparison output coverage."""

import time

import pytest

from rag.independent.answer_composer import StructuredAnswerComposer
from rag.independent.engine import IndependentResearchEngine
from rag.independent.models import EvidenceDecision, QueryAnalysis, QuestionIntent
from rag.retrieval.query import RetrievedSource


def _source(source_id, document_id, filename, text):
    return RetrievedSource(
        source_id=source_id,
        chunk_id=f"chunk-{source_id}",
        paper_id="project-1",
        document_id=document_id,
        page_start=2,
        page_end=2,
        text=text,
        filename=filename,
        title=filename,
    )


def _analysis(output_format):
    return QueryAnalysis(
        intent=QuestionIntent.COMPARISON,
        normalized_question="Compare reported methods",
        search_query="methods",
        important_terms=["method", "retrieval"],
        document_filters={
            "document_ids": ["doc-a", "doc-b", "doc-c"],
            "document_labels": {
                "doc-a": "Project · alpha.pdf",
                "doc-b": "Project · beta.pdf",
                "doc-c": "Another project · gamma.pdf",
            },
            "output_format": output_format,
        },
    )


@pytest.mark.parametrize("output_format", ["table", "side_by_side", "detailed_report"])
def test_comparison_keeps_each_selected_document_in_scope(output_format):
    sources = [
        _source("S1", "doc-a", "alpha.pdf", "The method uses lexical retrieval for evidence ranking."),
        _source("S2", "doc-b", "beta.pdf", "The method uses vector retrieval for evidence ranking."),
    ]

    answer = StructuredAnswerComposer().compose(_analysis(output_format), sources, [])

    assert "alpha.pdf" in answer
    assert "beta.pdf" in answer
    assert "gamma.pdf" in answer
    assert "[S1]" in answer and "[S2]" in answer
    assert "No relevant passage" in answer


def test_comparison_table_uses_documents_as_independent_columns():
    sources = [
        _source("S1", "doc-a", "alpha.pdf", "The method uses lexical retrieval for evidence ranking."),
        _source("S2", "doc-b", "beta.pdf", "The method uses vector retrieval for evidence ranking."),
    ]

    answer = StructuredAnswerComposer().compose(_analysis("table"), sources, [])

    assert "| Comparison dimension | Project · alpha.pdf | Project · beta.pdf | Another project · gamma.pdf |" in answer
    assert "| Evidence for the requested focus |" in answer


def test_independent_result_reports_requested_format_and_document_scope():
    analysis = _analysis("detailed_report")

    result = IndependentResearchEngine._result(
        "Report", analysis, [], [], {}, EvidenceDecision(status="SUPPORTED"), [], time.perf_counter()
    )

    assert result.metadata["output_format"] == "detailed_report"
    assert result.metadata["selected_document_ids"] == ["doc-a", "doc-b", "doc-c"]


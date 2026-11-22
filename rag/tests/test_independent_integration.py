"""
Automated validation suite for Phase 1-7 Evidence-First Deterministic Research Engine.
Tests:
1. Default independent engine execution
2. No hidden LLM calls (zero model calls)
3. Academic citation resolution contract ([Author et al., Year, p. X])
4. 8-section structured summary with honest abstention
5. Markdown table synthesis
6. Honest abstention on unsupported claims
7. Optional Local AI opt-in branching
8. SEC-001 multi-tenant owner isolation
"""

import pytest
from rag.config.settings import settings
from rag.independent.engine import IndependentResearchEngine
from rag.independent.models import QuestionIntent
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.answer_composer import StructuredAnswerComposer
from rag.citations.citation_mapper import format_citation_label, CitationMapper, SourceCitation
from rag.citations.source_tracker import SourceTracker
from rag.retrieval.query import RetrievedSource
from rag.pipelines.query_pipeline import QueryPipeline


def test_01_default_independent_engine_configuration():
    """Verify that settings default to independent deterministic engine with zero LLM calls."""
    assert settings.rag_engine_mode == "independent"
    assert settings.rag_answer_mode == "INDEPENDENT"
    assert settings.llm_enabled is False


def test_02_no_hidden_llm_calls():
    """Verify that independent engine executes end-to-end without any model or network calls."""
    engine = IndependentResearchEngine()
    dummy_source = RetrievedSource(
        source_id="S1",
        chunk_id="chk_001",
        paper_id="paper_abc",
        document_id="doc_xyz",
        page_start=5,
        page_end=5,
        section="Methodology",
        text="The algorithm executes in linear time by processing each token sequentially.",
        score=0.95,
        title="Linear Processing",
    )
    engine.retriever.retrieve = lambda *args, **kwargs: ([dummy_source], {"S1": ["test"]})

    result = engine.answer(
        question="what is an algorithm",
        paper_ids=["paper_abc"],
        user_id="user_123",
    )

    assert result.metadata["model_calls"] == 0
    assert result.metadata["pretrained_embeddings_used"] is False
    assert result.metadata["external_inference_used"] is False
    assert result.metadata["answer_mode"] == "independent_documents_only"
    assert result.metadata["generation_provider"] == "none"


def test_03_academic_citation_label_formatting():
    """Verify standard academic citation label formatting: [Author et al., Year, p. X]."""
    # 1. Two authors
    label1 = format_citation_label(
        authors=["Thomas Cormen", "Charles Leiserson"],
        year=2022,
        page_start=38,
        page_end=38,
        title="Algorithms",
    )
    assert label1 == "[Cormen & Leiserson, 2022, p. 38]"

    # 2. Three or more authors
    label2 = format_citation_label(
        authors=["Gorav Vance", "Alex Chen", "David Miller"],
        year=2025,
        page_start=12,
        page_end=15,
        title="ResearchLens",
    )
    assert label2 == "[Vance et al., 2025, pp. 12-15]"

    # 3. Single author, no year
    label3 = format_citation_label(
        authors=["Smith"],
        year=None,
        page_start=1,
        page_end=1,
    )
    assert label3 == "[Smith, p. 1]"

    # 4. No authors, title fallback
    label4 = format_citation_label(
        authors=None,
        year=2024,
        page_start=4,
        page_end=4,
        title="Computer Science",
    )
    assert label4 == '["Computer Science", 2024, p. 4]'


def test_04_citation_mapper_metadata_contract():
    """Verify that CitationMapper populates all contract fields for API consumers."""
    source = RetrievedSource(
        source_id="S1",
        chunk_id="chunk_test_99",
        paper_id="paper_1",
        document_id="doc_1",
        page_start=10,
        page_end=11,
        section="Results",
        text="The model achieved 98.4% precision on benchmark datasets.",
        score=0.91,
        title="Benchmark Analysis",
        filename="benchmark.pdf",
    )
    tracker = SourceTracker([source])
    paper_metadata = {
        "paper_1": {
            "title": "Benchmark Analysis",
            "authors": ["Vance", "Chen"],
            "year": 2025,
        }
    }
    mapper = CitationMapper(tracker, paper_metadata=paper_metadata)
    citations = mapper.map_citations(["S1"])

    assert len(citations) == 1
    c = citations[0]
    assert c.source_id == "S1"
    assert c.paper_id == "paper_1"
    assert c.citation_label == "[Vance & Chen, 2025, pp. 10-11]"
    assert c.author_metadata == ["Vance", "Chen"]
    assert c.paper_title == "Benchmark Analysis"
    assert c.publication_year == 2025
    assert c.page_start == 10
    assert c.page_end == 11
    assert c.original_page_number == 10
    assert c.section_label == "Results"
    assert c.evidence_excerpt == source.text


def test_05_markdown_table_synthesis():
    """Verify that table synthesis produces markdown tables without empty Answer:/Explanation: labels."""
    composer = StructuredAnswerComposer()
    analysis = QuestionIntentClassifier().classify("Present the relevant findings in a concise table with citations")
    assert analysis.intent == QuestionIntent.TABLE_SYNTHESIS

    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c1",
            paper_id="p1",
            document_id="d1",
            page_start=2,
            page_end=2,
            section="Methodology",
            text="We applied graph convolution networks with 4 layers and 256 hidden units.",
            score=0.88,
            title="GCN Paper",
        ),
        RetrievedSource(
            source_id="S2",
            chunk_id="c2",
            paper_id="p1",
            document_id="d1",
            page_start=5,
            page_end=5,
            section="Evaluation",
            text="The proposed method outperformed baselines by 14.2% in F1 score.",
            score=0.92,
            title="GCN Paper",
        ),
    ]

    answer = composer.compose(analysis, sources, [])
    assert "| Topic / Aspect | Key Finding / Evidence | Source & Location |" in answer
    assert "|---|---|---|" in answer
    assert "[S1]" in answer or "[S2]" in answer
    assert "Answer:" not in answer
    assert "Explanation:" not in answer


def test_06_structured_8_section_summary_and_honest_abstention():
    """Verify that 8-section summary produces grounded quotes and honest notices for missing sections."""
    composer = StructuredAnswerComposer()
    analysis = QuestionIntentClassifier().classify("Summarize the paper")
    assert analysis.intent == QuestionIntent.SUMMARY

    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c1",
            paper_id="p1",
            document_id="d1",
            page_start=1,
            page_end=1,
            section="Introduction",
            text="The primary motivation is to overcome severe latency bottlenecks in distributed consensus.",
            score=0.85,
            title="Consensus Study",
        ),
        RetrievedSource(
            source_id="S2",
            chunk_id="c2",
            paper_id="p1",
            document_id="d1",
            page_start=8,
            page_end=8,
            section="Conclusion",
            text="In conclusion, our decentralized architecture eliminates single-point bottlenecks.",
            score=0.89,
            title="Consensus Study",
        ),
    ]

    summary = composer.compose(analysis, sources, [])
    assert "### Structured Research Paper Summary" in summary
    assert "#### Problem / Motivation" in summary
    assert "#### Research Objective" in summary
    assert "#### Background / Related Work" in summary
    assert "#### Proposed Methodology / Architecture" in summary
    assert "#### Experimental Setup & Datasets" in summary
    assert "#### Key Findings & Performance Metrics" in summary
    assert "#### Reported Limitations & Threats to Validity" in summary
    assert "#### Conclusion & Future Directions" in summary

    # Verify honest abstention notice is present for unmentioned sections
    assert "*Not explicitly detailed in the retrieved passages.*" in summary


def test_07_query_pipeline_routing():
    """Verify QueryPipeline routes to independent engine by default."""
    pipeline = QueryPipeline()
    assert pipeline._independent_engine is not None

    dummy_source = RetrievedSource(
        source_id="S1",
        chunk_id="chk_mock",
        paper_id="p_mock",
        document_id="d_mock",
        page_start=1,
        page_end=1,
        section="Abstract",
        text="This research is defined as a fast deterministic research system.",
        score=0.99,
    )
    pipeline._independent_engine.retriever.retrieve = lambda *args, **kwargs: ([dummy_source], {"S1": []})

    res = pipeline.answer_question(
        question="what is this research",
        user_id="user_owner_1",
        paper_ids=["p_mock"],
        answer_mode="EVIDENCE_FIRST",
    )

    assert res.metadata["answer_mode"] == "independent_documents_only"
    assert res.metadata["model_calls"] == 0
    assert len(res.sources) >= 1


def test_08_owner_id_sec001_isolation_enforced():
    """Verify that QueryPipeline and IndependentResearchEngine enforce owner_id isolation."""
    pipeline = QueryPipeline()

    # Attempting to call without user_id raises ValueError
    with pytest.raises(ValueError, match="user_id is required"):
        pipeline.answer_question(
            question="what is the method",
            user_id="",
            paper_ids=["p_mock"],
        )


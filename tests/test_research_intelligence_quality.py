"""
Research Intelligence Quality Evaluation & Regression Suite.
Validates document structure understanding, intent planning, topic analysis,
retrieval granularity, evidence verification, and answer accuracy on isolated fixtures.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from rag.independent.engine import IndependentResearchEngine
from rag.independent.index_writer import IndependentIndexWriter
from rag.independent.ingest_pipeline import IndependentIngestionPipeline
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.models import QuestionIntent
from rag.independent.retriever import IndependentRetriever
from rag.independent.topic_analyzer import TopicCoverageAnalyzer


@pytest.fixture(scope="module")
def isolated_gate_env():
    """Sets up an isolated SQLite FTS5 index for the GATE syllabus document."""
    temp_dir = tempfile.mkdtemp(prefix="researchlens_qa_gate_")
    db_path = Path(temp_dir) / "test_lexical.sqlite3"
    
    writer = IndependentIndexWriter(db_path=db_path)
    pipeline = IndependentIngestionPipeline(index_writer=writer)
    
    gate_pdf = Path("storage/uploads/5918c028-3381-480a-b6e5-7bae7bc97b06.pdf")
    assert gate_pdf.is_file(), f"Target GATE PDF fixture not found: {gate_pdf}"
    
    paper_id = "paper_gate_test_01"
    doc_id = "doc_gate_test_01"
    owner_id = "owner_gate_qa_test"
    
    ingest_res = pipeline.ingest_file(
        file_path=str(gate_pdf),
        paper_id=paper_id,
        metadata={
            "document_id": doc_id,
            "owner_id": owner_id,
            "filename": "CS_GATE2027_Syllabus.pdf",
        }
    )
    assert ingest_res.success, f"GATE ingestion failed: {ingest_res.error}"
    assert ingest_res.chunk_count >= 10, f"Expected at least 10 section chunks, got: {ingest_res.chunk_count}"
    
    retriever = IndependentRetriever(db_path=db_path)
    engine = IndependentResearchEngine(retriever=retriever)
    
    yield {
        "engine": engine,
        "paper_id": paper_id,
        "doc_id": doc_id,
        "owner_id": owner_id,
        "chunk_count": ingest_res.chunk_count,
    }
    
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def isolated_multi_paper_env():
    """Sets up an isolated SQLite FTS5 index with two distinct research papers."""
    temp_dir = tempfile.mkdtemp(prefix="researchlens_qa_multi_")
    db_path = Path(temp_dir) / "test_multi_lexical.sqlite3"
    
    writer = IndependentIndexWriter(db_path=db_path)
    pipeline = IndependentIngestionPipeline(index_writer=writer)
    
    paper_a = Path(".researchlens-qa/fixtures/paper_alpha_quantum.pdf")
    paper_b = Path(".researchlens-qa/fixtures/paper_beta_algorithms.pdf")
    assert paper_a.is_file() and paper_b.is_file()
    
    owner_id = "owner_multi_qa_test"
    
    pipeline.ingest_file(
        file_path=str(paper_a),
        paper_id="paper_alpha",
        metadata={"document_id": "doc_alpha", "owner_id": owner_id, "filename": paper_a.name}
    )
    pipeline.ingest_file(
        file_path=str(paper_b),
        paper_id="paper_beta",
        metadata={"document_id": "doc_beta", "owner_id": owner_id, "filename": paper_b.name}
    )
    
    retriever = IndependentRetriever(db_path=db_path)
    engine = IndependentResearchEngine(retriever=retriever)
    
    yield {
        "engine": engine,
        "owner_id": owner_id,
        "paper_ids": ["paper_alpha", "paper_beta"],
    }
    
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# TEST 1: Which section contains the most topics? (Exact Reproduction & Fix)
# ==============================================================================
def test_gate_most_topics_ranking(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "tell me which section have more syllabus or topics"
    
    classifier = QuestionIntentClassifier()
    analysis = classifier.classify(q)
    assert analysis.intent == QuestionIntent.TOPIC_COUNT_RANKING
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    # Assertions
    assert "Section 1: Engineering Mathematics" in result.answer
    assert "has the most syllabus topics" in result.answer
    assert "### Section ranking" in result.answer
    assert "| Section 1: Engineering Mathematics |" in result.answer
    assert "### Explanation" in result.answer
    assert "### Supporting evidence" in result.answer
    assert len(result.sources) >= 10
    
    # Evidence panel verification: Section 1 should be cited with Page 1
    s1_source = next(s for s in result.sources if "Section 1" in s.section)
    assert s1_source.page_start == 1


# ==============================================================================
# TEST 2: Which section contains the fewest topics?
# ==============================================================================
def test_gate_fewest_topics_ranking(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "which section contains the fewest topics"
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "has the fewest syllabus topics" in result.answer
    assert ("Section 2: Digital Logic" in result.answer or "Section 4: Programming and Data Structures" in result.answer)
    assert "### Section ranking" in result.answer


# ==============================================================================
# TEST 3: How many distinct topics are present? (Topic Coverage Analysis)
# ==============================================================================
def test_gate_topic_coverage_analysis(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "analyze the syllabus coverage across all sections"
    
    classifier = QuestionIntentClassifier()
    analysis = classifier.classify(q)
    assert analysis.intent == QuestionIntent.TOPIC_COVERAGE_ANALYSIS
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "covers" in result.answer.lower()
    assert "sections" in result.answer.lower()
    assert "### Curriculum coverage breakdown" in result.answer


# ==============================================================================
# TEST 4: List all topics in Section 3
# ==============================================================================
def test_gate_section_3_topic_extraction(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "list all topics in section 3"
    
    classifier = QuestionIntentClassifier()
    analysis = classifier.classify(q)
    assert analysis.intent == QuestionIntent.TOPIC_EXTRACTION
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "Section 3: Computer Organization and Architecture" in result.answer
    assert "Instruction set and addressing modes" in result.answer
    assert "arithmetic and logic unit" in result.answer or "ALU" in result.answer
    assert "Memory interfacing" in result.answer or "pipelining" in result.answer


# ==============================================================================
# TEST 5: Compare Section 1 and Section 8
# ==============================================================================
def test_gate_compare_section_1_and_8(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "compare section 1 and section 8"
    
    classifier = QuestionIntentClassifier()
    analysis = classifier.classify(q)
    assert analysis.intent == QuestionIntent.SECTION_COMPARISON
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "Section 1: Engineering Mathematics" in result.answer
    assert "Section 8: Operating System" in result.answer
    assert "| Attribute |" in result.answer
    assert "Key differences" in result.answer


# ==============================================================================
# TEST 6: Summarize this syllabus
# ==============================================================================
def test_gate_summarize_syllabus(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "summarize this syllabus"
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert ("### Structured Document Summary" in result.answer or "### Structured Research Paper Summary" in result.answer)
    assert len(result.sources) > 0


# ==============================================================================
# TEST 7: What is an operating system? (Concept Explanation)
# ==============================================================================
def test_concept_explanation_operating_system(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "explain operating system"
    
    classifier = QuestionIntentClassifier()
    analysis = classifier.classify(q)
    assert analysis.intent == QuestionIntent.CONCEPT_EXPLANATION
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "Operating System" in result.answer
    assert "System calls" in result.answer or "processes" in result.answer or "threads" in result.answer
    assert len(result.sources) >= 1


# ==============================================================================
# TEST 8: Limitations extraction
# ==============================================================================
def test_limitations_extraction(isolated_multi_paper_env):
    engine = isolated_multi_paper_env["engine"]
    q = "what are the reported limitations in this paper"
    
    result = engine.answer(
        question=q,
        paper_ids=["paper_alpha"],
        user_id=isolated_multi_paper_env["owner_id"]
    )
    
    assert "Limitations" in result.answer or "threats to validity" in result.answer.lower() or "not found" in result.answer.lower()


# ==============================================================================
# TEST 9: Methodology extraction
# ==============================================================================
def test_methodology_extraction(isolated_multi_paper_env):
    engine = isolated_multi_paper_env["engine"]
    q = "what methodology was used in this study"
    
    result = engine.answer(
        question=q,
        paper_ids=["paper_alpha"],
        user_id=isolated_multi_paper_env["owner_id"]
    )
    
    assert "Methodology" in result.answer or "method" in result.answer.lower()


# ==============================================================================
# TEST 10: Reported numerical results
# ==============================================================================
def test_numerical_results(isolated_multi_paper_env):
    engine = isolated_multi_paper_env["engine"]
    q = "find the source's reported numerical results"
    
    result = engine.answer(
        question=q,
        paper_ids=["paper_alpha"],
        user_id=isolated_multi_paper_env["owner_id"]
    )
    
    assert "Reported metrics" in result.answer or "Numerical values" in result.answer or "not found" in result.answer.lower()


# ==============================================================================
# TEST 11: Ask for a fact that does not appear in the source (Abstention Quality)
# ==============================================================================
def test_abstention_on_absent_fact(isolated_gate_env):
    engine = isolated_gate_env["engine"]
    q = "what is the speed of light in vacuum according to this paper"
    
    result = engine.answer(
        question=q,
        paper_ids=[isolated_gate_env["paper_id"]],
        document_ids=[isolated_gate_env["doc_id"]],
        user_id=isolated_gate_env["owner_id"]
    )
    
    assert "Not found in your selected documents" in result.answer
    assert result.metadata["independent_research"]["evidence_decision"]["status"] == "NOT FOUND"


# ==============================================================================
# TEST 12: Comparison across two documents
# ==============================================================================
def test_multi_document_comparison(isolated_multi_paper_env):
    engine = isolated_multi_paper_env["engine"]
    q = "compare the methodologies of these two papers"
    
    result = engine.answer(
        question=q,
        paper_ids=isolated_multi_paper_env["paper_ids"],
        user_id=isolated_multi_paper_env["owner_id"]
    )
    
    assert "Comparison" in result.answer
    assert len(result.paper_ids) >= 1

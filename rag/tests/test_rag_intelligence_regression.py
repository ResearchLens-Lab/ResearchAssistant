"""
Comprehensive Regression Suite for RAG Answer Intelligence and Local Qwen Integration.
Tests all 15 scenarios:
1. Author extraction and author questions (Test A: Cormen, Leiserson, Rivest, Stein).
2. Definition questions and preface rejection (Test B: Algorithm definition).
3. Exact keyword retrieval.
4. Paraphrased questions.
5. Semantic retrieval relevance.
6. Irrelevant passage rejection.
7. Multi-document answers.
8. Citation verification.
9. Unsupported questions and honest abstention.
10. Local Qwen unavailable fallback to extractive mode.
11. Qwen response grounding and citation check.
12. Invalid citation rejection.
13. Interactive follow-up suggestions.
14. Summarization intent.
15. Deeper explanations intent.
"""

import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")

from rag.config.settings import settings
from rag.retrieval.query import RetrievedSource
from rag.research.orchestrator import CitationVerifier
from rag.generation.llm_client import OllamaLLMClient
from rag.generation.generator import GroundedGenerator


CLRS_FULL_BOOK_TEXT = """
Introduction to Algorithms
Third Edition

Thomas H. Cormen
Charles E. Leiserson
Ronald L. Rivest
Clifford Stein

The MIT Press
Cambridge, Massachusetts London, England

Preface
This book is designed to provide a comprehensive introduction to modern algorithms.
It is intended for use in university courses as well as for self-study by professionals.
We have tried to make algorithms accessible to all levels of readers.
The explanations are clear and straightforward without sacrificing depth.

Chapter 1: The Role of Algorithms in Computing

1.1 Algorithms
Informally, an algorithm is any well-defined computational procedure that takes some value, or set of values, as input and produces some value, or set of values, as output.
An algorithm is thus a sequence of computational steps that transform the input into the output.
We can also view an algorithm as a tool for solving a well-specified computational problem.
For example, we might need to sort a sequence of numbers into nondecreasing order.
"""

DISTRACTOR_PAGE = """
Recipe for Fresh Apple Tart
Preheat oven to 375 degrees F. Peel and slice the apples into uniform wedges.
Toss apples with cinnamon, sugar, and a squeeze of fresh lemon juice.
Bake for 45 minutes until the pastry crust is golden brown and flaky.
"""


@pytest.fixture
def seeded_pipeline(full_rag_pipeline):
    """Pre-seeds pipeline with CLRS textbook and mobile hardware benchmarks."""
    ingest_p, query_p = full_rag_pipeline
    ingest_p.ingest_text(
        content=CLRS_FULL_BOOK_TEXT,
        paper_id="book_clrs_algorithms",
        metadata={"title": "Introduction to Algorithms", "filename": "clrs_algorithms.pdf", "year": 2009},
    )
    ingest_p.ingest_text(
        content="On the Qualcomm Snapdragon 888 chipset, the model reached 78.6% ImageNet Top-1 accuracy with 14.2 ms inference latency.",
        paper_id="benchmarks_2024",
        metadata={"title": "Mobile Benchmarks", "filename": "benchmarks.pdf", "year": 2024},
    )
    ingest_p.ingest_text(
        content="Peak power draw remained strictly under 2.4 Watts during continuous inference. Thermal throttling was not observed.",
        paper_id="power_benchmarks_2024",
        metadata={"title": "Power Profile", "filename": "power.pdf", "year": 2024},
    )
    return ingest_p, query_p


def test_scenario_1_author_extraction(seeded_pipeline, monkeypatch):
    """Test A: Author entity question returns author names without requiring the keyword 'author'."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="Who is the author of this book?",
        paper_ids=["book_clrs_algorithms"],
    )

    assert "Thomas H. Cormen" in result.answer
    assert "Charles E. Leiserson" in result.answer
    assert "Ronald L. Rivest" in result.answer
    assert "Clifford Stein" in result.answer
    assert "[S1]" in result.answer
    assert len(result.sources) > 0
    assert "There is insufficient evidence" not in result.answer


def test_scenario_2_definition_retrieval_and_preface_rejection(seeded_pipeline, monkeypatch):
    """Test B: Definition questions retrieve the Chapter 1 definition rather than preface boilerplate."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What is an algorithm?",
        paper_ids=["book_clrs_algorithms"],
    )

    assert "computational procedure" in result.answer.casefold() or "sequence of computational steps" in result.answer.casefold()
    assert "[S1]" in result.answer
    # Top cited source must be the definition, not preface
    assert "computational procedure" in result.sources[0].text.casefold()


def test_scenario_3_exact_keyword_retrieval(seeded_pipeline, monkeypatch):
    """Scenario 3: Exact numeric and keyword matching works accurately."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What is the inference latency on Snapdragon 888?",
        paper_ids=["benchmarks_2024"],
    )

    assert "14.2 ms" in result.answer or "14.2" in result.answer
    assert len(result.sources) > 0


def test_scenario_4_paraphrased_questions(seeded_pipeline, monkeypatch):
    """Scenario 4: Paraphrased query maps to the relevant concept."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What is the latency on Qualcomm Snapdragon?",
        paper_ids=["benchmarks_2024"],
    )
    assert len(result.sources) > 0
    assert any("snapdragon" in s.text.casefold() for s in result.sources)


def test_scenario_5_semantic_retrieval_relevance(seeded_pipeline, monkeypatch):
    """Scenario 5: Dense embedding retrieval identifies semantic concepts."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What was the peak power draw during continuous inference?",
        paper_ids=["power_benchmarks_2024"],
    )
    assert "2.4" in result.answer or "Watts" in result.answer


def test_scenario_6_irrelevant_passage_rejection(seeded_pipeline, monkeypatch):
    """Scenario 6: Completely irrelevant passages (distractors) are not cited."""
    ingest_p, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    ingest_p.ingest_text(
        content=DISTRACTOR_PAGE,
        paper_id="distractor_paper",
        metadata={"title": "Apple Tart Recipe", "filename": "recipe.pdf", "page": 1},
    )

    result = query_p.answer_question(
        question="What is the definition of an algorithm in computing?",
        paper_ids=["book_clrs_algorithms", "distractor_paper"],
    )
    assert all("apple" not in s.text.casefold() for s in result.sources)


def test_scenario_7_multi_document_answers(seeded_pipeline, monkeypatch):
    """Scenario 7: Queries across multiple documents retrieve and cite sources from both."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="Compare the findings in the mobile benchmarks with the algorithm textbook.",
        paper_ids=["book_clrs_algorithms", "benchmarks_2024"],
    )
    assert len(result.sources) >= 1
    cited_papers = {s.paper_id for s in result.sources}
    assert len(cited_papers) >= 1


def test_scenario_8_citation_verification():
    """Scenario 8: Verifies valid citation markers match ground truth."""
    verifier = CitationVerifier()
    sources = [
        RetrievedSource(document_id="d1", chunk_id="c1", text="Atlas scored 91.2 percent on benchmark B1.", source_id="S1", paper_id="p1"),
        RetrievedSource(document_id="d2", chunk_id="c2", text="Boreal scored 88.4 percent on benchmark B1.", source_id="S2", paper_id="p2"),
    ]
    raw_answer = "Atlas reached 91.2% [S1] while Boreal achieved 88.4% [S2]."
    clean, verification = verifier.verify(raw_answer, sources, ["p1", "p2"])
    assert set(verification.valid_source_ids) == {"S1", "S2"}
    assert verification.invalid_source_ids == []
    assert "[S1]" in clean and "[S2]" in clean


def test_scenario_9_unsupported_questions_honest_abstention(seeded_pipeline, monkeypatch):
    """Scenario 9: Unanswerable/unsupported question triggers honest abstention."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What was the price of apples in Paris in 1789?",
        paper_ids=["book_clrs_algorithms"],
    )
    assert "insufficient evidence" in result.answer.casefold()
    assert len(result.sources) == 0


def test_scenario_10_local_qwen_unavailable_fallback(seeded_pipeline, monkeypatch):
    """Scenario 10: When LOCAL_QWEN mode is active but Ollama is offline, gracefully fall back to extractive mode."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "LOCAL_QWEN")
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:54321")  # non-existent port

    result = query_p.answer_question(
        question="What is an algorithm?",
        paper_ids=["book_clrs_algorithms"],
    )
    assert result.metadata.get("answer_mode") in ("evidence_fallback", "EXTRACTIVE", "evidence_only")
    assert "computational procedure" in result.answer.casefold() or "sequence of computational steps" in result.answer.casefold()
    assert len(result.sources) > 0


def test_scenario_11_qwen_response_grounding(monkeypatch):
    """Scenario 11: GroundedGenerator formats system prompt with strict grounding and citation instructions."""
    mock_client = MagicMock(spec=OllamaLLMClient)
    mock_client.generate.return_value = "An algorithm is a computational procedure [S1]."
    generator = GroundedGenerator(llm_client=mock_client)

    context = MagicMock()
    context.to_prompt_context.return_value = "[S1] An algorithm is a sequence of computational steps."
    context.source_ids = ["S1"]

    res = generator.generate_answer(
        question="What is an algorithm?",
        context=context,
        intent="definition",
    )
    assert "algorithm" in res.answer.casefold()
    assert "[S1]" in res.answer
    assert mock_client.generate.called


def test_scenario_12_invalid_citation_rejection():
    """Scenario 12: Hallucinated citations like [S99] are removed during verification."""
    verifier = CitationVerifier()
    sources = [
        RetrievedSource(document_id="d1", chunk_id="c1", text="Transformers rely on multi-head attention.", source_id="S1", paper_id="p1"),
    ]
    raw_answer = "Transformers rely on multi-head attention [S1] and recurrent units [S99]."
    clean, verification = verifier.verify(raw_answer, sources, ["p1"])
    assert "[S99]" not in clean
    assert "[S1]" in clean
    assert "S99" in verification.invalid_source_ids


def test_scenario_13_interactive_follow_up_suggestions(seeded_pipeline, monkeypatch):
    """Scenario 13: Metadata includes 3-4 interactive contextual follow-up suggestions."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="What is an algorithm?",
        paper_ids=["book_clrs_algorithms"],
    )
    follow_ups = result.metadata.get("follow_up_suggestions", [])
    assert len(follow_ups) >= 3
    assert any("depth" in f.casefold() or "example" in f.casefold() or "simple" in f.casefold() for f in follow_ups)


def test_scenario_14_summarization_intent(seeded_pipeline, monkeypatch):
    """Scenario 14: Summary queries correctly assign 'summary' intent and format key points."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="Summarize the core topics in Introduction to Algorithms.",
        paper_ids=["book_clrs_algorithms"],
    )
    assert result.metadata["research"]["intent"] == "summary"
    assert len(result.sources) > 0


def test_scenario_15_deeper_explanations_intent(seeded_pipeline, monkeypatch):
    """Scenario 15: Follow-up deeper explanation queries assign 'follow_up' intent and expand search."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")

    result = query_p.answer_question(
        question="Explain in more depth the computational procedure of an algorithm.",
        paper_ids=["book_clrs_algorithms"],
    )
    assert result.metadata["research"]["intent"] in ("follow_up", "explanation", "definition")
    assert len(result.sources) > 0


def test_scenario_16_short_follow_up_retrieves_the_previous_book_topic(seeded_pipeline, monkeypatch):
    """A short follow-up must stay on the immediate topic, not bibliography matches."""
    _, query_p = seeded_pipeline
    monkeypatch.setattr(settings, "rag_answer_mode", "EXTRACTIVE")
    monkeypatch.setattr(settings, "llm_provider", "local")
    context = (
        "user: What is an algorithm?\n"
        "assistant: An algorithm is a well-defined computational procedure that transforms input into output [S1]."
    )

    result = query_p.answer_question(
        question="Explain in more depth",
        paper_ids=["book_clrs_algorithms"],
        conversation_context=context,
    )

    assert "algorithm" in result.metadata["research"]["plan"]["resolved_question"].casefold()
    assert result.sources
    assert all("references" not in (source.section or "").casefold() for source in result.sources)
    assert any("algorithm" in source.text.casefold() for source in result.sources)

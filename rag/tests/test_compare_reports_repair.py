import os
from pathlib import Path
import pytest
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.fact_extractor import is_syntax_convention_noise
from rag.independent.engine import IndependentResearchEngine


def test_comparison_query_aspect_decomposition():
    classifier = QuestionIntentClassifier()
    q = "I want to know the different types of algorithms and their limitations"
    aspects = classifier.decompose_comparison_aspects(q)
    assert len(aspects) >= 2
    titles = [a["title"] for a in aspects]
    assert "Algorithm Types & Design Paradigms" in titles
    assert "Reported Limitations & Complexity Constraints" in titles


def test_syntax_convention_noise_filtering():
    noisy_lines = [
        "Comments begin with // and continue until the end of line",
        "Blocks are indicated with matching braces",
        "An identifier begins with a letter",
        "Keywords are in boldface",
        "In this text we present most of our algorithms using a pseudocode that resembles C and Pascal",
    ]
    for line in noisy_lines:
        assert is_syntax_convention_noise(line) is True

    valid_lines = [
        "This part covers three important techniques used in designing and analyzing efficient algorithms: dynamic programming, greedy algorithms, and amortized analysis.",
        "The greedy method is perhaps the most straightforward design technique we consider in this text.",
        "An algorithm is a finite set of instructions that accomplishes a particular task.",
    ]
    for line in valid_lines:
        assert is_syntax_convention_noise(line) is False


def test_compare_three_formats_consistency():
    db_path = Path.home() / "Documents" / "ResearchLens Library" / "library.sqlite3"
    if not db_path.is_file():
        pytest.skip("Local test library database not found")

    engine = IndependentResearchEngine()
    cormen_id = "ca86fa5f-3baa-4c68-9abb-294a6d8f832f"
    horowitz_id = "be61583c-74c9-4681-bfd6-bf5a62ed719f"
    q = "I want to know the different types of algorithms and their limitations"

    for fmt in ["table", "side_by_side", "detailed_report"]:
        res = engine.answer(
            question=q,
            document_ids=[cormen_id, horowitz_id],
            output_format=fmt,
            document_labels={cormen_id: "Cormen", horowitz_id: "Horowitz"},
        )
        dec = res.metadata.get("independent_research", {}).get("evidence_decision", {})
        assert dec.get("status") == "STRONGLY SUPPORTED", f"Format {fmt} failed with status {dec.get('status')}"
        assert len(dec.get("unsupported_claims", [])) == 0, f"Format {fmt} had unsupported claims: {dec.get('unsupported_claims')}"
        assert len(res.sources) >= 2, f"Format {fmt} retrieved fewer than 2 sources"

        # Verify consecutive citation IDs without gaps
        source_ids = [s.source_id for s in res.sources]
        expected_ids = [f"S{i + 1}" for i in range(len(source_ids))]
        assert source_ids == expected_ids, f"Format {fmt} had non-consecutive source IDs: {source_ids}"

        # Verify comparison_formats exists in metadata
        formats = res.metadata.get("comparison_formats")
        assert formats is not None
        assert "table" in formats
        assert "side_by_side" in formats
        assert "detailed_report" in formats


def test_research_desk_noise_avoidance():
    db_path = Path.home() / "Documents" / "ResearchLens Library" / "library.sqlite3"
    if not db_path.is_file():
        pytest.skip("Local test library database not found")

    engine = IndependentResearchEngine()
    cormen_id = "ca86fa5f-3baa-4c68-9abb-294a6d8f832f"
    horowitz_id = "be61583c-74c9-4681-bfd6-bf5a62ed719f"

    res = engine.answer(question="different algorithms?", document_ids=[cormen_id, horowitz_id])
    assert "Comments begin with //" not in res.answer
    assert "matching braces" not in res.answer
    assert "An identifier begins with a letter" not in res.answer

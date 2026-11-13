import pytest

from backend.app.services.research_intelligence import (
    Phase1ResearchIntelligenceAdapter,
    PublicMetadataProvider,
    ResearchIntelligenceError,
    ResearchQuestionAnalyzer,
    normalize,
    tokens,
)


@pytest.mark.parametrize(("question", "expected"), [
    ("How do these two papers compare?", "PAPER_COMPARISON"),
    ("What evidence supports this claim?", "CLAIM_ASSESSMENT"),
    ("Which studies contradict this result?", "CONTRADICTION_ANALYSIS"),
    ("What research gaps are in my library?", "RESEARCH_GAP_ANALYSIS"),
    ("Summarize this paper", "PAPER_OVERVIEW"),
])
def test_question_analysis_is_deterministic_and_preserves_source(question, expected):
    result = ResearchQuestionAnalyzer().analyze(question)
    assert result["task_type"] == expected
    assert result["original_question"] == question
    assert result["model_used"] is False
    assert result["subquestions"]
    assert all(item["derived_from"] == question for item in result["subquestions"])


def test_comparison_decomposition_checks_experimental_comparability():
    result = ResearchQuestionAnalyzer().analyze("Compare the two methods and results")
    ids = {item["task_id"] for item in result["subquestions"]}
    assert {"identify_methods", "retrieve_context", "compare_results", "assess_comparability"} <= ids


def test_local_token_normalization_is_transparent():
    assert tokens("Algorithmic methods: BERT-2") == {"algorithmic", "methods", "bert-2"}
    assert normalize("A DOI: 10.1234/ABC") == "a doi 10 1234 abc"


def test_adapter_is_disabled_by_default():
    assert Phase1ResearchIntelligenceAdapter().enabled is False


@pytest.mark.asyncio
async def test_external_lookup_requires_explicit_public_identifier():
    with pytest.raises(ResearchIntelligenceError):
        await PublicMetadataProvider().lookup()

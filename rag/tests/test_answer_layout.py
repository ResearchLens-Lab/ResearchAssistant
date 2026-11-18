import re
import pytest
from rag.intelligence.answer_composer import ResearchAnswerComposer
from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import RetrievedSource
from rag.intelligence.confidence_evaluator import ConfidenceReport, ConfidenceLevel


@pytest.fixture
def sample_sources():
    return [
        RetrievedSource(
            chunk_id="chk_cormen_1",
            paper_id="paper_cormen",
            source_id="src_cormen_1",
            text="A red-black tree is a binary search tree with one extra bit of storage per node: its color, which can be either RED or BLACK. Each node of the tree contains the attributes color, key, left, right, and p.",
            title="Introduction to Algorithms",
            locator="Chapter 13, Page 308",
            page_start=308,
            document_id="doc_cormen",
        ),
        RetrievedSource(
            chunk_id="chk_cormen_2",
            paper_id="paper_cormen",
            source_id="src_cormen_2",
            text="Because a red-black tree with n internal nodes has height at most 2 lg(n + 1), search operations take O(lg n) time in the worst case. Insertion and deletion also run in O(lg n) time.",
            title="Introduction to Algorithms",
            locator="Chapter 13, Page 310",
            page_start=310,
            document_id="doc_cormen",
        ),
        RetrievedSource(
            chunk_id="chk_horowitz_1",
            paper_id="paper_horowitz",
            source_id="src_horowitz_1",
            text="An algorithm is a finite set of instructions that, if followed, accomplishes a particular task. In addition, all algorithms must satisfy the following criteria: input, output, definiteness, finiteness, and effectiveness.",
            title="Fundamentals of Computer Algorithms",
            locator="Chapter 1, Page 23",
            page_start=23,
            document_id="doc_horowitz",
        ),
    ]


@pytest.mark.parametrize("intent", [
    ResearchIntent.DEFINITION,
    ResearchIntent.COMPLEXITY,
    ResearchIntent.PROCEDURE,
    ResearchIntent.COMPARISON,
    ResearchIntent.LIST_PROPERTIES,
    ResearchIntent.LOCATE,
    ResearchIntent.EXAMPLE,
    ResearchIntent.THEOREM_LOOKUP,
    ResearchIntent.SUMMARIZATION,
    ResearchIntent.COUNT_RANKING,
    ResearchIntent.RELATIONSHIP,
    ResearchIntent.EVIDENCE_VERIFICATION,
    ResearchIntent.CLASSIFICATION,
    ResearchIntent.OTHER,
])
def test_answer_layout_for_every_intent(sample_sources, intent):
    composer = ResearchAnswerComposer()
    query = QueryUnderstanding(
        raw_query=f"Explain {intent.value} of red-black tree",
        normalized_query=f"explain {intent.value} of red-black tree",
        intent=intent,
        primary_concept="red-black tree",
        query_constraints={},
    )
    confidence = ConfidenceReport(
        level=ConfidenceLevel.STRONG,
        overall_confidence_score=0.92,
        is_definitive_answer=True,
        top_source=sample_sources[0],
    )

    answer = composer.compose(query, sample_sources, confidence)
    assert answer is not None
    content = answer.markdown_content
    assert content, "Markdown content must not be empty"

    # 1. No LLM jargon
    forbidden = ["as an ai", "i cannot", "based on my knowledge", "as a language model"]
    for phrase in forbidden:
        assert phrase not in content.lower(), f"Found LLM jargon '{phrase}' in answer"
        assert phrase not in (answer.headline_answer or "").lower(), f"Found LLM jargon '{phrase}' in headline"

    # 2. First section is a 1-3 sentence extractive direct answer
    # First section should have an extractive quote or direct answer lines
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    has_direct_quote = any(l.startswith("> ") for l in lines[:5])
    has_direct_para = any(len(l) > 25 and not l.startswith(("#", "-", "*", "|", ">")) for l in lines[:5])
    assert has_direct_quote or has_direct_para, "First section must contain a 1-3 sentence direct answer"

    # 3. Followed by evidence bullets with citations
    has_bullets_or_tables = any(re.match(r"^[-*]\s+", l) or re.match(r"^\|\s+", l) or re.match(r"^\d+\.\s+", l) for l in lines)
    assert has_bullets_or_tables, "Answer must contain evidence bullets or table with citations"

    # 4. Followed by max 3 related questions
    assert "### Related Questions" in content
    rel_section = content.split("### Related Questions")[-1]
    rel_questions = [l for l in rel_section.split("\n") if l.strip().startswith("- ")]
    assert 1 <= len(rel_questions) <= 3, f"Expected 1-3 related questions, got {len(rel_questions)}"

    # 5. Every citation resolves to a real chunk in the retrieved set
    valid_source_ids = {s.source_id for s in sample_sources}
    cited_ids = re.findall(r"\[([A-Za-z0-9_-]+)\]", content)
    # Filter out markdown formatting like [x] or table headers
    for cid in cited_ids:
        assert cid in valid_source_ids, f"Citation [{cid}] does not resolve to a retrieved source"

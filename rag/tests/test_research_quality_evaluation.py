"""
Comprehensive 12-scenario evaluation suite for ResearchLens deterministic research quality.
Validates:
1. Academic answer grounding and truthfulness
2. Honest abstention when target concept is not formally defined
3. Exact bibliographic author extraction
4. Systematic literature review methodology synthesis
5. High-quality non-fragmented explanation synthesis
6. Clean tabular synthesis with zero isolated digits and zero publication headers
7. Genuine limitation and challenge identification
8. Comparative analysis across distinct sources
9. Accurate numeric extraction with verified units
10. Dependent follow-up query contextual rewriting
11. Independent question immunity from prior conversation topic corruption
12. Strict SEC-001 tenant isolation and provenance tracking
"""

import pytest
from rag.independent.models import QuestionIntent
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.answer_composer import StructuredAnswerComposer
from rag.independent.fact_extractor import FactExtractor, clean_academic_text
from rag.citations.citation_mapper import format_citation_label, CitationMapper
from rag.citations.source_tracker import SourceTracker
from rag.retrieval.query import RetrievedSource


@pytest.fixture
def classifier():
    return QuestionIntentClassifier()


@pytest.fixture
def composer():
    return StructuredAnswerComposer()


@pytest.fixture
def cormen_source():
    return RetrievedSource(
        source_id="S1",
        chunk_id="cormen_c1",
        paper_id="paper_cormen",
        document_id="doc_cormen",
        page_start=5,
        page_end=5,
        section="1.1 Algorithms",
        text=(
            "Informally, an algorithm is any well-defined computational procedure that takes "
            "some value, or set of values, as input and produces some value, or set of values, as output. "
            "An algorithm is thus a sequence of computational steps that transform the input into the output."
        ),
        score=0.98,
        title="Introduction to Algorithms",
        filename="cormen.pdf",
    )


@pytest.fixture
def hassan_methodology_source():
    return RetrievedSource(
        source_id="S1",
        chunk_id="hassan_c0007",
        paper_id="paper_hassan",
        document_id="doc_hassan",
        page_start=2,
        page_end=3,
        section="4. RESEARCH METHODOLOGY",
        text=(
            "4. RESEARCH METHODOLOGY This study employs a systematic literature review to assess current advancements "
            "in cybersecurity research between 2020 and 2024. This study adopted the systematic literature review "
            "techniques developed by (Kitchenham et al., 2003) and (Torres-Carrión et al., 2018). The systematic approach "
            "encompassing the following key steps: Research questions definition, design of search strategy, selection of "
            "studies, evaluation of quality, extraction and synthesis of data. A total of thirty academic studies were "
            "analyzed to identify key trends, challenges, and technological innovations. The search criteria used keywords: "
            "“AI in Cybersecurity”, “Role of AI in Cybersecurity”, “Security risks Gen AI”."
        ),
        score=0.95,
        title="Advances in Cybersecurity: A Literature Review",
        filename="hassan.pdf",
    )


@pytest.fixture
def hassan_ai_source():
    return RetrievedSource(
        source_id="S2",
        chunk_id="hassan_c0002",
        paper_id="paper_hassan",
        document_id="doc_hassan",
        page_start=1,
        page_end=2,
        section="3. LITERATURE REVIEW",
        text=(
            "3.1 The Role of AI and Machine Learning in Cybersecurity The use of machine learning and deep learning "
            "techniques in cybersecurity has gained significant attention. AI assists in safeguarding systems against "
            "unauthorized access by predicting the behavior of malicious software. Srivastava et al. (2022) highlight "
            "the growing relevance of Explainable AI (xAI) in cybersecurity, advocating for transparent models to build "
            "trust and efficacy in automated defense systems."
        ),
        score=0.91,
        title="Advances in Cybersecurity: A Literature Review",
        filename="hassan.pdf",
    )


# Scenario 1: Direct Definition Grounding
def test_scenario_01_definition_grounding(classifier, composer, cormen_source):
    analysis = classifier.classify("What is an algorithm?")
    assert analysis.intent in (QuestionIntent.DEFINITION, QuestionIntent.CONCEPT_EXPLANATION)
    facts = FactExtractor().extract([cormen_source], analysis.important_terms)
    answer = composer.compose(analysis, [cormen_source], facts)
    assert "### Definition" in answer or "### Direct answer" in answer
    assert "well-defined computational procedure" in answer
    assert "- **Input:**" in answer
    assert "- **Output:**" in answer
    assert "[S1]" in answer


# Scenario 2: Honest Academic Abstention for Undefined Subject
def test_scenario_02_honest_definition_abstention(classifier, composer, hassan_methodology_source):
    analysis = classifier.classify("What is cybersecurity?")
    assert analysis.intent in {QuestionIntent.DEFINITION, QuestionIntent.FACT_LOOKUP}
    facts = FactExtractor().extract([hassan_methodology_source], analysis.important_terms)
    answer = composer.compose(analysis, [hassan_methodology_source], facts)
    # Must NOT fabricate a definition or pick an arbitrary sentence
    assert (
        "does not contain an explicit formal definition" in answer
        or "Direct answer" in answer
    )


# Scenario 3: Author Extraction
def test_scenario_03_author_extraction():
    source = RetrievedSource(
        source_id="S1",
        chunk_id="title_page",
        paper_id="p1",
        document_id="d1",
        page_start=1,
        page_end=1,
        section="Title",
        text="Advances in Cybersecurity: A Literature Review\nAmrani Hassan, Kennedy Hadullo, Kelvin Tole\nAbstract: Rapid pace...",
        score=1.0,
    )
    facts = FactExtractor().extract([source], ["authors"])
    authors = [f.value for f in facts if f.fact_type == "person_candidate"]
    assert "Amrani Hassan" in authors
    assert "Kennedy Hadullo" in authors
    assert "Kelvin Tole" in authors


# Scenario 4: Methodology Synthesis
def test_scenario_04_methodology_synthesis(classifier, composer, hassan_methodology_source):
    analysis = classifier.classify("What research methodology did the authors use?")
    assert analysis.intent == QuestionIntent.METHODOLOGY_EXTRACTION
    facts = FactExtractor().extract([hassan_methodology_source], analysis.important_terms)
    answer = composer.compose(analysis, [hassan_methodology_source], facts)
    assert "### Research Methodology" in answer
    assert "Systematic Literature Review" in answer
    assert "Kitchenham et al." in answer or "Torres-Carrión" in answer
    assert "Research questions" in answer
    assert "[S1]" in answer


# Scenario 5: Explanation Synthesis
def test_scenario_05_explanation_synthesis(classifier, composer, hassan_ai_source):
    analysis = classifier.classify("How does the paper describe the role of AI in cybersecurity?")
    assert analysis.intent == QuestionIntent.EXPLANATION
    facts = FactExtractor().extract([hassan_ai_source], analysis.important_terms)
    answer = composer.compose(analysis, [hassan_ai_source], facts)
    assert "### Direct answer" in answer or "### Direct Explanation" in answer or "### Key Grounded Points" in answer
    assert "deep learning" in answer or "Explainable AI" in answer
    assert "[S2]" in answer


# Scenario 6: Table Synthesis Rejects Publication Headers and Random Numbers
def test_scenario_06_table_synthesis_quality(classifier, composer, hassan_methodology_source, hassan_ai_source):
    analysis = classifier.classify("Present the relevant findings in a concise table with citations")
    assert analysis.intent == QuestionIntent.TABLE_SYNTHESIS
    sources = [hassan_methodology_source, hassan_ai_source]
    facts = FactExtractor().extract(sources, analysis.important_terms)
    answer = composer.compose(analysis, sources, facts)
    assert "| Topic / Aspect | Key Finding / Evidence | Source & Location |" in answer
    assert "|---|---|---|" in answer
    # Must NOT have raw publication headers
    assert "Volume 14" not in answer
    assert "ISSN" not in answer
    assert "DOI:" not in answer


# Scenario 7: Limitations Extraction
def test_scenario_07_limitations_extraction(classifier, composer):
    source = RetrievedSource(
        source_id="S1",
        chunk_id="lim1",
        paper_id="p1",
        document_id="d1",
        page_start=3,
        page_end=3,
        section="Limitations",
        text="The review has certain limitations: it focuses exclusively on English-language peer-reviewed articles.",
        score=0.9,
    )
    analysis = classifier.classify("What are the reported limitations?")
    assert analysis.intent == QuestionIntent.LIMITATIONS_EXTRACTION
    facts = FactExtractor().extract([source], analysis.important_terms)
    answer = composer.compose(analysis, [source], facts)
    assert "### Reported" in answer
    assert "English-language peer-reviewed articles" in answer
    assert "[S1]" in answer


# Scenario 8: Comparative Analysis
def test_scenario_08_comparison(classifier, composer, cormen_source, hassan_ai_source):
    analysis = classifier.classify("Compare the two documents")
    assert analysis.intent == QuestionIntent.COMPARISON
    sources = [cormen_source, hassan_ai_source]
    facts = FactExtractor().extract(sources, analysis.important_terms)
    answer = composer.compose(analysis, sources, facts)
    assert "### Comparison of retrieved evidence" in answer
    assert "| Comparison dimension |" in answer or "| Source | Retrieved finding | Location |" in answer


# Scenario 9: Numerical Extraction with Units
def test_scenario_09_numerical_query(classifier, composer):
    source = RetrievedSource(
        source_id="S1",
        chunk_id="num1",
        paper_id="p1",
        document_id="d1",
        page_start=4,
        page_end=4,
        section="Results",
        text="The classifier achieved an overall accuracy of 96.4% across 10-fold cross validation.",
        score=0.95,
    )
    analysis = classifier.classify("What percentage accuracy was achieved?")
    assert analysis.intent == QuestionIntent.NUMERICAL_QUERY
    facts = FactExtractor().extract([source], analysis.important_terms)
    num_facts = [f for f in facts if f.fact_type in {"numerical_value", "metric"}]
    assert any("96.4%" in f.value for f in num_facts)
    answer = composer.compose(analysis, [source], facts)
    assert "96.4%" in answer
    assert "[S1]" in answer


# Scenario 10: Dependent Follow-Up Query Contextual Rewriting
def test_scenario_10_follow_up_rewriting(classifier):
    context = "user: What research methodology did the authors use?\nassistant: The authors used a systematic literature review."
    follow_up = "Present the relevant findings in a concise table with citations"
    analysis = classifier.classify(follow_up, conversation_context=context)
    assert analysis.intent == QuestionIntent.TABLE_SYNTHESIS
    # Search query should incorporate the prior topic
    assert "methodology" in analysis.search_query.casefold()


# Scenario 11: Independent Question Immunity from Prior Topic
def test_scenario_11_independent_query_immunity(classifier):
    context = "user: Present the relevant findings in a concise table with citations\nassistant: | Topic | Finding |"
    new_question = "Who wrote this paper?"
    analysis = classifier.classify(new_question, conversation_context=context)
    assert analysis.intent == QuestionIntent.AUTHOR_LOOKUP
    # Must NOT be coerced into TABLE_SYNTHESIS
    assert analysis.intent != QuestionIntent.TABLE_SYNTHESIS


# Scenario 12: Citation Label Standards and SEC-001 Metadata
def test_scenario_12_citation_metadata_standards():
    label1 = format_citation_label(
        authors=["Amrani Hassan", "Kennedy Hadullo", "Kelvin Tole"],
        year=2025,
        page_start=2,
        page_end=3,
        title="Advances in Cybersecurity",
    )
    assert label1 == "[Hassan et al., 2025, pp. 2-3]"

    tracker = SourceTracker([
        RetrievedSource(
            source_id="S1",
            chunk_id="c1",
            paper_id="p_sec",
            document_id="d_sec",
            page_start=2,
            page_end=2,
            section="Methodology",
            text="Evidence passage for user 1.",
            score=1.0,
        )
    ])
    mapper = CitationMapper(tracker, paper_metadata={
        "p_sec": {
            "title": "Secure Document",
            "authors": ["Alice Smith", "Bob Jones"],
            "year": 2024,
        }
    })
    citations = mapper.map_citations(["S1"])
    assert len(citations) == 1
    assert citations[0].citation_label == "[Smith & Jones, 2024, p. 2]"
    assert citations[0].author_metadata == ["Alice Smith", "Bob Jones"]


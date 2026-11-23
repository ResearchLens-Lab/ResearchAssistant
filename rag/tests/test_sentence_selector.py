"""Unit tests for SentenceSelector, MMR deduplication, Context Restoration, and Calibrated Validation."""

import pytest
from rag.independent.models import QueryAnalysis, QuestionIntent
from rag.independent.sentence_selector import SentenceSelector, segment_into_sentences, extract_prose_steps
from rag.retrieval.query import RetrievedSource


@pytest.fixture
def sample_sources():
    s1 = RetrievedSource(
        source_id="S1",
        chunk_id="chunk_search",
        paper_id="paper_algo",
        document_id="doc_algo",
        page_start=42,
        page_end=42,
        section="2.3 Binary Search",
        text=(
            "Binary search is an efficient search algorithm on ordered collections. "
            "It repeatedly compares the target with the middle element of a sorted array and discards half of the remaining interval. "
            "This procedure terminates when the target is found or the search interval becomes empty."
        ),
        score=0.95,
        title="Algorithms",
        filename="algo.pdf",
    )
    s2 = RetrievedSource(
        source_id="S2",
        chunk_id="chunk_limits",
        paper_id="paper_algo",
        document_id="doc_algo",
        page_start=45,
        page_end=45,
        section="2.4 Complexity",
        text=(
            "While binary search runs in O(log n) time, a strict limitation is that it requires random access and pre-sorted data. "
            "However, maintaining sorted order under dynamic insertions incurs O(n) overhead."
        ),
        score=0.90,
        title="Algorithms",
        filename="algo.pdf",
    )
    return [s1, s2]


def test_segment_into_sentences_abbreviation_safety():
    text = "The protocol was tested vs. baseline methods (e.g. Atlas, Boreal et al.). Dr. Smith verified the result. It ran in 12.5 ms."
    sents = segment_into_sentences(text)
    assert len(sents) == 3
    assert "vs." in sents[0]
    assert "e.g. Atlas" in sents[0]
    assert "Dr. Smith" in sents[1]
    assert "12.5 ms." in sents[2]


def test_context_restoration_anaphora_and_connectors(sample_sources):
    selector = SentenceSelector()
    candidates = selector.extract_candidates(sample_sources)

    # Candidate 1: "It repeatedly compares..."
    it_cand = next(c for c in candidates if c.text.startswith("It repeatedly"))
    assert it_cand.has_dangling_reference is True
    assert it_cand.preceding_text is not None
    assert "Binary search is an efficient search algorithm" in it_cand.restored_text
    assert "It repeatedly compares" in it_cand.restored_text

    # Candidate 2: "This procedure terminates..."
    this_cand = next(c for c in candidates if c.text.startswith("This procedure"))
    assert this_cand.has_dangling_reference is True
    assert "It repeatedly compares" in this_cand.preceding_text

    # Candidate 3: "However, maintaining..."
    however_cand = next(c for c in candidates if c.text.startswith("However"))
    assert however_cand.has_dangling_reference is True
    assert "strict limitation" in however_cand.preceding_text


def test_mmr_deduplication(sample_sources):
    selector = SentenceSelector(mmr_lambda=0.70)
    analysis = QueryAnalysis(
        intent=QuestionIntent.DEFINITION,
        normalized_question="what is binary search",
        search_query="binary search",
        important_terms=["binary search", "search algorithm"],
        primary_phrase="binary search",
    )
    selected = selector.select_evidence_mmr(analysis, sample_sources, limit=3)
    assert len(selected) >= 1
    # First sentence should be the direct definition
    assert any("Binary search is an efficient search algorithm" in c.text for c in selected)
    # Check that duplicates are not returned
    texts = [c.text for c in selected]
    assert len(texts) == len(set(texts))


def test_document_order_preservation(sample_sources):
    selector = SentenceSelector()
    analysis = QueryAnalysis(
        intent=QuestionIntent.EXPLANATION,
        normalized_question="how does binary search work and what are its limitations",
        search_query="binary search limitations",
        important_terms=["binary search", "limitation"],
    )
    selected = selector.select_evidence_mmr(analysis, sample_sources, limit=4, preserve_document_order=True)
    # Ensure chunk_search sentences come before chunk_limits sentences
    indices = [c.page_start for c in selected]
    assert indices == sorted(indices)


def test_calibrated_evidence_validation_abstention():
    selector = SentenceSelector()
    analysis = QueryAnalysis(
        intent=QuestionIntent.DEFINITION,
        normalized_question="what is penicillin",
        search_query="penicillin",
        important_terms=["penicillin", "antibiotic", "chemical"],
    )
    dummy_source = RetrievedSource(
        source_id="S1",
        chunk_id="c1",
        paper_id="p1",
        document_id="d1",
        page_start=1,
        page_end=1,
        section="Introduction",
        text="Binary search repeatedly compares elements in a sorted array.",
        score=0.2,
    )
    candidates = selector.extract_candidates([dummy_source])
    for c in candidates:
        selector.score_candidate(c, analysis)

    is_sufficient, missing = selector.check_evidence_sufficiency(analysis, candidates)
    assert is_sufficient is False
    assert "penicillin" in missing


def test_textrank_centrality():
    selector = SentenceSelector(enable_textrank=True)
    s = RetrievedSource(
        source_id="S1",
        chunk_id="c1",
        paper_id="p1",
        document_id="d1",
        page_start=1,
        page_end=1,
        section="Methods",
        text=(
            "Quantum error correction preserves quantum states across noisy qubits. "
            "Surface codes provide topological quantum error correction. "
            "The error correction threshold depends on physical qubit error rates."
        ),
        score=0.9,
    )
    candidates = selector.extract_candidates([s])
    scores = selector.compute_textrank(candidates)
    assert len(scores) == 3
    # Error correction is shared across sentences and should have valid centrality
    for cid, tr_score in scores.items():
        assert 0.0 <= tr_score <= 1.0


def test_extract_prose_steps():
    text = (
        "The merge sort procedure consists of three sequential steps: "
        "first, divide the n-element sequence to be sorted into two subsequences; "
        "second, conquer by sorting the two subsequences recursively using merge sort; "
        "third, combine the sorted subsequences by merging them to produce the sorted answer."
    )
    steps = extract_prose_steps(text)
    assert len(steps) == 3
    assert steps[0][0].lower() == "divide"
    assert "divide the n-element" in steps[0][1]
    assert steps[1][0].lower() == "conquer"
    assert "conquer by sorting" in steps[1][1]
    assert steps[2][0].lower() == "combine"
    assert "combine the sorted" in steps[2][1]

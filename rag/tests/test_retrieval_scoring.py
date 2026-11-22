import pytest
from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import (
    ExplainableRetrievalEngine,
    norm,
    body_text,
    compute_heading_boost,
    compute_description_boost,
    compute_caption_penalty,
    compute_garbage_penalty,
)


@pytest.fixture
def retrieval_engine():
    # Synthetic unit tests do not require an active SQLite DB
    return ExplainableRetrievalEngine(db_path=":memory:")


def test_hyphen_vs_space_matches():
    """Verify that norm() normalizes hyphens, underscores, casing, and spaces uniformly."""
    assert norm("Divide-and-Conquer") == "divide and conquer"
    assert norm("divide_and_conquer") == "divide and conquer"
    assert norm("CHAPTER 3.: DIVIDE-AND-CONQUER") == "chapter 3.: divide and conquer"
    assert norm("divide and conquer") in norm("CHAPTER 3.: DIVIDE-AND-CONQUER")


def test_figure_caption_less_than_real_definition(retrieval_engine):
    """Figure captions must be penalized (0.4x) and score significantly less than real definitions with description cues."""
    query = QueryUnderstanding(
        raw_query="what is divide and conquer",
        normalized_query="what is divide and conquer",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["divide and conquer"],
        primary_concept="divide and conquer",
    )

    caption_row = {
        "chunk_id": "c_caption",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 202,
        "section": "Chapter 3: Divide-and-Conquer",
        "locator": "Chapter 3: Divide-and-Conquer · p.202",
        "bm25_score": -9.0,
        "text": "CHAPTER 3: DIVIDE-AND-CONQUER\nFigure 3.6 Convex hull: an example of computational geometry.",
        "meta_heading": "Chapter 3: Divide-and-Conquer",
        "meta_section_type": "body",
        "meta_page_label": "202",
    }

    definition_row = {
        "chunk_id": "c_definition",
        "document_id": "doc_2",
        "paper_id": "paper_2",
        "page_start": 51,
        "section": "Chapter 2: Getting Started",
        "locator": "Chapter 2: Getting Started · p.51",
        "bm25_score": -9.0,
        "text": "The divide-and-conquer paradigm involves three steps at each level of recursion: Divide, Conquer, and Combine.",
        "meta_heading": "Chapter 2: Getting Started",
        "meta_section_type": "body",
        "meta_page_label": "51",
    }

    trace_caption = retrieval_engine._score_candidate(caption_row, query, set())
    trace_def = retrieval_engine._score_candidate(definition_row, query, set())

    # Caption must be penalized with caption_penalty=0.4
    assert trace_caption.caption_penalty == 0.4
    # Definition must receive description boost (1.8x)
    assert trace_def.description_boost == 1.8
    # Real definition score must far exceed caption score
    assert trace_def.final_score > trace_caption.final_score * 3.0


def test_chapter_only_match_is_capped(retrieval_engine):
    """Chapter-level label match without subsection or first-line match is capped at 1.15x; absent concept in body caps at 1.0."""
    query = QueryUnderstanding(
        raw_query="what is divide and conquer",
        normalized_query="what is divide and conquer",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["divide and conquer"],
        primary_concept="divide and conquer",
    )

    # 1. Concept absent from body text: heading boost capped at 1.0
    row_absent = {
        "chunk_id": "c_absent",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 100,
        "section": "Chapter 3: Divide-and-Conquer",
        "locator": "Chapter 3: Divide-and-Conquer · p.100",
        "bm25_score": 0.0,
        "text": "Chapter 3: Divide-and-Conquer\nThis section discusses purely geometric hulls and polygon triangulation.",
        "meta_heading": "Chapter 3: Divide-and-Conquer",
        "meta_section_type": "body",
        "meta_page_label": "100",
    }
    trace_absent = retrieval_engine._score_candidate(row_absent, query, set())
    assert trace_absent.heading_boost == 1.0

    # 2. Concept present in body text, but only chapter-level heading matches: capped at 1.15x
    row_chapter = {
        "chunk_id": "c_chap",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 101,
        "section": "Chapter 3: Divide-and-Conquer",
        "locator": "Chapter 3: Divide-and-Conquer · p.101",
        "bm25_score": 0.0,
        "text": "Chapter 3: Divide-and-Conquer\nSome introductory remarks.\nLater in the body we mention divide-and-conquer recurrence equations.",
        "meta_heading": "Chapter 3: Divide-and-Conquer",
        "meta_section_type": "body",
        "meta_page_label": "101",
    }
    trace_chapter = retrieval_engine._score_candidate(row_chapter, query, set())
    assert trace_chapter.heading_boost <= 1.15


def test_garbage_chunk_penalised(retrieval_engine):
    """Chunks with low alphabetic-character ratio (< 0.6) receive a 0.2x garbage penalty."""
    query = QueryUnderstanding(
        raw_query="what is divide and conquer",
        normalized_query="what is divide and conquer",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["divide and conquer"],
        primary_concept="divide and conquer",
    )

    garbage_row = {
        "chunk_id": "c_garbage",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 8,
        "section": "Contents",
        "locator": "Contents · p.8",
        "bm25_score": 0.0,
        "text": ".... 145 ....... 230 .... 12 34 56 78 90 ....",
        "meta_heading": "Contents",
        "meta_section_type": "front_matter",
        "meta_page_label": "8",
    }
    trace_garbage = retrieval_engine._score_candidate(garbage_row, query, set())
    assert trace_garbage.garbage_penalty == 0.2


def test_non_definition_intents_caption_penalty_unchanged(retrieval_engine):
    """Intents other than DEFINITION and COMPARISON (e.g. COMPLEXITY, OTHER) do NOT trigger caption penalty."""
    query_complexity = QueryUnderstanding(
        raw_query="complexity of merge sort",
        normalized_query="complexity of merge sort",
        intent=ResearchIntent.COMPLEXITY,
        target_concepts=["merge sort"],
        primary_concept="merge sort",
    )

    caption_row = {
        "chunk_id": "c_caption_comp",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 45,
        "section": "Chapter 2: Getting Started",
        "locator": "Chapter 2: Getting Started · p.45",
        "bm25_score": 0.0,
        "text": "Figure 2.5 The recurrence tree for merge sort showing O(n lg n) running time.",
        "meta_heading": "Chapter 2: Getting Started",
        "meta_section_type": "body",
        "meta_page_label": "45",
    }
    trace = retrieval_engine._score_candidate(caption_row, query_complexity, set())
    assert trace.caption_penalty == 1.0


def test_definition_composer_chooses_passage_over_caption():
    """When no formal 'X is...' sentence is found, composer chooses a real passage over a caption and uses '### How the selected sources describe it'."""
    from rag.intelligence.answer_composer import ResearchAnswerComposer
    from rag.intelligence.confidence_evaluator import ConfidenceReport, ConfidenceLevel
    from rag.retrieval.query import RetrievedSource

    composer = ResearchAnswerComposer()
    query = QueryUnderstanding(
        raw_query="what is divide and conquer",
        normalized_query="what is divide and conquer",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["divide and conquer"],
        primary_concept="divide and conquer",
    )

    s1_caption = RetrievedSource(
        source_id="S1",
        chunk_id="c_caption",
        document_id="doc_1",
        paper_id="paper_1",
        page_start=202,
        page_end=202,
        section="3.8 Convex Hull",
        title="Algorithms Textbook",
        filename="textbook.pdf",
        locator="3.8 Convex Hull · p.202",
        text="Figure 3.6 Convex hull: A divide-and-conquer strategy for finding the hull of a planar point set.",
        score=2.5,
    )

    s2_passage = RetrievedSource(
        source_id="S2",
        chunk_id="c_passage",
        document_id="doc_1",
        paper_id="paper_1",
        page_start=51,
        page_end=51,
        section="2.3 Designing Algorithms",
        title="Algorithms Textbook",
        filename="textbook.pdf",
        locator="2.3 Designing Algorithms · p.51",
        text="The divide-and-conquer paradigm involves three steps at each level of the recursion: Divide the problem into subproblems. Conquer the subproblems recursively. Combine the solutions.",
        score=7.0,
    )

    confidence = ConfidenceReport(
        overall_confidence_score=0.9,
        level=ConfidenceLevel.STRONG,
        is_definitive_answer=True,
        top_source=s2_passage,
        top_definition=None,
    )

    answer = composer.compose(query=query, sources=[s1_caption, s2_passage], confidence=confidence)
    assert "### How the selected sources describe it" in answer.markdown_content
    assert "The sources describe this topic but do not state a one-line definition." in answer.markdown_content
    assert "[S2]" in answer.markdown_content
    assert "divide-and-conquer paradigm involves three steps" in answer.markdown_content
    assert "Figure 3.6" not in answer.markdown_content


def test_pseudocode_penalty_applied_for_listings(retrieval_engine):
    """Listing with >=3 numbered lines or >=2 ':=' / '//' lines receives a 0.5x penalty for DEFINITION."""
    query = QueryUnderstanding(
        raw_query="what is a red-black tree",
        normalized_query="what is a red-black tree",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["red-black tree"],
        primary_concept="red-black tree",
    )

    # 1. Numbered lines listing
    listing_text = (
        "RB-INSERT(T, z)\n"
        "1  y = T.nil\n"
        "2  x = T.root\n"
        "3  while x != T.nil\n"
        "4      y = x\n"
    )
    row_listing = {
        "chunk_id": "c_listing",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 315,
        "section": "13.3 Insertion",
        "locator": "13.3 Insertion · p.315",
        "bm25_score": 0.0,
        "text": listing_text,
        "meta_heading": "13.3 Insertion",
        "meta_section_type": "body",
        "meta_page_label": "315",
    }
    trace_listing = retrieval_engine._score_candidate(row_listing, query, set())
    assert trace_listing.pseudocode_penalty == 0.5

    # 2. Syntax assignment / comment lines listing
    syntax_text = (
        "Algorithm Step:\n"
        "x := root // find position\n"
        "y := nil // previous node\n"
        "A red-black tree is balanced."
    )
    row_syntax = {
        "chunk_id": "c_syntax",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 316,
        "section": "13.3 Insertion",
        "locator": "13.3 Insertion · p.316",
        "bm25_score": 0.0,
        "text": syntax_text,
        "meta_heading": "13.3 Insertion",
        "meta_section_type": "body",
        "meta_page_label": "316",
    }
    trace_syntax = retrieval_engine._score_candidate(row_syntax, query, set())
    assert trace_syntax.pseudocode_penalty == 0.5

    # 3. Normal prose is not penalized
    prose_text = (
        "A red-black tree is a binary search tree that satisfies the red-black properties.\n"
        "Every node is either red or black, and the root is always black."
    )
    row_prose = {
        "chunk_id": "c_prose",
        "document_id": "doc_1",
        "paper_id": "paper_1",
        "page_start": 308,
        "section": "13.1 Properties",
        "locator": "13.1 Properties · p.308",
        "bm25_score": 0.0,
        "text": prose_text,
        "meta_heading": "13.1 Properties",
        "meta_section_type": "body",
        "meta_page_label": "308",
    }
    trace_prose = retrieval_engine._score_candidate(row_prose, query, set())
    assert trace_prose.pseudocode_penalty == 1.0


def test_multidoc_fairness_guarantees_representation_in_top_5(tmp_path):
    """For DEFINITION and COMPARISON queries, each active document with a matching concept candidate is guaranteed in top 5."""
    import sqlite3

    db_file = tmp_path / "lexical_test.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        """
        CREATE VIRTUAL TABLE lexical_chunks USING fts5(
            chunk_id UNINDEXED,
            paper_id UNINDEXED,
            document_id UNINDEXED,
            section UNINDEXED,
            page_start UNINDEXED,
            page_end UNINDEXED,
            title UNINDEXED,
            filename UNINDEXED,
            locator UNINDEXED,
            collection_name UNINDEXED,
            owner_id UNINDEXED,
            text
        )
        """
    )

    # Insert 6 chunks for doc_a (high BM25 hits)
    for i in range(1, 7):
        conn.execute(
            """
            INSERT INTO lexical_chunks (chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, collection_name, owner_id, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"a_{i}", "p_a", "doc_a", f"Section {i}", i * 10, i * 10, "Book A", "book_a.pdf", f"Section {i} · p.{i*10}", "default", "user1",
                f"divide and conquer divide and conquer divide and conquer chunk text {i} about algorithm analysis."
            )
        )

    # Insert 1 chunk for doc_b (lower frequency hit but has concept in body)
    conn.execute(
        """
        INSERT INTO lexical_chunks (chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, collection_name, owner_id, text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "b_1", "p_b", "doc_b", "Introduction", 5, 5, "Book B", "book_b.pdf", "Introduction · p.5", "default", "user1",
            "The divide and conquer approach splits the problem into smaller instances."
        )
    )
    conn.commit()
    conn.close()

    engine = ExplainableRetrievalEngine(db_path=db_file, collection_name="default")
    query = QueryUnderstanding(
        raw_query="what is divide and conquer",
        normalized_query="what is divide and conquer",
        intent=ResearchIntent.DEFINITION,
        target_concepts=["divide and conquer"],
        primary_concept="divide and conquer",
    )

    sources, traces = engine.retrieve(query=query, document_ids=["doc_a", "doc_b"], top_k=5, owner_id="user1")

    # Both doc_a and doc_b must have representation in the top 5
    doc_ids_in_top5 = {s.document_id for s in sources[:5]}
    assert "doc_a" in doc_ids_in_top5
    assert "doc_b" in doc_ids_in_top5
    assert any(s.chunk_id == "b_1" for s in sources[:5])



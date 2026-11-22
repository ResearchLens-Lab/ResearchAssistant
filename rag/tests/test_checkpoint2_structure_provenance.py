"""
Tests for Checkpoint 2: Structure and Provenance Hardening.
Verifies rejection of TOC decomposition, greedy continuation, cross-page mid-sentence headings,
and page-scoped physical provenance resolution.
"""

from rag.chunking.structure_chunker import StructureAwareChunker
from rag.ingestion.document_normalizer import DocumentMetadata, DocumentNormalizer, Page, Section
from rag.ingestion.structure_extractor import (
    DocumentSectionNode,
    SectionType,
    StructureExtractor,
    is_valid_heading_title,
    is_valid_title_continuation,
)


def test_is_valid_heading_title_rejections():
    # 1. Cross-page sentence continuation starting with closing parenthesis
    assert not is_valid_heading_title("), and using a search engine to quickly find pages on which particular")

    # 2. OCR repetitive artifacts / table cells
    assert not is_valid_heading_title("eeees")
    assert not is_valid_heading_title("aaaa")

    # 3. Exercise and problem instructions
    assert not is_valid_heading_title("Exercise 4. Design a data structure for storing intervals")
    assert not is_valid_heading_title("Review Questions")
    assert not is_valid_heading_title("Self-test Problems")

    # 4. Table markup and bracket leaks
    assert not is_valid_heading_title("| Backtracking |")
    assert not is_valid_heading_title("[Dene este due |")

    # 5. Sentence continuations starting with lowercase or conjunctions
    assert not is_valid_heading_title("and using a search engine")
    assert not is_valid_heading_title("which proves the theorem")

    # 6. Valid heading titles must be accepted
    assert is_valid_heading_title("Introduction to Algorithms")
    assert is_valid_heading_title("Binary Search Trees")
    assert is_valid_heading_title("Elementary Data Structures")
    assert is_valid_heading_title("Dynamic Programming")


def test_toc_node_not_decomposed_into_fake_sections():
    extractor = StructureExtractor()

    # Create a base TOC node spanning pages 6 to 13 (like Cormen's Contents)
    toc_node = DocumentSectionNode(
        title="Contents",
        level=1,
        page_start=6,
        page_end=13,
        section_type=SectionType.FRONT_MATTER,
    )

    # Page 7 contains table of contents lines with chapter numbers
    page_texts = [
        (6, "Contents\n\nPreface ... 12\n"),
        (7, "6 Heapsort 151\n6.1 Heaps 151\n10 Elementary Data Structures 232\n10.1 Stacks and queues 232\n"),
        (13, "35 Approximation Algorithms 1106\nIndex 1231\n"),
    ]

    enriched = extractor._enrich_with_subsections([toc_node], page_texts, {})
    # Must NOT decompose the TOC node into fake body sections on page 7
    assert len(enriched) == 1
    assert enriched[0].title == "Contents"
    assert enriched[0].page_start == 6
    assert enriched[0].page_end == 13


def test_normalizer_rejects_cross_page_sentence_as_heading():
    normalizer = DocumentNormalizer()
    pages = [
        Page(page_number=1, text="This topic is discussed in\n\nChapter 24), and using a search engine to quickly find pages on which particular keywords appear."),
    ]
    meta = DocumentMetadata(
        paper_id="p1",
        document_id="d1",
        owner_id="u1",
        title="Sample Paper",
    )
    doc = normalizer.normalize(pages, meta)
    # The cross-page sentence must NOT become a Section named "Chapter 24: ), and using a search engine..."
    for sec in doc.sections:
        assert "search engine" not in sec.name
        assert "eeees" not in sec.name


def test_find_page_range_scopes_to_candidate_pages():
    chunker = StructureAwareChunker()
    pages = [
        Page(page_number=7, text="Contents: 10 Elementary Data Structures 232"),
        Page(page_number=253, text="Chapter 10\n\nElementary Data Structures\n\nIn this chapter, we investigate elementary data structures such as stacks, queues, and linked lists."),
    ]

    chunk_text = "In this chapter, we investigate elementary data structures such as stacks, queues, and linked lists."
    # When searching for this body chunk with section page_start=253, page_end=255
    p_start, p_end, resolved = chunker._find_page_range(
        document_text="\n\n".join(p.text for p in pages),
        chunk_text=chunk_text,
        page_offsets=[(7, 0), (253, 50)],
        fallback_start=253,
        fallback_end=255,
        pages=pages,
    )

    assert p_start == 253
    assert p_end == 253
    assert resolved is True

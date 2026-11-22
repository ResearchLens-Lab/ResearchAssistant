import pytest
from rag.ingestion.structure_extractor import (
    is_valid_title_continuation,
    normalize_section_label,
    StructureExtractor,
)
from rag.chunking.structure_chunker import StructureAwareChunker
from rag.ingestion.document_normalizer import NormalizedDocument, Section, Page, DocumentMetadata


def test_is_valid_title_continuation():
    # Long tutorial sentence ending with function word 'a' must NOT be joined
    long_tutorial = "All the chapters in Part I and the Appendices are written with a"
    assert is_valid_title_continuation(long_tutorial) is False

    # Valid chapter subtitle must be joined
    assert is_valid_title_continuation("Divide-and-Conquer") is True

    # Punctuation termination must NOT be joined
    assert is_valid_title_continuation("Introduction.") is False

    # Lowercase function word ending must NOT be joined
    assert is_valid_title_continuation("The Role of Algorithms in") is False
    assert is_valid_title_continuation("The Role of Algorithms for") is False

    # Over 60 characters or over 8 words must NOT be joined
    assert is_valid_title_continuation("One Two Three Four Five Six Seven Eight Nine Ten Words") is False


def test_structure_extractor_heading_continuation():
    # StructureExtractor heading joining rule:
    # "Part I:" + long tutorial sentence is NOT a title.
    # "Chapter 3" + "Divide-and-Conquer" IS a title.
    extractor = StructureExtractor()
    extracted_pages = [
        (1, "Part I:\nAll the chapters in Part I and the Appendices are written with a tutorial flavor.\nSome content."),
        (2, "Chapter 3\nDivide-and-Conquer\nThis chapter introduces the divide-and-conquer paradigm.\n"),
    ]
    nodes = extractor._build_from_page_text(extracted_pages, {})
    titles = [n.title for n in nodes]

    # "Part I:" + tutorial sentence is NOT joined as a title
    assert not any("All the chapters in Part I" in t for t in titles)

    # "Chapter 3" + "Divide-and-Conquer" IS joined as a title
    assert any("Chapter 3: Divide-and-Conquer" in t for t in titles)


def test_normalize_section_label():
    # Stray '.' before ':' and all-uppercase -> title-cased preserving hyphens
    assert normalize_section_label("CHAPTER 3.: DIVIDE-AND-CONQUER") == "Chapter 3: Divide-and-Conquer"

    # Already mixed-case is preserved
    assert normalize_section_label("Chapter 4: Divide-and-Conquer") == "Chapter 4: Divide-and-Conquer"

    # Section with number and hyphen
    assert normalize_section_label("SECTION 2.1: MERGE-SORT") == "Section 2.1: Merge-Sort"

    # Empty or None handling
    assert normalize_section_label("") == ""


def test_structure_chunker_merges_page_break_blocks():
    # Block 1 lacks terminal punctuation; Block 2 begins lowercase (page-break artefact)
    sec_text = "The quick brown fox jumps over\n\nthe lazy dog that was sleeping in the yard."
    section = Section(name="Introduction", text=sec_text, page_start=1, page_end=1)
    pages = [Page(page_number=1, text=sec_text)]
    doc = NormalizedDocument(
        owner_id="test_owner",
        document_id="doc_test_1",
        paper_id="paper_test_1",
        title="Test Document",
        total_pages=1,
        pages=pages,
        sections=[section],
        metadata=DocumentMetadata(
            paper_id="paper_test_1",
            document_id="doc_test_1",
            owner_id="test_owner",
            title="Test Document",
            source_format="pdf",
        ),
        raw_text=sec_text,
    )

    chunker = StructureAwareChunker(target_words=100, overlap_words=20)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    assert "jumps over the lazy dog" in chunks[0].text


def test_structure_chunker_handles_orphan_fragments():
    chunker = StructureAwareChunker(target_words=5, overlap_words=0)

    # Paragraph 1 ends with sentence; Paragraph 2 starts with orphan fragment "flavor."
    sec_text = (
        "Part I is written with a rich tutorial.\n\n"
        "flavor. The Role of Algorithms in Computing begins with an introduction to foundational models."
    )
    section = Section(name="Overview", text=sec_text, page_start=1, page_end=1)
    pages = [Page(page_number=1, text=sec_text)]
    doc = NormalizedDocument(
        owner_id="test_owner",
        document_id="doc_test_2",
        paper_id="paper_test_2",
        title="Test Document 2",
        total_pages=1,
        pages=pages,
        sections=[section],
        metadata=DocumentMetadata(
            paper_id="paper_test_2",
            document_id="doc_test_2",
            owner_id="test_owner",
            title="Test Document 2",
            source_format="pdf",
        ),
        raw_text=sec_text,
    )

    chunks = chunker.chunk_document(doc)
    # The orphan fragment "flavor." should be appended to the first chunk
    assert any(c.text.endswith("flavor.") for c in chunks)
    assert any(c.text.startswith("The Role of Algorithms in Computing") for c in chunks)
    assert all(not c.text.startswith("flavor.") for c in chunks)


def test_structure_chunker_orphan_safety_rules():
    """Validates that numbered headings, abbreviations, and figures are NEVER treated as orphans,
    while ligature/word fragments are correctly attached to previous chunk."""
    chunker = StructureAwareChunker(target_words=5, overlap_words=0)

    def _chunk_text(t: str, sec_name: str = "Test Section"):
        doc = NormalizedDocument(
            owner_id="test_owner",
            document_id="doc_t",
            paper_id="paper_t",
            title="Doc",
            total_pages=1,
            pages=[Page(page_number=1, text=t)],
            sections=[Section(name=sec_name, text=t, page_start=1, page_end=1)],
            metadata=DocumentMetadata(paper_id="paper_t", document_id="doc_t", owner_id="test_owner", title="Doc", source_format="pdf"),
            raw_text=t,
        )
        return chunker.chunk_document(doc)

    # 1. "3.5 QUICKSORT The divide-and-conquer approach..." unchanged (starts with digit)
    t1 = "Previous paragraph ends here with complete text.\n\n3.5 QUICKSORT The divide-and-conquer approach is used."
    c1 = _chunk_text(t1)
    assert any(c.text.startswith("3.5 QUICKSORT") for c in c1)
    assert all(not c.text.endswith("3.") for c in c1)

    # 2. "1. Introduction ..." unchanged (starts with digit)
    t2 = "Section finishes.\n\n1. Introduction to sorting algorithms and their design principles."
    c2 = _chunk_text(t2)
    assert any(c.text.startswith("1. Introduction") for c in c2)

    # 3. "e.g. sorting is..." unchanged (known abbreviation)
    t3 = "Algorithms solve problems efficiently.\n\ne.g. sorting is a fundamental computational task in computer science."
    c3 = _chunk_text(t3)
    assert any(c.text.startswith("e.g. sorting is") for c in c3)

    # 4. "Fig. 3.6 Convex hull" unchanged (starts with uppercase / figure)
    t4 = "Geometric algorithms are discussed below.\n\nFig. 3.6 Convex hull: an example of divide-and-conquer."
    c4 = _chunk_text(t4)
    assert any(c.text.startswith("Fig. 3.6 Convex hull") for c in c4)

    # 5. "flavor. The Role of Algorithms in Computing" -> "flavor." appended to previous chunk
    t5 = "Part I is written with a rich tutorial.\n\nflavor. The Role of Algorithms in Computing begins."
    c5 = _chunk_text(t5)
    assert any(c.text.endswith("flavor.") for c in c5)
    assert any(c.text.startswith("The Role of Algorithms in Computing") for c in c5)

    # 6. "of the input. Next we..." with a previous chunk is merged
    t6 = "The algorithm operates on subsets.\n\nof the input. Next we consider the base cases of recursion."
    c6 = _chunk_text(t6)
    assert any(c.text.endswith("of the input.") for c in c6)
    assert any(c.text.startswith("Next we consider the base cases") for c in c6)


def test_structure_chunker_removes_running_header():
    """Running headers matching section label or ^(chapter|part) are removed from text and stored in metadata."""
    chunker = StructureAwareChunker(target_words=50, overlap_words=5)

    text = "CHAPTER 3.: DIVIDE-AND-CONQUER\nIn this chapter we explore divide and conquer strategies in detail."
    doc = NormalizedDocument(
        owner_id="test_owner",
        document_id="doc_rh",
        paper_id="paper_rh",
        title="Doc RH",
        total_pages=1,
        pages=[Page(page_number=1, text=text)],
        sections=[Section(name="Chapter 3: Divide-and-Conquer", text=text, page_start=1, page_end=1)],
        metadata=DocumentMetadata(paper_id="paper_rh", document_id="doc_rh", owner_id="test_owner", title="Doc RH", source_format="pdf"),
        raw_text=text,
    )
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("In this chapter we explore")
    assert "CHAPTER 3.: DIVIDE-AND-CONQUER" not in chunks[0].text
    assert chunks[0].metadata.extra.get("running_header") == "CHAPTER 3.: DIVIDE-AND-CONQUER"


def test_text_cleaning_safety_rules():
    """Verify hyphenation rejoining and running header collapse / stray page number safety."""
    from rag.intelligence.answer_composer import clean_passage_text
    from rag.ingestion.document_normalizer import DocumentNormalizer

    # 1. Hyphenation rejoining
    assert clean_passage_text("ez-\ntreme") == "eztreme"
    assert clean_passage_text("divide-\nand-conquer") == "divide-and-conquer"
    assert clean_passage_text("well-\nknown") == "wellknown"

    normalizer = DocumentNormalizer()
    assert normalizer._clean_text("ez-\ntreme") == "eztreme"
    assert normalizer._clean_text("divide-\nand-conquer") == "divide-and-conquer"
    assert normalizer._clean_text("well-\nknown") == "wellknown"

    # 2. Duplicated running header collapse
    collapsed = clean_passage_text("13.4 Deletion 323 13.4 Deletion Like the other basic operations on an n-node red-black tree")
    assert collapsed == "13.4 Deletion Like the other basic operations on an n-node red-black tree"

    # 3. Stray page number must NOT fire inside a sentence
    sentence = "Section 4 has 12 nodes 5 Of these"
    assert clean_passage_text(sentence) == "Section 4 has 12 nodes 5 Of these"


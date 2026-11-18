import pytest
from rag.chunking.structure_chunker import StructureAwareChunker
from rag.ingestion.document_normalizer import NormalizedDocument, Section, Page, DocumentMetadata


def test_chunk_bounding_and_deduplication():
    chunker = StructureAwareChunker(target_words=350, overlap_words=50)

    para_short = "This is a brief introductory clause that has very few words."
    para_normal = " ".join(["algorithm"] * 100)
    para_giant = " ".join(["computation"] * 900)

    pages = [
        Page(page_number=1, text=para_short, width=612.0, height=792.0),
        Page(page_number=2, text=para_normal + "\n\n" + para_giant, width=612.0, height=792.0),
    ]
    sections = [
        Section(name="Chapter 1: Intro", page_start=1, page_end=1, text=para_short + "\n\n" + para_normal),
        Section(name="Chapter 2: Algorithms", page_start=2, page_end=2, text=para_giant),
    ]
    doc = NormalizedDocument(
        document_id="doc_bounds_test",
        paper_id="paper_bounds_test",
        owner_id="test_owner",
        title="Bounds Test Document",
        pages=pages,
        sections=sections,
        metadata=DocumentMetadata(
            paper_id="paper_bounds_test",
            document_id="doc_bounds_test",
            owner_id="test_owner",
            filename="test.pdf",
            total_pages=2,
        ),
    )

    chunks = chunker.chunk(doc)

    assert len(chunks) >= 2
    # 0 chunks have > 800 words
    for idx, c in enumerate(chunks):
        word_count = len(c.text.split())
        assert word_count <= 800, f"Chunk {idx} exceeds 800 words: {word_count}"

    # Verify no tiny orphan chunks < 20 words (except title page if alone)
    non_title_chunks = [c for c in chunks if (c.metadata.page_start or 1) > 1]
    for idx, c in enumerate(non_title_chunks):
        word_count = len(c.text.split())
        assert word_count >= 20, f"Non-title chunk {idx} has fewer than 20 words: {word_count}"

    # Verify average chunk size
    total_words = sum(len(c.text.split()) for c in chunks)
    avg_words = total_words / len(chunks)
    assert 150 <= avg_words <= 600, f"Average chunk words {avg_words} out of expected range"


def test_chunk_bounds_on_reindexed_cormen_simulation():
    # Simulate a 10-page chapter of Cormen
    pages = []
    sections = []

    for p in range(1, 11):
        para = " ".join([f"In section 13.{p}, a red-black tree satisfies five properties to maintain logarithmic height."] * 6)
        page_text = "\n\n".join([para] * 8)
        pages.append(Page(page_number=p, text=page_text, width=612.0, height=792.0))
        sections.append(Section(name=f"Section 13.{p}", page_start=p, page_end=p, text=page_text))

    doc = NormalizedDocument(
        document_id="doc_cormen_sim",
        paper_id="paper_cormen_sim",
        owner_id="test_owner",
        title="Introduction to Algorithms (Cormen)",
        pages=pages,
        sections=sections,
        metadata=DocumentMetadata(
            paper_id="paper_cormen_sim",
            document_id="doc_cormen_sim",
            owner_id="test_owner",
            filename="cormen.pdf",
            total_pages=10,
        ),
    )

    chunker = StructureAwareChunker(target_words=350, overlap_words=50)
    chunks = chunker.chunk(doc)

    word_counts = [len(c.text.split()) for c in chunks]
    assert len(chunks) > 5

    # 1. 0 chunks have < 20 words (except title page)
    short_chunks = [w for idx, w in enumerate(word_counts) if w < 20 and (chunks[idx].metadata.page_start or 1) > 1]
    assert len(short_chunks) == 0, f"Found chunks < 20 words: {short_chunks}"

    # 2. 0 chunks have > 800 words
    giant_chunks = [w for w in word_counts if w > 800]
    assert len(giant_chunks) == 0, f"Found chunks > 800 words: {giant_chunks}"

    # 3. Average chunk size is 250-450 words
    avg_size = sum(word_counts) / len(word_counts)
    assert 250 <= avg_size <= 450, f"Expected average 250-450 words, got: {avg_size}"

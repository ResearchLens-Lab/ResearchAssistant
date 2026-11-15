"""
Unit tests for Document Normalization, Metadata Mapping, and Chunking.
Verifies page and section preservation and deterministic IDs.
"""

import pytest
from rag.ingestion.document_normalizer import DocumentNormalizer, Page, DocumentMetadata
from rag.ingestion.metadata_mapper import MetadataMapper
from rag.chunking.chunker import DocumentChunker
from rag.chunking.metadata import ChunkMetadata, DocumentChunk


def test_metadata_mapper():
    raw = {
        "title": "Attention Is All You Need",
        "authors": "Vaswani, Shazeer, Parmar",
        "year": "2017",
        "doi": "10.48550/arXiv.1706.03762",
    }
    meta = MetadataMapper.map_metadata(raw_metadata=raw, paper_id="paper_101")
    assert meta.paper_id == "paper_101"
    assert meta.title == "Attention Is All You Need"
    assert len(meta.authors) == 3
    assert meta.year == 2017
    assert meta.doi == "10.48550/arXiv.1706.03762"


def test_document_normalizer_section_and_page_extraction():
    normalizer = DocumentNormalizer()
    pages = [
        Page(page_number=1, text="Title\n\nAbstract\nThis is the abstract.\n\n1. Introduction\nIntroductory text here."),
        Page(page_number=2, text="2. Methodology\nWe describe our attention algorithm.\n\n3. Results\nResults are strong."),
    ]
    meta = DocumentMetadata(
        paper_id="paper_test",
        document_id="doc_test",
        title="Test Paper",
        owner_id="test_user_fixture",
    )
    doc = normalizer.normalize(pages=pages, metadata=meta)

    assert doc.total_pages == 2
    assert len(doc.sections) >= 3
    section_names = [s.name for s in doc.sections]
    assert "Abstract" in section_names or "Header / Abstract" in section_names
    assert "Introduction" in section_names
    assert "Methodology" in section_names


def test_chunker_preserves_page_numbers_and_sections(sample_document):
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_document(sample_document)

    assert len(chunks) > 0
    for chunk in chunks:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.paper_id == "paper_attention_2017"
        assert chunk.metadata.document_id == "doc_attention_001"
        assert chunk.page_start >= 1
        assert chunk.page_end >= chunk.page_start
        assert chunk.metadata.chunk_id.startswith("paper_attention_2017_c")
        assert len(chunk.text.strip()) > 0
        assert chunk.section != ""


def test_chunk_ids_are_unique_per_document_even_within_one_paper(sample_document):
    first = sample_document.model_copy(deep=True)
    first.document_id = "doc_first"
    first.metadata.document_id = "doc_first"
    second = sample_document.model_copy(deep=True)
    second.document_id = "doc_second"
    second.metadata.document_id = "doc_second"

    first_chunks = DocumentChunker(chunk_size=100, chunk_overlap=20).chunk_document(first)
    second_chunks = DocumentChunker(chunk_size=100, chunk_overlap=20).chunk_document(second)

    assert first_chunks and second_chunks
    assert {chunk.chunk_id for chunk in first_chunks}.isdisjoint(
        {chunk.chunk_id for chunk in second_chunks}
    )


def test_chunk_metadata_chroma_serialization():
    meta = ChunkMetadata(
        chunk_id="paper_1_c0001_p1-2",
        paper_id="paper_1",
        document_id="doc_1",
        page_start=1,
        page_end=2,
        section="Methodology",
        chunk_index=1,
        token_count=120,
        title="Attention Paper",
        owner_id="test_user_fixture",
    )
    chroma_dict = meta.to_chroma_metadata()
    assert chroma_dict["chunk_id"] == "paper_1_c0001_p1-2"
    assert chroma_dict["page_start"] == 1
    assert chroma_dict["page_end"] == 2
    assert chroma_dict["section"] == "Methodology"

    # Reconstruct
    reconstructed = ChunkMetadata.from_chroma_metadata(chroma_dict)
    assert reconstructed.chunk_id == meta.chunk_id
    assert reconstructed.page_start == 1
    assert reconstructed.page_end == 2
    assert reconstructed.section == "Methodology"

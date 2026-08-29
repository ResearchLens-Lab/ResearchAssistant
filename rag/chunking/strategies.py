"""
Chunking strategies for research papers.
Preserves section semantics, sentence/paragraph boundaries, and page provenance.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple
from rag.ingestion.document_normalizer import NormalizedDocument, Section, Page
from rag.chunking.metadata import DocumentChunk, ChunkMetadata

logger = logging.getLogger(__name__)


class BaseChunkingStrategy(ABC):
    """
    Abstract chunking strategy interface.
    """

    @abstractmethod
    def chunk(self, document: NormalizedDocument) -> List[DocumentChunk]:
        """
        Splits a normalized document into a list of DocumentChunk instances.
        """
        pass


class SectionAwareChunkingStrategy(BaseChunkingStrategy):
    """
    Chunks documents while respecting academic sections and tracking page numbers.
    Uses token/word estimation with sliding window overlap.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: NormalizedDocument) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        # Pre-build page word offsets to accurately resolve page numbers for any text offset
        page_offsets = self._build_page_index(document.pages)

        # If document has detected sections, chunk each section independently to prevent cross-section bleeding
        if document.sections:
            for section in document.sections:
                section_chunks = self._chunk_section(
                    document=document,
                    section=section,
                    page_offsets=page_offsets,
                    start_chunk_idx=chunk_idx,
                )
                chunks.extend(section_chunks)
                chunk_idx += len(section_chunks)
        else:
            # Fallback to full document page stream
            fallback_section = Section(
                name="Main Content",
                page_start=document.pages[0].page_number if document.pages else 1,
                page_end=document.pages[-1].page_number if document.pages else 1,
                text=document.full_text,
            )
            chunks = self._chunk_section(
                document=document,
                section=fallback_section,
                page_offsets=page_offsets,
                start_chunk_idx=0,
            )

        return chunks

    def _build_page_index(self, pages: List[Page]) -> List[Tuple[int, int, int]]:
        """
        Returns list of tuples: (page_number, start_char_index, end_char_index)
        """
        index: List[Tuple[int, int, int]] = []
        current_offset = 0
        for page in pages:
            length = len(page.text)
            index.append((page.page_number, current_offset, current_offset + length))
            current_offset += length + 2  # accounted for '\n\n' separator
        return index

    def _find_page_range_for_text(
        self,
        document_text: str,
        chunk_text: str,
        page_offsets: List[Tuple[int, int, int]],
        fallback_start: int,
        fallback_end: int,
    ) -> Tuple[int, int]:
        """
        Finds the exact start and end page for a chunk snippet.
        """
        if not page_offsets:
            return fallback_start, fallback_end

        start_pos = document_text.find(chunk_text[:100])
        if start_pos == -1:
            return fallback_start, fallback_end

        end_pos = start_pos + len(chunk_text)

        p_start = fallback_start
        p_end = fallback_end
        found_start = False

        for page_num, p_from, p_to in page_offsets:
            if not found_start and start_pos <= p_to:
                p_start = page_num
                found_start = True
            if end_pos <= p_to:
                p_end = page_num
                break
            p_end = page_num

        return max(1, p_start), max(p_start, p_end)

    def _chunk_section(
        self,
        document: NormalizedDocument,
        section: Section,
        page_offsets: List[Tuple[int, int, int]],
        start_chunk_idx: int,
    ) -> List[DocumentChunk]:
        text = section.text.strip()
        if not text:
            return []

        # Split into sentence-like or paragraph units
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        units: List[str] = []
        for p in paragraphs:
            # If paragraph is long, split by sentences
            if len(p.split()) > self.chunk_size:
                sentences = re.split(r"(?<=[.?!])\s+", p)
                units.extend([s.strip() for s in sentences if s.strip()])
            else:
                units.append(p)

        section_chunks: List[DocumentChunk] = []
        current_words: List[str] = []
        current_unit_texts: List[str] = []
        doc_full_text = document.full_text

        for unit in units:
            unit_words = unit.split()
            if len(current_words) + len(unit_words) > self.chunk_size and current_words:
                chunk_text = " ".join(current_words).strip()
                p_start, p_end = self._find_page_range_for_text(
                    document_text=doc_full_text,
                    chunk_text=chunk_text,
                    page_offsets=page_offsets,
                    fallback_start=section.page_start,
                    fallback_end=section.page_end,
                )

                chunk_idx = start_chunk_idx + len(section_chunks)
                chunk_id = f"{document.paper_id}_c{chunk_idx:04d}_p{p_start}-{p_end}"

                meta = ChunkMetadata(
                    chunk_id=chunk_id,
                    paper_id=document.paper_id,
                    document_id=document.document_id,
                    page_start=p_start,
                    page_end=p_end,
                    section=section.name,
                    chunk_index=chunk_idx,
                    token_count=len(current_words),
                    title=document.title,
                )
                section_chunks.append(DocumentChunk(text=chunk_text, metadata=meta))

                # Slide window with overlap
                if self.chunk_overlap > 0 and len(current_words) > self.chunk_overlap:
                    current_words = current_words[-self.chunk_overlap:]
                else:
                    current_words = []

            current_words.extend(unit_words)

        # Append trailing words
        if current_words:
            chunk_text = " ".join(current_words).strip()
            p_start, p_end = self._find_page_range_for_text(
                document_text=doc_full_text,
                chunk_text=chunk_text,
                page_offsets=page_offsets,
                fallback_start=section.page_start,
                fallback_end=section.page_end,
            )
            chunk_idx = start_chunk_idx + len(section_chunks)
            chunk_id = f"{document.paper_id}_c{chunk_idx:04d}_p{p_start}-{p_end}"

            meta = ChunkMetadata(
                chunk_id=chunk_id,
                paper_id=document.paper_id,
                document_id=document.document_id,
                page_start=p_start,
                page_end=p_end,
                section=section.name,
                chunk_index=chunk_idx,
                token_count=len(current_words),
                title=document.title,
            )
            section_chunks.append(DocumentChunk(text=chunk_text, metadata=meta))

        return section_chunks

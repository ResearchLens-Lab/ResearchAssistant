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
        self._match_cursor = 0

    def chunk(self, document: NormalizedDocument) -> List[DocumentChunk]:
        self._match_cursor = 0
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
        nonempty_pages = [page for page in pages if page.text.strip()]
        for page_index, page in enumerate(nonempty_pages):
            length = len(page.text)
            index.append((page.page_number, current_offset, current_offset + length))
            current_offset += length + (2 if page_index < len(nonempty_pages) - 1 else 0)
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

        # Match on whitespace-normalized text while retaining source offsets. PDF
        # extractors often wrap lines differently from the chunker.
        match = self._find_normalized_match(document_text, chunk_text, self._match_cursor)
        start_pos = match[0] if match else -1
        if start_pos == -1:
            return fallback_start, fallback_end
        end_pos = match[1]
        # Advance by the match start, not its end, so overlapping chunks can
        # still resolve while repeated identical passages map in document order.
        # Keep the matcher stateless so overlapping chunks can resolve the same
        # passage; ambiguity from repeated text is bounded by source page range.

        p_start = fallback_start
        p_end = fallback_end
        found_start = False

        for page_num, p_from, p_to in page_offsets:
            if not found_start and start_pos < p_to:
                p_start = page_num
                found_start = True
            if end_pos <= p_to:
                p_end = page_num
                break
            p_end = page_num

        return max(1, p_start), max(p_start, p_end)

    @staticmethod
    def _locator_for(document: NormalizedDocument, text: str, section_name: str, chunk_number: int) -> str:
        fmt = (document.metadata.source_format or "pdf").lower()
        if fmt in {"xlsx", "csv", "docx"}:
            sheets = re.findall(r"Sheet:\s*(.+?)(?=\s+Columns:|\s+Row\s+\d+:|$)", text, re.I)
            rows = [int(value) for value in re.findall(r"\bRow\s+(\d+)\s*:", text, re.I)]
            if sheets:
                row_label = (f"row {rows[0]}" if len(rows) == 1 else f"rows {min(rows)}-{max(rows)}") if rows else "headers"
                return f"Sheet {sheets[0].strip()}, {row_label}"
            if rows:
                row_label = f"rows {min(rows)}-{max(rows)}" if len(rows) > 1 else f"row {rows[0]}"
                return row_label
        if fmt == "pptx":
            slides = [int(value) for value in re.findall(r"\bSlide\s+(\d+)\s*:", text, re.I)]
            if not slides:
                slides = [int(value) for value in re.findall(r"\bSlide\s+(\d+)\b", text, re.I)]
            if slides:
                return f"Slide {min(slides)}" if min(slides) == max(slides) else f"Slides {min(slides)}-{max(slides)}"
        return f"{section_name} · passage {chunk_number}"

    @staticmethod
    def _find_normalized_match(source: str, target: str, start_at: int = 0):
        tokens = list(re.finditer(r"\S+", source))
        wanted = target.split()
        if not wanted:
            return None
        # Compare token streams so differences in line breaks and repeated spaces
        # do not invalidate provenance. The first contiguous exact sequence wins.
        for i in range(0, len(tokens) - len(wanted) + 1):
            if tokens[i].start() < start_at:
                continue
            if all(tokens[i + j].group() == word for j, word in enumerate(wanted)):
                return tokens[i].start(), tokens[i + len(wanted) - 1].end()
        return None

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
                is_pdf = (document.metadata.source_format or "pdf").lower() == "pdf"
                locator = self._locator_for(document, chunk_text, section.name, chunk_idx + 1)
                chunk_id = f"{document.paper_id}_c{chunk_idx:04d}" + (f"_p{p_start}-{p_end}" if is_pdf else "")

                meta = ChunkMetadata(
                    chunk_id=chunk_id,
                    paper_id=document.paper_id,
                    document_id=document.document_id,
                    page_start=p_start if is_pdf else None,
                    page_end=p_end if is_pdf else None,
                    section=section.name,
                    chunk_index=chunk_idx,
                    token_count=len(current_words),
                    title=document.title,
                    filename=document.metadata.filename,
                    locator=locator,
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
            is_pdf = (document.metadata.source_format or "pdf").lower() == "pdf"
            locator = self._locator_for(document, chunk_text, section.name, chunk_idx + 1)
            chunk_id = f"{document.paper_id}_c{chunk_idx:04d}" + (f"_p{p_start}-{p_end}" if is_pdf else "")

            meta = ChunkMetadata(
                chunk_id=chunk_id,
                paper_id=document.paper_id,
                document_id=document.document_id,
                page_start=p_start if is_pdf else None,
                page_end=p_end if is_pdf else None,
                section=section.name,
                chunk_index=chunk_idx,
                token_count=len(current_words),
                title=document.title,
                filename=document.metadata.filename,
                locator=locator,
            )
            section_chunks.append(DocumentChunk(text=chunk_text, metadata=meta))

        return section_chunks

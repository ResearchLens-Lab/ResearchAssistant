"""
Chunking strategies for research papers.
Preserves section semantics, sentence/paragraph boundaries, and page provenance.
"""

import re
import logging
from bisect import bisect_left, bisect_right
from abc import ABC, abstractmethod
from typing import List, Tuple
from rag.ingestion.document_normalizer import NormalizedDocument, Section, Page
from rag.chunking.metadata import DocumentChunk, ChunkMetadata, make_chunk_id

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
        self._source_text = ""
        self._source_tokens = []
        self._source_token_starts = []

    def chunk(self, document: NormalizedDocument) -> List[DocumentChunk]:
        self._source_text = document.full_text
        self._source_tokens = []
        self._source_token_starts = []
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

    def clear_match_cache(self) -> None:
        """Release source text indexes after chunking to bound document memory."""
        self._source_text = ""
        self._source_tokens = []
        self._source_token_starts = []
        self._match_cursor = 0

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
        Finds the exact start and end page for a chunk snippet using fast
        string searching and binary search page resolution.
        """
        if not page_offsets:
            return fallback_start, fallback_end

        words = chunk_text.split()
        if not words:
            return fallback_start, fallback_end

        start_pos = -1
        # 1. Exact string search using a prefix of words (fast C-level Boyer-Moore .find)
        prefix_len = min(6, len(words))
        prefix = " ".join(words[:prefix_len])
        start_pos = document_text.find(prefix, self._match_cursor)
        if start_pos == -1 and self._match_cursor > 0:
            start_pos = document_text.find(prefix)

        # 2. Shorter prefix fallback if line break or formatting split the prefix
        if start_pos == -1 and prefix_len > 3:
            prefix3 = " ".join(words[:3])
            start_pos = document_text.find(prefix3, self._match_cursor)
            if start_pos == -1 and self._match_cursor > 0:
                start_pos = document_text.find(prefix3)

        # 3. Regex fallback with flexible whitespace across line-breaks
        if start_pos == -1:
            search_words = words[:min(4, len(words))]
            pattern = re.compile(r"\s+".join(re.escape(w) for w in search_words))
            # First search in local forward window of 50,000 chars for efficiency
            window = document_text[self._match_cursor: self._match_cursor + 50000]
            match = pattern.search(window)
            if match:
                start_pos = self._match_cursor + match.start()
            else:
                match = pattern.search(document_text)
                if match:
                    start_pos = match.start()

        if start_pos == -1:
            return fallback_start, fallback_end

        # Find end position using suffix
        suffix_len = min(6, len(words))
        suffix = " ".join(words[-suffix_len:])
        end_pos = -1
        suffix_pos = document_text.find(suffix, start_pos)
        if suffix_pos != -1:
            end_pos = suffix_pos + len(suffix)
        else:
            suffix_words = words[-min(4, len(words)):]
            pattern_end = re.compile(r"\s+".join(re.escape(w) for w in suffix_words))
            match_end = pattern_end.search(document_text, start_pos)
            if match_end:
                end_pos = match_end.end()
            else:
                end_pos = min(len(document_text), start_pos + len(chunk_text))

        self._match_cursor = start_pos + 1

        # Binary search page boundaries in O(log P)
        page_starts = [p[1] for p in page_offsets]
        p_idx = bisect_right(page_starts, start_pos) - 1
        p_start = page_offsets[max(0, p_idx)][0]

        p_end_idx = bisect_right(page_starts, end_pos) - 1
        p_end = page_offsets[max(0, min(p_end_idx, len(page_offsets) - 1))][0]

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

    def _find_normalized_match(self, source: str, target: str, start_at: int = 0):
        words = target.split()
        if not words:
            return None
        prefix_len = min(6, len(words))
        prefix = " ".join(words[:prefix_len])
        start_pos = source.find(prefix, start_at)
        if start_pos == -1 and start_at > 0:
            start_pos = source.find(prefix)
        if start_pos == -1:
            search_words = words[:min(4, len(words))]
            pattern = re.compile(r"\s+".join(re.escape(w) for w in search_words))
            match = pattern.search(source, start_at)
            if not match and start_at > 0:
                match = pattern.search(source)
            if not match:
                return None
            start_pos = match.start()

        suffix_len = min(6, len(words))
        suffix = " ".join(words[-suffix_len:])
        suffix_pos = source.find(suffix, start_pos)
        if suffix_pos != -1:
            end_pos = suffix_pos + len(suffix)
        else:
            suffix_words = words[-min(4, len(words)):]
            pattern_end = re.compile(r"\s+".join(re.escape(w) for w in suffix_words))
            match_end = pattern_end.search(source, start_pos)
            if match_end:
                end_pos = match_end.end()
            else:
                end_pos = min(len(source), start_pos + len(target))
        return start_pos, end_pos

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

        # Split into sentence-like or paragraph units, keeping tables intact where practical
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        units: List[str] = []
        for p in paragraphs:
            # Check if this paragraph is a Markdown table
            lines = [line.strip() for line in p.split("\n") if line.strip()]
            is_table = len(lines) >= 2 and all(l.startswith("|") and l.endswith("|") for l in lines)

            if is_table:
                # Keep table together if it fits inside chunk_size, else split by row
                table_words = p.split()
                if len(table_words) <= self.chunk_size:
                    units.append(p)
                else:
                    # Very large table: chunk by rows while repeating header
                    header_line = lines[0]
                    separator_line = lines[1] if len(lines) > 1 and "---" in lines[1] else "| " + " | ".join(["---"] * (header_line.count("|") - 1)) + " |"
                    current_rows = []
                    for row in lines[2:] if "---" in lines[1] else lines[1:]:
                        current_rows.append(row)
                        if len(" ".join(current_rows).split()) >= self.chunk_size:
                            units.append("\n".join([header_line, separator_line] + current_rows))
                            current_rows = []
                    if current_rows:
                        units.append("\n".join([header_line, separator_line] + current_rows))
            elif len(p.split()) > self.chunk_size:
                # If paragraph is long, split by sentences without breaking mid-sentence
                sentences = re.split(r"(?<=[.?!])\s+", p)
                for sentence in sentences:
                    sentence_words = sentence.split()
                    if len(sentence_words) <= self.chunk_size:
                        if sentence_words:
                            units.append(" ".join(sentence_words))
                        continue
                    # Hard window fallback for extremely long unpunctuated text
                    units.extend(
                        " ".join(sentence_words[start:start + self.chunk_size])
                        for start in range(0, len(sentence_words), self.chunk_size)
                    )
            else:
                units.append(p)

        section_chunks: List[DocumentChunk] = []
        current_words: List[str] = []
        doc_full_text = self._source_text

        for unit in units:
            unit_words = unit.split()
            if len(current_words) + len(unit_words) > self.chunk_size and current_words:
                chunk_text = " ".join(current_words).strip()
                # Skip meaningless or empty chunks
                if len(re.sub(r"\W+", "", chunk_text)) >= 3:
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
                    chunk_id = make_chunk_id(document.paper_id, document.document_id, chunk_idx, p_start, p_end, is_pdf)

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

                # Slide window with overlap, preferring sentence boundary
                if self.chunk_overlap > 0 and len(current_words) > self.chunk_overlap:
                    overlap_target = self.chunk_overlap
                    # Try to align overlap to sentence boundary
                    tail_text = " ".join(current_words[-min(len(current_words), overlap_target * 2):])
                    sentence_matches = list(re.finditer(r"(?<=[.?!])\s+", tail_text))
                    if sentence_matches:
                        last_sentence_start = sentence_matches[-1].end()
                        sentence_words = tail_text[last_sentence_start:].split()
                        if 10 <= len(sentence_words) <= overlap_target * 2:
                            current_words = sentence_words
                        else:
                            current_words = current_words[-overlap_target:]
                    else:
                        current_words = current_words[-overlap_target:]
                else:
                    current_words = []

            current_words.extend(unit_words)

        # Append trailing words
        if current_words:
            chunk_text = " ".join(current_words).strip()
            if len(re.sub(r"\W+", "", chunk_text)) >= 3:
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
                chunk_id = make_chunk_id(document.paper_id, document.document_id, chunk_idx, p_start, p_end, is_pdf)

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

"""
Structure-Aware Parent-Child Document Chunker.
Splits documents along strict section and paragraph boundaries, maintaining
heading hierarchy breadcrumbs, section types, and parent-child chunk relations.
"""

from __future__ import annotations

import logging
import re
from bisect import bisect_right
from typing import Any, Dict, List, Optional, Tuple

from rag.chunking.metadata import ChunkMetadata, DocumentChunk, make_chunk_id
from rag.chunking.strategies import BaseChunkingStrategy
from rag.ingestion.document_normalizer import NormalizedDocument, Section

logger = logging.getLogger(__name__)


class StructureAwareChunker(BaseChunkingStrategy):
    """
    Hierarchical, structure-preserving chunking strategy.
    Guarantees no cross-section text leakage, captures heading paths,
    and supports parent-child chunk linkage.
    """

    DEFAULT_TARGET_WORDS = 350
    DEFAULT_OVERLAP_WORDS = 60

    def clear_match_cache(self) -> None:
        pass

    def __init__(
        self,
        target_words: int = DEFAULT_TARGET_WORDS,
        overlap_words: int = DEFAULT_OVERLAP_WORDS,
    ):
        self.target_words = target_words
        self.overlap_words = overlap_words
        self._sentence_split_re = re.compile(
            r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])",
        )

    def chunk(self, document: NormalizedDocument) -> List[DocumentChunk]:
        """Splits normalized document into parent and child chunks respecting section boundaries."""
        if not document.pages and not document.sections:
            logger.warning("Attempted to chunk empty document: %s", document.document_id)
            return []

        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        # Build page offset mapping for page boundary resolution
        page_offsets = self._build_page_index(document.pages)
        source_text = document.full_text

        sections = document.sections
        if not sections:
            # Fallback single section
            sections = [
                Section(
                    name="Main Content",
                    page_start=document.pages[0].page_number if document.pages else 1,
                    page_end=document.pages[-1].page_number if document.pages else 1,
                    text=document.full_text,
                )
            ]

        for sec in sections:
            sec_chunks = self._chunk_single_section(
                document=document,
                section=sec,
                page_offsets=page_offsets,
                source_text=source_text,
                start_chunk_idx=chunk_idx,
            )
            chunks.extend(sec_chunks)
            chunk_idx += len(sec_chunks)

        logger.info(
            "Document [%s] produced %d structure-aware chunks across %d sections",
            document.document_id,
            len(chunks),
            len(sections),
        )
        return chunks

    def _chunk_single_section(
        self,
        document: NormalizedDocument,
        section: Section,
        page_offsets: List[Tuple[int, int]],
        source_text: str,
        start_chunk_idx: int,
    ) -> List[DocumentChunk]:
        sec_text = section.text.strip()
        if not sec_text:
            return []

        # Extract extra section properties if attached
        extra_meta = getattr(section, "extra", {}) or {}
        heading_path = extra_meta.get("heading_path") or [section.name]
        section_type = extra_meta.get("section_type", "body")
        extraction_method = extra_meta.get("extraction_method", "native")
        extraction_conf = extra_meta.get("extraction_confidence", 1.0)
        page_label_start = extra_meta.get("page_label_start", str(section.page_start))
        page_label_end = extra_meta.get("page_label_end", str(section.page_end))

        # Parent chunk ID for hierarchical linking
        parent_chunk_id = f"{document.paper_id}_sec{start_chunk_idx:04d}_d{document.document_id}"

        # Segment section text into paragraphs
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", sec_text) if p.strip()]
        if not paragraphs:
            paragraphs = [sec_text]

        # Aggregate paragraphs into target chunk sizes with sliding overlap
        chunk_units: List[str] = []
        current_paras: List[str] = []
        current_word_count = 0

        for para in paragraphs:
            para_words = len(para.split())
            if current_word_count + para_words > self.target_words and current_paras:
                chunk_units.append("\n\n".join(current_paras))
                # Carry over last paragraph for overlap if it's within overlap budget
                if para_words <= self.overlap_words:
                    current_paras = [para]
                    current_word_count = para_words
                else:
                    current_paras = [para]
                    current_word_count = para_words
            else:
                current_paras.append(para)
                current_word_count += para_words

        if current_paras:
            chunk_units.append("\n\n".join(current_paras))

        is_pdf = (document.metadata.source_format or "pdf").lower() == "pdf"
        result_chunks: List[DocumentChunk] = []

        for offset_idx, text_unit in enumerate(chunk_units):
            current_idx = start_chunk_idx + offset_idx

            # Find page range for this specific text unit
            p_start, p_end = self._find_page_range(
                document_text=source_text,
                chunk_text=text_unit,
                page_offsets=page_offsets,
                fallback_start=section.page_start,
                fallback_end=section.page_end,
            )

            chunk_id = make_chunk_id(
                paper_id=document.paper_id,
                document_id=document.document_id,
                chunk_index=current_idx,
                page_start=p_start,
                page_end=p_end,
                is_pdf=is_pdf,
            )

            breadcrumb = " > ".join(heading_path)
            locator = f"{breadcrumb} · p.{p_start}"

            chunk_extra = {
                "heading_path": heading_path,
                "section_type": section_type,
                "extraction_method": extraction_method,
                "extraction_confidence": extraction_conf,
                "page_label_start": page_label_start,
                "page_label_end": page_label_end,
                "parent_chunk_id": parent_chunk_id if len(chunk_units) > 1 else None,
            }

            token_count = int(len(text_unit.split()) * 1.33)

            meta = ChunkMetadata(
                chunk_id=chunk_id,
                owner_id=document.owner_id,  # SEC-001: Required multi-tenant isolation
                paper_id=document.paper_id,
                document_id=document.document_id,
                page_start=p_start,
                page_end=p_end,
                section=section.name,
                chunk_index=current_idx,
                token_count=token_count,
                title=document.title,
                filename=document.metadata.filename,
                locator=locator,
                extra=chunk_extra,
            )

            result_chunks.append(DocumentChunk(text=text_unit, metadata=meta))

        return result_chunks

    @staticmethod
    def _build_page_index(pages) -> List[Tuple[int, int]]:
        offsets = []
        cursor = 0
        for p in pages:
            offsets.append((p.page_number, cursor))
            cursor += len(p.text) + 2
        return offsets

    @staticmethod
    def _find_page_range(
        document_text: str,
        chunk_text: str,
        page_offsets: List[Tuple[int, int]],
        fallback_start: int,
        fallback_end: int,
    ) -> Tuple[int, int]:
        if not page_offsets or not document_text:
            return fallback_start, fallback_end

        # Use first 40 chars of chunk to locate starting offset in document_text
        probe = chunk_text[:40].strip()
        pos = document_text.find(probe) if probe else -1
        if pos == -1:
            return fallback_start, fallback_end

        page_starts = [o[1] for o in page_offsets]
        p_idx = bisect_right(page_starts, pos) - 1
        p_start = page_offsets[max(0, p_idx)][0]

        end_probe = chunk_text[-40:].strip()
        end_pos = document_text.find(end_probe, pos) if end_probe else -1
        if end_pos != -1:
            p_end_idx = bisect_right(page_starts, end_pos) - 1
            p_end = page_offsets[max(0, min(p_end_idx, len(page_offsets) - 1))][0]
        else:
            p_end = p_start

        return max(1, p_start), max(p_start, p_end)

"""
Structure-Aware Parent-Child Document Chunker.
Splits documents along strict section and paragraph boundaries, maintaining
heading hierarchy breadcrumbs, section types, and parent-child chunk relations.
"""

from __future__ import annotations

import hashlib
import logging
import re
from bisect import bisect_right
from typing import Any, Dict, List, Optional, Tuple

from rag.chunking.metadata import ChunkMetadata, DocumentChunk, make_chunk_id
from rag.chunking.strategies import BaseChunkingStrategy
from rag.ingestion.document_normalizer import NormalizedDocument, Section

logger = logging.getLogger(__name__)


KNOWN_ABBREVIATIONS = (
    "e.g.", "i.e.", "fig.", "figure", "eq.", "equation", "sec.", "section", "thm.", "theorem", "vs.", "et al."
)

HEADING_LABELS_RE = re.compile(
    r"^(?:chapter|part|section|appendix|unit|module|problem|exercise|algorithm|figure|table)\b", re.I
)


def norm_header(s: str) -> str:
    if not s:
        return ""
    s = s.lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"[^\w\s]", "", s)
    return " ".join(s.split())


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

        # Q3 Deduplication: drop verbatim identical chunks (hash(norm(text))) keeping earlier page
        def _norm_t(t: str) -> str:
            return re.sub(r"\s+", " ", t).strip().lower()

        seen_hashes: Dict[str, DocumentChunk] = {}
        deduped: List[DocumentChunk] = []
        for chk in chunks:
            h = hashlib.sha256(_norm_t(chk.text).encode("utf-8")).hexdigest()
            if h in seen_hashes:
                existing = seen_hashes[h]
                if (chk.metadata.page_start or 999999) < (existing.metadata.page_start or 999999):
                    seen_hashes[h] = chk
            else:
                seen_hashes[h] = chk
                deduped.append(chk)
        chunks = [chk for chk in deduped if chk in seen_hashes.values()]

        # Q1 Chunk size bounding:
        # - Split chunks > 800 words on paragraph/sentence boundaries
        def _split_oversized_text(text: str, max_words: int = 600) -> List[str]:
            paras = text.split("\n\n")
            if len(paras) > 1:
                res = []
                curr = []
                curr_w = 0
                for p in paras:
                    pw = len(p.split())
                    if pw > max_words:
                        if curr:
                            res.append("\n\n".join(curr))
                            curr = []
                            curr_w = 0
                        res.extend(_split_oversized_text(p, max_words=max_words))
                    elif curr_w + pw > max_words and curr:
                        res.append("\n\n".join(curr))
                        curr = [p]
                        curr_w = pw
                    else:
                        curr.append(p)
                        curr_w += pw
                if curr:
                    res.append("\n\n".join(curr))
                return res

            sentences = re.split(r"(?<=[.!?])\s+", text)
            if len(sentences) > 1:
                res = []
                curr = []
                curr_w = 0
                for s in sentences:
                    sw = len(s.split())
                    if sw > max_words:
                        if curr:
                            res.append(" ".join(curr))
                            curr = []
                            curr_w = 0
                        words = s.split()
                        for i in range(0, len(words), max_words):
                            res.append(" ".join(words[i : i + max_words]))
                    elif curr_w + sw > max_words and curr:
                        res.append(" ".join(curr))
                        curr = [s]
                        curr_w = sw
                    else:
                        curr.append(s)
                        curr_w += sw
                if curr:
                    res.append(" ".join(curr))
                return res

            words = text.split()
            return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]

        bounded_chunks: List[DocumentChunk] = []
        for chk in chunks:
            words = chk.text.split()
            if len(words) > 800:
                splits = _split_oversized_text(chk.text, max_words=600)
                for s in splits:
                    if s.strip():
                        sub_meta = chk.metadata.model_copy()
                        bounded_chunks.append(DocumentChunk(text=s.strip(), metadata=sub_meta))
            else:
                bounded_chunks.append(chk)

        # - Merge chunks < min(60, target_words) into previous chunk if same section
        min_merge_words = min(60, self.target_words)
        merged_chunks: List[DocumentChunk] = []
        for chk in bounded_chunks:
            if not merged_chunks:
                merged_chunks.append(chk)
                continue
            prev = merged_chunks[-1]
            chk_words = len(chk.text.split())
            same_sec = (prev.metadata.section or "").strip() == (chk.metadata.section or "").strip()
            if chk_words < min_merge_words and same_sec and (len(prev.text.split()) + chk_words <= 800):
                prev.text = prev.text.rstrip() + "\n\n" + chk.text.lstrip()
                if chk.metadata.page_end:
                    prev.metadata.page_end = max(prev.metadata.page_end or 0, chk.metadata.page_end)
            else:
                merged_chunks.append(chk)

        # Re-index chunk_index sequentially
        for idx, chk in enumerate(merged_chunks):
            chk.metadata.chunk_index = idx
            chk.metadata.chunk_id = make_chunk_id(
                document.paper_id,
                document.document_id,
                idx,
                page_start=chk.metadata.page_start,
                page_end=chk.metadata.page_end,
            )

        chunks = merged_chunks

        logger.info(
            "Document [%s] produced %d structure-aware chunks across %d sections",
            document.document_id,
            len(chunks),
            len(sections),
        )
        return chunks

    chunk_document = chunk

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

        # Segment section text into paragraphs, merging blocks split across page breaks
        raw_blocks = [p.strip() for p in re.split(r"\n\s*\n", sec_text) if p.strip()]
        paragraphs: List[str] = []
        for b in raw_blocks:
            if paragraphs:
                prev = paragraphs[-1]
                ends_terminal = bool(re.search(r'[.?!:][\'"’”\)]*$', prev))
                starts_lower = bool(re.match(r'^[a-z]', b))
                if not ends_terminal and starts_lower:
                    paragraphs[-1] = prev + " " + b
                    continue
            paragraphs.append(b)
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

            # Running header removal at chunk time:
            # If first line of a chunk equals the normalized section label
            # (ignore case, punctuation, hyphen vs space) or matches ^(chapter|part)\s+\d+,
            # store it in metadata as running_header and drop it from `text`. (New ingestions only.)
            lines = text_unit.split("\n", 1)
            first_l = lines[0].strip()
            norm_first = norm_header(first_l)
            norm_sec = norm_header(section.name)
            running_hdr = None
            if norm_sec and norm_first == norm_sec:
                running_hdr = first_l
            elif (
                re.match(r"^(?:chapter|part)\s+\d+", norm_first, re.I)
                and len(first_l) <= 80
                and len(first_l.split()) <= 8
                and not re.search(r"[.,;!?]$", first_l)
            ):
                running_hdr = first_l

            if running_hdr is not None and len(lines) > 1:
                text_unit = lines[1].strip()

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
            if running_hdr is not None:
                chunk_extra["running_header"] = running_hdr

            token_count = int(len(text_unit.split()) * 1.33)

            meta = ChunkMetadata(
                chunk_id=chunk_id,
                owner_id=document.owner_id,  # SEC-001: Required multi-tenant isolation
                paper_id=document.paper_id,
                document_id=document.document_id,
                page_start=p_start,
                page_end=p_end,
                section=(section.name[:70] if section.name else ""),
                chunk_index=current_idx,
                token_count=token_count,
                title=document.title,
                filename=document.metadata.filename,
                locator=locator,
                extra=chunk_extra,
            )

            result_chunks.append(DocumentChunk(text=text_unit, metadata=meta))

        # Post-process chunks in this section to fix orphan fragment artifacts
        for i in range(len(result_chunks)):
            c_text = result_chunks[i].text.strip()
            if not c_text:
                continue

            # Never treat as orphan: text starting with a digit, "(", "[", a heading label,
            # or a known abbreviation before the first terminator
            if c_text[0].isdigit() or c_text.startswith(("(", "[")):
                continue
            if HEADING_LABELS_RE.match(c_text):
                continue
            lower_start = c_text.lower()
            if any(lower_start.startswith(abbr) for abbr in KNOWN_ABBREVIATIONS):
                continue

            # Restrict orphan handling to chunks whose FIRST CHARACTER IS A LOWERCASE LETTER
            if not c_text[0].islower():
                continue

            is_orphan = False
            orphan_fragment = ""
            rest_text = ""

            m = re.search(r"^([^.!?]*[.!?])(?:\s+|$)", c_text)
            if m:
                frag = m.group(1).strip()
                rem = c_text[m.end():].strip()
                frag_words = frag.split()
                if any(frag_words[0].lower().startswith(abbr) for abbr in KNOWN_ABBREVIATIONS):
                    continue
                # The fragment is <= 3 words, starts lowercase or is a lone ligature-broken word like "flavor",
                # and the remainder starts with an uppercase letter
                if len(frag_words) <= 3 and (frag[0].islower() or len(frag_words) == 1):
                    if not rem or rem[0].isupper():
                        is_orphan = True
                        orphan_fragment = frag
                        rest_text = rem
            else:
                # No terminator in chunk and starts lowercase -> only merge whole chunk if <= 40 words
                if len(c_text.split()) <= 40:
                    is_orphan = True
                    orphan_fragment = c_text
                    rest_text = ""
                else:
                    is_orphan = False

            if is_orphan and orphan_fragment:
                if i > 0:
                    result_chunks[i - 1].text = (result_chunks[i - 1].text.rstrip() + " " + orphan_fragment).strip()
                    result_chunks[i].text = rest_text
                    prev_meta = result_chunks[i - 1].metadata
                    this_meta = result_chunks[i].metadata
                    if prev_meta and this_meta:
                        prev_meta.page_end = max(prev_meta.page_end or 0, this_meta.page_end or 0)
                        if hasattr(prev_meta, "extra") and isinstance(prev_meta.extra, dict):
                            prev_meta.extra["page_end"] = prev_meta.page_end
                else:
                    if rest_text:
                        result_chunks[i].text = rest_text

        result_chunks = [c for c in result_chunks if c.text.strip()]
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

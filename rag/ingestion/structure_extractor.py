"""
Document Structure and Outline Extractor.
Extracts Table of Contents (TOC), headings hierarchy (H1-H4), chapter/section boundaries,
printed page labels vs PDF physical indices, and classifies academic section types.
"""

from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

logger = logging.getLogger(__name__)


class SectionType(str, enum.Enum):
    FRONT_MATTER = "front_matter"
    BODY = "body"
    DEFINITIONS = "definitions"
    EXAMPLES = "examples"
    EXERCISES = "exercises"
    PROBLEMS = "problems"
    CHAPTER_NOTES = "chapter_notes"
    BIBLIOGRAPHY = "bibliography"
    INDEX = "index"
    APPENDIX = "appendix"
    TABLE_FIGURE = "table_figure"


@dataclass
class DocumentSectionNode:
    title: str
    level: int  # 1 for Part/Chapter, 2 for Section, 3 for Subsection
    page_start: int  # 1-indexed PDF physical page
    page_end: int  # 1-indexed PDF physical page
    page_label_start: str = ""
    page_label_end: str = ""
    heading_path: List[str] = field(default_factory=list)
    section_type: SectionType = SectionType.BODY
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "page_label_start": self.page_label_start,
            "page_label_end": self.page_label_end,
            "heading_path": self.heading_path,
            "section_type": self.section_type.value,
        }


class StructureExtractor:
    """Extracts document structure and segments pages into typed, hierarchical sections."""

    # Section type classification rules
    SECTION_TYPE_PATTERNS = [
        (SectionType.FRONT_MATTER, re.compile(r"^(?:preface|contents|table\s+of\s+contents|acknowledg(?:e)?ments|foreword|about\s+the\s+author)\b", re.IGNORECASE)),
        (SectionType.BIBLIOGRAPHY, re.compile(r"^(?:references|bibliography|literature\s+cited|further\s+reading)\b", re.IGNORECASE)),
        (SectionType.INDEX, re.compile(r"^(?:index|subject\s+index|author\s+index|name\s+index)\b", re.IGNORECASE)),
        (SectionType.EXERCISES, re.compile(r"^(?:exercises|exercise\s+\d+|review\s+questions|self[- ]test)\b", re.IGNORECASE)),
        (SectionType.PROBLEMS, re.compile(r"^(?:problems|chapter\s+problems)\b", re.IGNORECASE)),
        (SectionType.CHAPTER_NOTES, re.compile(r"^(?:chapter\s+notes|historical\s+notes|notes\s+and\s+references)\b", re.IGNORECASE)),
        (SectionType.APPENDIX, re.compile(r"^(?:appendix|appendices)\b", re.IGNORECASE)),
        (SectionType.DEFINITIONS, re.compile(r"^(?:definitions|glossary|terminology|notation)\b", re.IGNORECASE)),
        (SectionType.EXAMPLES, re.compile(r"^(?:example|examples|case\s+study|case\s+studies)\b", re.IGNORECASE)),
    ]

    # Regular expressions for detecting headings in text stream
    CHAPTER_HEADING_RE = re.compile(
        r"^(?:(?:Part|Chapter|Unit|Module|Section)\s+([0-9IVXLCDM]+)\s*[:.\s-]*\s*(.*)|(\d+)\s+([A-Z][A-Za-z0-9\s,'\-\(\)]+))$",
        re.IGNORECASE,
    )
    SUBSECTION_HEADING_RE = re.compile(
        r"^(\d+\.\d+(?:\.\d+)?)\s+([A-Z][A-Za-z0-9\s,'\-\(\)]+)$"
    )
    SUBSECTION_NUM_ONLY_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)$")

    @classmethod
    def classify_section_type(cls, title: str, text_sample: str = "") -> SectionType:
        """Determines the semantic section type from heading title and optional text sample."""
        clean_title = title.strip().lower()

        # Check title patterns
        for stype, pat in cls.SECTION_TYPE_PATTERNS:
            if pat.search(clean_title):
                return stype

        # Secondary heuristic: check beginning of text
        if text_sample:
            head = text_sample[:300].strip().lower()
            for stype, pat in cls.SECTION_TYPE_PATTERNS:
                if pat.search(head):
                    return stype

        return SectionType.BODY

    def extract_structure(
        self,
        doc: pymupdf.Document,
        extracted_pages: List[Tuple[int, str]],  # List of (page_num, text)
    ) -> List[DocumentSectionNode]:
        """
        Extracts sections from PDF outline (TOC) if available, enriched with
        in-text subsection headings; falls back to regex-based layout heading extraction.
        """
        total_pages = len(doc)
        page_labels: Dict[int, str] = {}
        try:
            for idx, lbl in enumerate(doc.get_page_labels()):
                page_labels[idx + 1] = str(lbl)
        except Exception:
            pass

        # 1. Try PDF Native Outline / TOC
        toc = []
        try:
            toc = doc.get_toc()  # [[lvl, title, page_1_indexed], ...]
        except Exception:
            pass

        if toc and len(toc) >= 3:
            base_nodes = self._build_from_toc(toc, total_pages, page_labels, extracted_pages)
            return self._enrich_with_subsections(base_nodes, extracted_pages, page_labels)

        # 2. Fallback: Parse headings from page texts
        return self._build_from_page_text(extracted_pages, page_labels)

    def _enrich_with_subsections(
        self,
        base_nodes: List[DocumentSectionNode],
        extracted_pages: List[Tuple[int, str]],
        page_labels: Dict[int, str],
    ) -> List[DocumentSectionNode]:
        """Scans page texts within coarse TOC chapters to find fine-grained subsections."""
        page_dict = dict(extracted_pages)
        enriched: List[DocumentSectionNode] = []

        for node in base_nodes:
            # If the node spans multiple pages, check for subheadings
            if node.page_end > node.page_start:
                sub_headings: List[Tuple[int, str]] = []  # (page_num, title)
                for p_num in range(node.page_start, node.page_end + 1):
                    p_text = page_dict.get(p_num, "")
                    lines = [l.strip() for l in p_text.split("\n") if l.strip()]
                    for idx, line in enumerate(lines):
                        m_single = self.SUBSECTION_HEADING_RE.match(line)
                        if m_single:
                            sub_headings.append((p_num, f"{m_single.group(1)} {m_single.group(2)}"))
                            continue
                        m_num = self.SUBSECTION_NUM_ONLY_RE.match(line)
                        if m_num and idx + 1 < len(lines):
                            next_l = lines[idx + 1]
                            if len(next_l) <= 60 and not re.search(r"[.!?]$", next_l):
                                sub_headings.append((p_num, f"{m_num.group(1)} {next_l}"))

                if sub_headings and len(sub_headings) >= 1:
                    # Decompose node into subsections
                    prev_p = node.page_start
                    prev_sub_title = node.title
                    for sub_p, sub_title in sub_headings:
                        if sub_p > prev_p:
                            sec_text = "\n\n".join(page_dict.get(p, "") for p in range(prev_p, sub_p))
                            stype = self.classify_section_type(prev_sub_title, sec_text)
                            enriched.append(
                                DocumentSectionNode(
                                    title=prev_sub_title,
                                    level=node.level + 1,
                                    page_start=prev_p,
                                    page_end=sub_p - 1,
                                    page_label_start=page_labels.get(prev_p, str(prev_p)),
                                    page_label_end=page_labels.get(sub_p - 1, str(sub_p - 1)),
                                    heading_path=node.heading_path + ([prev_sub_title] if prev_sub_title != node.title else []),
                                    section_type=stype,
                                    raw_text=sec_text,
                                )
                            )
                            prev_p = sub_p
                            prev_sub_title = sub_title
                        else:
                            prev_sub_title = sub_title

                    # Final subsection
                    sec_text = "\n\n".join(page_dict.get(p, "") for p in range(prev_p, node.page_end + 1))
                    stype = self.classify_section_type(prev_sub_title, sec_text)
                    enriched.append(
                        DocumentSectionNode(
                            title=prev_sub_title,
                            level=node.level + 1,
                            page_start=prev_p,
                            page_end=node.page_end,
                            page_label_start=page_labels.get(prev_p, str(prev_p)),
                            page_label_end=page_labels.get(node.page_end, str(node.page_end)),
                            heading_path=node.heading_path + ([prev_sub_title] if prev_sub_title != node.title else []),
                            section_type=stype,
                            raw_text=sec_text,
                        )
                    )
                    continue

            enriched.append(node)

        return enriched

    def _build_from_toc(
        self,
        toc: List[List[Any]],
        total_pages: int,
        page_labels: Dict[int, str],
        extracted_pages: List[Tuple[int, str]],
    ) -> List[DocumentSectionNode]:
        nodes: List[DocumentSectionNode] = []
        page_texts: Dict[int, str] = dict(extracted_pages)

        # Build breadcrumbs and resolve page spans
        active_path: Dict[int, str] = {}

        for i, entry in enumerate(toc):
            lvl, title, start_page = entry[0], str(entry[1]).strip(), int(entry[2])
            if start_page < 1:
                start_page = 1
            if start_page > total_pages:
                start_page = total_pages

            # Determine end page from next entry
            if i + 1 < len(toc):
                next_start = int(toc[i + 1][2])
                end_page = max(start_page, min(total_pages, next_start - 1 if next_start > start_page else start_page))
            else:
                end_page = total_pages

            # Update active heading path
            active_path[lvl] = title
            # Invalidate deeper levels
            for deeper in list(active_path.keys()):
                if deeper > lvl:
                    del active_path[deeper]

            current_path = [active_path[k] for k in sorted(active_path.keys())]
            stype = self.classify_section_type(title)

            # Collect text for section
            sec_text = "\n\n".join(page_texts.get(p, "") for p in range(start_page, end_page + 1))

            nodes.append(
                DocumentSectionNode(
                    title=title,
                    level=lvl,
                    page_start=start_page,
                    page_end=end_page,
                    page_label_start=page_labels.get(start_page, str(start_page)),
                    page_label_end=page_labels.get(end_page, str(end_page)),
                    heading_path=current_path,
                    section_type=stype,
                    raw_text=sec_text,
                )
            )

        return nodes

    def _build_from_page_text(
        self,
        extracted_pages: List[Tuple[int, str]],
        page_labels: Dict[int, str],
    ) -> List[DocumentSectionNode]:
        """Heuristic heading scanner for documents without embedded TOC."""
        nodes: List[DocumentSectionNode] = []
        if not extracted_pages:
            return nodes

        current_title = "Introduction / Front Matter"
        current_level = 1
        current_start_page = extracted_pages[0][0]
        current_path = [current_title]
        current_text_lines: List[str] = []

        total_pages = extracted_pages[-1][0] if extracted_pages else 1

        for page_num, text in extracted_pages:
            lines = text.split("\n")
            idx = 0
            while idx < len(lines):
                line = lines[idx]
                s = line.strip()
                if not s:
                    idx += 1
                    continue

                # Check chapter or section heading
                m_sub = self.SUBSECTION_HEADING_RE.match(s)
                m_chap = self.CHAPTER_HEADING_RE.match(s) if not m_sub else None
                advance = 1

                if not m_sub and not m_chap:
                    m_num = self.SUBSECTION_NUM_ONLY_RE.match(s)
                    if m_num and idx + 1 < len(lines):
                        next_l = lines[idx + 1].strip()
                        if len(next_l) <= 60 and not re.search(r"[.!?]$", next_l):
                            s = f"{m_num.group(1)} {next_l}"
                            m_sub = self.SUBSECTION_HEADING_RE.match(s)
                            advance = 2

                if m_chap:
                    chap_num = m_chap.group(1) or m_chap.group(3)
                    chap_title = (m_chap.group(2) or m_chap.group(4) or "").strip()
                    if chap_num and not chap_title and idx + 1 < len(lines):
                        next_idx = idx + 1
                        while next_idx < len(lines) and not lines[next_idx].strip():
                            next_idx += 1
                        if next_idx < len(lines):
                            next_l = lines[next_idx].strip()
                            if len(next_l) <= 80 and not re.search(r"[.!?]$", next_l) and not self.CHAPTER_HEADING_RE.match(next_l):
                                s = f"{s.rstrip(': ')}: {next_l}"
                                advance = (next_idx - idx) + 1

                if m_chap or m_sub:
                    # Flush previous section
                    if current_text_lines:
                        sec_text = "\n".join(current_text_lines)
                        stype = self.classify_section_type(current_title, sec_text)
                        nodes.append(
                            DocumentSectionNode(
                                title=current_title,
                                level=current_level,
                                page_start=current_start_page,
                                page_end=page_num,
                                page_label_start=page_labels.get(current_start_page, str(current_start_page)),
                                page_label_end=page_labels.get(page_num, str(page_num)),
                                heading_path=list(current_path),
                                section_type=stype,
                                raw_text=sec_text,
                            )
                        )
                        current_text_lines = []
                        current_start_page = page_num

                    if m_sub:
                        num, name = m_sub.group(1), m_sub.group(2)
                        current_title = f"{num} {name}"
                        current_level = 2
                        current_path = [p for p in current_path if p != current_title][:1] + [current_title]
                    elif m_chap:
                        current_title = s
                        current_level = 1
                        current_path = [current_title]

                current_text_lines.append(s)
                idx += advance

        # Flush final section
        if current_text_lines:
            sec_text = "\n".join(current_text_lines)
            stype = self.classify_section_type(current_title, sec_text)
            last_page = extracted_pages[-1][0] if extracted_pages else 1
            nodes.append(
                DocumentSectionNode(
                    title=current_title,
                    level=current_level,
                    page_start=current_start_page,
                    page_end=last_page,
                    page_label_start=page_labels.get(current_start_page, str(current_start_page)),
                    page_label_end=page_labels.get(last_page, str(last_page)),
                    heading_path=list(current_path),
                    section_type=stype,
                    raw_text=sec_text,
                )
            )

        return nodes

"""
Document normalization models and parser for research papers.
Converts raw extracted page streams into structured, section-aware NormalizedDocuments.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Page(BaseModel):
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str = Field(..., description="Extracted text of the page")
    is_ocr: bool = Field(default=False, description="Whether text was recovered via OCR fallback")
    ocr_confidence: Optional[float] = Field(default=None, description="Confidence score if OCR was used")


class Section(BaseModel):
    name: str = Field(..., description="Normalized section title (e.g., Introduction, Methodology)")
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    text: str = Field(..., description="Aggregated text content of the section")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Hierarchical breadcrumbs, section type, provenance")


class DocumentMetadata(BaseModel):
    paper_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    owner_id: str = Field(..., min_length=1, description="User ID who owns this document (REQUIRED for multi-tenant isolation)")
    title: str = Field(default="Untitled Research Paper")
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    file_path: Optional[str] = None
    filename: Optional[str] = None
    source_format: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(BaseModel):
    document_id: str
    paper_id: str
    owner_id: str  # SEC-001: User ID for multi-tenant isolation
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    pages: List[Page] = Field(default_factory=list)
    sections: List[Section] = Field(default_factory=list)
    metadata: DocumentMetadata

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())

    @property
    def total_pages(self) -> int:
        return len(self.pages)


class DocumentNormalizer:
    """
    Normalizes a sequence of raw pages into a NormalizedDocument with detected sections.
    """

    DEFAULT_SECTION_REGEXES = [
        (re.compile(r"^(?:abstract)\b", re.IGNORECASE), "Abstract"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:introduction)\b", re.IGNORECASE), "Introduction"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:background|related\s+work|prior\s+work)\b", re.IGNORECASE), "Related Work"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:methodology|methods|method|approach|proposed\s+system|architecture|system\s+design)\b", re.IGNORECASE), "Methodology"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:experiments|experimental\s+setup|evaluation|implementation)\b", re.IGNORECASE), "Experiments"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:results|findings|experimental\s+results)\b", re.IGNORECASE), "Results"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:discussion|analysis)\b", re.IGNORECASE), "Discussion"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:conclusion|conclusions|concluding\s+remarks|future\s+work)\b", re.IGNORECASE), "Conclusion"),
        (re.compile(r"^(?:\d+[\.\s]+)?(?:references|bibliography)\b", re.IGNORECASE), "References"),
    ]

    def __init__(self, section_patterns: Optional[List[tuple]] = None):
        self.section_patterns = section_patterns or self.DEFAULT_SECTION_REGEXES

    def normalize(
        self,
        pages: List[Page],
        metadata: DocumentMetadata,
    ) -> NormalizedDocument:
        """
        Processes pages to identify sections while strictly tracking page start and end.
        """
        if not pages:
            logger.warning("Normalizing document with empty pages: %s", metadata.document_id)
            return NormalizedDocument(
                document_id=metadata.document_id,
                paper_id=metadata.paper_id,
                owner_id=metadata.owner_id,  # SEC-001: Propagate owner_id
                title=metadata.title,
                authors=metadata.authors,
                year=metadata.year,
                pages=[],
                sections=[],
                metadata=metadata,
            )

        # Clean pages
        cleaned_pages = [
            Page(page_number=p.page_number, text=self._clean_text(p.text))
            for p in pages
        ]

        # Extract sections across pages
        sections = self._extract_sections(cleaned_pages)

        # If no explicit sections could be parsed, fallback to page-based sections
        if not sections:
            sections = [
                Section(
                    name="Main Content",
                    page_start=cleaned_pages[0].page_number,
                    page_end=cleaned_pages[-1].page_number,
                    text="\n\n".join(p.text for p in cleaned_pages if p.text.strip()),
                )
            ]

        return NormalizedDocument(
            document_id=metadata.document_id,
            paper_id=metadata.paper_id,
            owner_id=metadata.owner_id,  # SEC-001: Propagate owner_id
            title=metadata.title,
            authors=metadata.authors,
            year=metadata.year,
            pages=cleaned_pages,
            sections=sections,
            metadata=metadata,
        )

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove null bytes, normalize whitespace
        text = text.replace("\x00", " ")
        text = re.sub(r"\r\n|\r", "\n", text)
        # Fix hyphenated line breaks in academic text: e.g. trans-\nformer -> transformer
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_sections(self, pages: List[Page]) -> List[Section]:
        """
        Scans lines across pages to segment text into known academic sections.
        """
        sections: List[Section] = []
        current_section_name = "Header / Front Matter"
        current_section_lines: List[str] = []
        section_start_page = pages[0].page_number if pages else 1
        current_page_num = section_start_page

        for page in pages:
            current_page_num = page.page_number
            lines = page.text.split("\n")
            line_idx = 0

            while line_idx < len(lines):
                line = lines[line_idx]
                stripped = line.strip()
                if not stripped:
                    line_idx += 1
                    continue

                matched_name = None
                matched_advance = 1

                # 1. Check markdown heading
                md_m = re.match(r"^#{1,6}\s+(.+)$", stripped)
                if md_m:
                    matched_name = md_m.group(1).strip()[:80]

                # 2. Check "Section \d+[:.]?" or "Section [A-ZIVXLCDM]+[:.]?"
                if not matched_name:
                    sec_m = re.match(r"^(Section|Unit|Module|Chapter|Part)\s+([0-9IVXLCDM]+)\s*[:.]?\s*(.*)$", stripped, re.IGNORECASE)
                    if sec_m:
                        prefix_word = sec_m.group(1).title()
                        sec_num = sec_m.group(2).upper()
                        inline_title = sec_m.group(3).strip()
                        if inline_title and len(inline_title) > 1:
                            matched_name = f"{prefix_word} {sec_num}: {inline_title}"
                        else:
                            # Check next line for section title
                            next_idx = line_idx + 1
                            while next_idx < len(lines) and not lines[next_idx].strip():
                                next_idx += 1
                            if next_idx < len(lines):
                                next_line = lines[next_idx].strip()
                                if (len(next_line) <= 80 and not re.search(r"[.!?]$", next_line)
                                        and not re.match(r"^(?:Section|Unit|Module|Chapter|Part)\b", next_line, re.IGNORECASE)):
                                    matched_name = f"{prefix_word} {sec_num}: {next_line}"
                                    matched_advance = (next_idx - line_idx) + 1
                            if not matched_name:
                                matched_name = f"{prefix_word} {sec_num}"

                # 3. Check numbered academic headings: e.g. "1. Introduction" or "2.3 Related Work"
                if not matched_name and len(stripped) < 90:
                    num_m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z0-9\s-]{2,70})$", stripped)
                    if num_m and not re.search(r"[.!?:;,]$", num_m.group(2)):
                        matched_name = f"{num_m.group(1)} {num_m.group(2).strip()}"

                # 4. Check configured section patterns (Abstract, Introduction, etc.)
                if not matched_name and len(stripped) < 70:
                    for pattern, name in self.section_patterns:
                        if pattern.match(stripped):
                            matched_name = name
                            break

                # 5. Check all-caps academic headings
                if not matched_name and len(stripped) <= 60 and stripped.isupper() and len(stripped.split()) <= 6:
                    if not re.search(r"[.!?:;,]$", stripped) and any(c.isalpha() for c in stripped):
                        if len(stripped) > 3 and not re.match(r"^(?:GATE|IIT|CS|IEEE|ACM|ACM/IEEE|USA|UK)\b", stripped):
                            matched_name = stripped.title()

                if matched_name and matched_name != current_section_name:
                    # Finalize current section if it has content
                    if current_section_lines:
                        sections.append(
                            Section(
                                name=current_section_name,
                                page_start=section_start_page,
                                page_end=current_page_num,
                                text="\n".join(current_section_lines).strip(),
                            )
                        )
                        current_section_lines = []
                    current_section_name = matched_name
                    section_start_page = current_page_num
                    line_idx += matched_advance
                    continue

                current_section_lines.append(stripped)
                line_idx += 1

        # Final section
        if current_section_lines:
            sections.append(
                Section(
                    name=current_section_name,
                    page_start=section_start_page,
                    page_end=current_page_num,
                    text="\n".join(current_section_lines).strip(),
                )
            )

        return sections

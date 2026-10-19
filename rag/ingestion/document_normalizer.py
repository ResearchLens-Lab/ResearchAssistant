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


class Section(BaseModel):
    name: str = Field(..., description="Normalized section title (e.g., Introduction, Methodology)")
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    text: str = Field(..., description="Aggregated text content of the section")


class DocumentMetadata(BaseModel):
    paper_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
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
        current_section_name = "Header / Abstract"
        current_section_lines: List[str] = []
        section_start_page = pages[0].page_number
        current_page_num = section_start_page

        for page in pages:
            current_page_num = page.page_number
            lines = page.text.split("\n")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Check if this line matches a section header (usually short line < 60 chars)
                matched_name = None
                if len(stripped) < 60:
                    if re.match(r"^#{1,6}\s+", stripped):
                        matched_name = re.sub(r"^#{1,6}\s+", "", stripped).strip()[:59]
                    for pattern, name in self.section_patterns:
                        if matched_name is None and pattern.match(stripped):
                            matched_name = name
                            break

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

                current_section_lines.append(stripped)

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

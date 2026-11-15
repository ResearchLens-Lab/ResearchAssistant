from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class Source(BaseModel):
    """A RAG source citation preserving provenance and academic metadata."""

    model_config = ConfigDict(extra="allow")

    source_id: Optional[str] = None
    paper_id: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    page: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    text: Optional[str] = None
    score: Optional[float] = None
    title: Optional[str] = None
    filename: Optional[str] = None
    locator: Optional[str] = None
    citation_label: Optional[str] = None
    author_metadata: Optional[List[str]] = None
    paper_title: Optional[str] = None
    publication_year: Optional[int] = None
    original_page_number: Optional[int] = None
    section_label: Optional[str] = None
    evidence_excerpt: Optional[str] = None
    text_offset_start: Optional[int] = None
    text_offset_end: Optional[int] = None

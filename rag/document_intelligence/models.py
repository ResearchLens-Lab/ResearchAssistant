from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Position(BaseModel):
    page_number: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class DocumentBlock(BaseModel):
    block_id: str
    block_type: Literal["heading", "paragraph", "list_item", "reference", "caption", "equation", "table_text"]
    text: str
    position: Position
    section_id: str | None = None
    structural_level: int | None = None
    classification: str = "unknown"
    classification_status: Literal["classified", "unknown", "needs_review"] = "unknown"


class SectionRecord(BaseModel):
    section_id: str
    heading: str
    classification: str = "unknown"
    classification_status: Literal["classified", "unknown", "needs_review"] = "unknown"
    level: int = 1
    parent_section_id: str | None = None
    page_start: int
    page_end: int
    text: str = ""


class KnowledgeRecord(BaseModel):
    record_id: str
    category: str
    exact_text: str
    document_id: str
    page_number: int
    section_id: str | None = None
    block_id: str
    char_start: int
    char_end: int
    extraction_method: str
    extraction_version: str
    confidence: float = Field(ge=0, le=1)
    uncertainty: str
    review_status: Literal["pending", "approved", "rejected"] = "pending"


class ReferenceRecord(BaseModel):
    reference_id: str
    raw_text: str
    reference_number: str | None = None
    authors: list[str] = Field(default_factory=list)
    title: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    page_number: int
    char_start: int
    char_end: int
    cited_in_text: bool = False
    citation_pages: list[int] = Field(default_factory=list)
    bibliographic_status: Literal["parsed_unverified"] = "parsed_unverified"


class EquationRecord(BaseModel):
    equation_id: str
    text: str
    text_format: str
    structural_index: int
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    position_status: str = "document order only; parser supplies no page or character position"


class DocumentIntelligence(BaseModel):
    schema_version: str = "1.0"
    extraction_version: str = "phase4-rules-1"
    run_id: str
    content_hash: str
    document_id: str
    paper_id: str
    filename: str | None = None
    file_type: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    keywords: list[str] = Field(default_factory=list)
    language: str = "unknown"
    page_count: int
    extraction_status: Literal["complete", "partial", "needs_ocr", "failed"]
    private_source: bool = False
    structure_capabilities: dict[str, str] = Field(default_factory=dict)
    pages: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[SectionRecord] = Field(default_factory=list)
    blocks: list[DocumentBlock] = Field(default_factory=list)
    knowledge_records: list[KnowledgeRecord] = Field(default_factory=list)
    references: list[ReferenceRecord] = Field(default_factory=list)
    equations: list[EquationRecord] = Field(default_factory=list)
    citation_markers: list[dict[str, Any]] = Field(default_factory=list)
    quality_issues: list[str] = Field(default_factory=list)
    duration_seconds: float = 0


class ReviewEvent(BaseModel):
    event_id: str
    run_id: str
    record_id: str
    action: Literal["approve", "reject", "correct"]
    reviewer: str
    changed_at: str
    previous: dict[str, Any]
    updated: dict[str, Any]
    training_permission: bool = False

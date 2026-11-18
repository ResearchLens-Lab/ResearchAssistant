from datetime import datetime
from typing import Optional, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.citation import Source


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    abstract: Optional[str] = None
    authors: Optional[list[str]] = None
    publication_year: Optional[int] = Field(default=None, ge=1000, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    venue: Optional[str] = Field(default=None, max_length=255)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Title is required and cannot be empty or only whitespace.")
        return value.strip()

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            raise ValueError("Description cannot be empty or only whitespace.")
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def sync_description(self) -> "PaperCreate":
        if not self.description and self.abstract:
            self.description = self.abstract.strip()
        return self


class PaperUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    abstract: Optional[str] = None
    authors: Optional[list[str]] = None
    publication_year: Optional[int] = Field(default=None, ge=1000, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    venue: Optional[str] = Field(default=None, max_length=255)


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str] = None
    folder_name: Optional[str] = None
    abstract: Optional[str] = None
    authors: Optional[list[str]] = None
    publication_year: Optional[int] = None
    doi: Optional[str] = None
    source_url: Optional[str] = None
    venue: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaperSummaryResponse(BaseModel):
    paper_id: str
    answer: str
    sources: list[Source]


class PaperCompareRequest(BaseModel):
    paper_ids: Optional[list[str]] = Field(default=None, min_length=2, max_length=4)
    document_ids: Optional[list[str]] = Field(default=None, min_length=2, max_length=4)
    focus_area: Optional[str] = Field(default=None, max_length=500)
    output_format: Literal["table", "side_by_side", "detailed_report"] = "table"

    @model_validator(mode="after")
    def validate_comparison_scope(self) -> "PaperCompareRequest":
        if bool(self.paper_ids) == bool(self.document_ids):
            raise ValueError("Provide either at least two document_ids or at least two legacy paper_ids.")
        scope = self.document_ids if self.document_ids is not None else self.paper_ids
        if len(set(scope or [])) < 2:
            raise ValueError("Select at least two distinct research sources to compare.")
        return self


class PaperCompareResponse(BaseModel):
    paper_ids: list[str]
    document_ids: list[str] = Field(default_factory=list)
    answer: str
    sources: list[Source]
    metadata: dict[str, Any] = Field(default_factory=dict)

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.citation import Source


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    abstract: Optional[str] = None
    authors: Optional[list[str]] = None
    publication_year: Optional[int] = Field(default=None, ge=1000, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    venue: Optional[str] = Field(default=None, max_length=255)


class PaperUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
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
    paper_ids: list[str] = Field(min_length=2)
    focus_area: Optional[str] = Field(default=None, max_length=500)


class PaperCompareResponse(BaseModel):
    paper_ids: list[str]
    answer: str
    sources: list[Source]
    metadata: dict[str, Any] = Field(default_factory=dict)

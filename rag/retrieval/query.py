"""
Structured models for search queries and retrieved research sources.
Preserves full provenance metadata for citation mapping.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QueryFilters(BaseModel):
    paper_ids: Optional[List[str]] = Field(default=None, description="Filter by one or more paper IDs")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter by document IDs")
    sections: Optional[List[str]] = Field(default=None, description="Filter by section names (e.g. Methodology)")
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question or research prompt")
    paper_ids: Optional[List[str]] = Field(default=None, description="Target papers to search within")
    filters: Optional[QueryFilters] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievedSource(BaseModel):
    source_id: str = Field(..., description="Short source index tag (e.g., S1, S2)")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    paper_id: str = Field(..., description="Paper ID")
    document_id: str = Field(..., description="Document ID")
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    section: str = Field(default="Main Content")
    text: str = Field(..., description="Retrieved passage text")
    score: float = Field(default=0.0, description="Normalized similarity relevance score")
    title: Optional[str] = None
    filename: Optional[str] = None
    locator: Optional[str] = None

    @property
    def page_display(self) -> str:
        if self.page_start is None:
            return self.locator or "Source passage"
        if self.page_start == self.page_end:
            return f"Page {self.page_start}"
        return f"Pages {self.page_start}-{self.page_end}"

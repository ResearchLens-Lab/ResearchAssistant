"""Schemas for the research-intelligence boundary (knowledge graph).

These are placeholders describing the interface shape; the implementation
behind the boundary is owned by the knowledge-graph subsystem.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class PaperGraphResponse(BaseModel):
    paper_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class RelatedPapersResponse(BaseModel):
    paper_id: str
    related: list[dict[str, Any]] = Field(default_factory=list)


class ResearchTrendsResponse(BaseModel):
    trends: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None

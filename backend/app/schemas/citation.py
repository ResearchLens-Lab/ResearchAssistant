from typing import Optional

from pydantic import BaseModel, ConfigDict


class Source(BaseModel):
    """A RAG source citation. Extra provider fields are preserved, never discarded."""

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

"""
Chunk metadata and chunk container models.
Preserves full provenance (paper_id, document_id, chunk_id, page_start, page_end, section).
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


def make_chunk_id(paper_id: str, document_id: str, chunk_index: int,
                  page_start: Optional[int] = None, page_end: Optional[int] = None,
                  is_pdf: bool = False) -> str:
    """Build a stable chunk key scoped to both project and uploaded source."""
    chunk_id = f"{paper_id}_c{chunk_index:04d}_d{document_id}"
    if is_pdf:
        chunk_id += f"_p{page_start or 1}-{page_end or page_start or 1}"
    return chunk_id


class ChunkMetadata(BaseModel):
    chunk_id: str = Field(..., description="Deterministic unique identifier for the chunk")
    paper_id: str = Field(..., description="ID of the research paper")
    document_id: str = Field(..., description="ID of the source document")
    page_start: Optional[int] = Field(default=None, ge=1, description="First physical PDF page containing this chunk")
    page_end: Optional[int] = Field(default=None, ge=1, description="Last physical PDF page containing this chunk")
    section: str = Field(default="Main Content", description="Academic section name (e.g., Methodology)")
    chunk_index: int = Field(..., ge=0, description="0-indexed position within the document chunk sequence")
    token_count: int = Field(default=0, ge=0, description="Estimated token count of the chunk text")
    title: Optional[str] = Field(default=None, description="Title of the paper for fast citation reference")
    filename: Optional[str] = None
    locator: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    def to_chroma_metadata(self) -> Dict[str, Any]:
        """
        Converts metadata to ChromaDB-compatible flat scalar dictionary.
        """
        data = {
            "chunk_id": self.chunk_id,
            "paper_id": self.paper_id,
            "document_id": self.document_id,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
            "title": self.title or "",
            "filename": self.filename or "",
            "locator": self.locator or "",
        }
        if self.page_start is not None:
            data["page_start"] = self.page_start
        if self.page_end is not None:
            data["page_end"] = self.page_end
        return data

    @classmethod
    def from_chroma_metadata(cls, meta: Dict[str, Any]) -> "ChunkMetadata":
        return cls(
            chunk_id=str(meta.get("chunk_id", "")),
            paper_id=str(meta.get("paper_id", "")),
            document_id=str(meta.get("document_id", "")),
            page_start=int(meta["page_start"]) if meta.get("page_start") is not None else None,
            page_end=int(meta["page_end"]) if meta.get("page_end") is not None else None,
            section=str(meta.get("section", "Main Content")),
            chunk_index=int(meta.get("chunk_index", 0)),
            token_count=int(meta.get("token_count", 0)),
            title=str(meta.get("title", "")) or None,
            filename=str(meta.get("filename", "")) or None,
            locator=str(meta.get("locator", "")) or None,
            extra={k: v for k, v in meta.items() if k not in {
                "chunk_id", "paper_id", "document_id", "page_start", "page_end", "section", "chunk_index", "token_count", "title", "filename", "locator"
            }},
        )


class DocumentChunk(BaseModel):
    text: str = Field(..., min_length=1, description="Text snippet content of the chunk")
    metadata: ChunkMetadata = Field(..., description="Full provenance metadata")

    @property
    def chunk_id(self) -> str:
        return self.metadata.chunk_id

    @property
    def paper_id(self) -> str:
        return self.metadata.paper_id

    @property
    def page_start(self) -> Optional[int]:
        return self.metadata.page_start

    @property
    def page_end(self) -> Optional[int]:
        return self.metadata.page_end

    @property
    def section(self) -> str:
        return self.metadata.section

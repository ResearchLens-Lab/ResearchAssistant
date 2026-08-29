"""
Configuration for document chunking strategies.
"""

from typing import List
from pydantic import BaseModel, Field


class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=500, ge=50, le=4000, description="Target chunk size in tokens/words")
    chunk_overlap: int = Field(default=80, ge=0, le=500, description="Overlap between consecutive chunks")
    preserve_sections: bool = True
    section_patterns: List[str] = Field(
        default_factory=lambda: [
            r"^(?:abstract)\b",
            r"^(?:introduction)\b",
            r"^(?:background|related\s+work)\b",
            r"^(?:methodology|method|methods|approach|model)\b",
            r"^(?:experiments|experimental\s+setup|evaluation)\b",
            r"^(?:results|findings)\b",
            r"^(?:discussion)\b",
            r"^(?:conclusion|conclusions|future\s+work)\b",
            r"^(?:references|bibliography)\b",
        ]
    )

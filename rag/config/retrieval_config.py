"""
Configuration for vector search, filters, ranking, and context assembly.
"""

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    min_score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    enable_reranking: bool = False
    context_max_tokens: int = Field(default=3500, ge=500, le=16000)

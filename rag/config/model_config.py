"""
Model configurations for Embeddings and LLMs.
"""

from typing import Literal
from pydantic import BaseModel, Field


class EmbeddingModelConfig(BaseModel):
    provider: Literal["mock", "gemini"] = "gemini"
    model_name: str = "gemini-embedding-001"
    dimension: int = 768
    batch_size: int = 64
    api_key: str = Field(default="", repr=False)


class LLMModelConfig(BaseModel):
    provider: Literal["mock", "gemini"] = "gemini"
    model_name: str = "gemini-3.8-flash"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_seconds: float = 30.0
    api_key: str = Field(default="", repr=False)

"""
Central configuration settings for ResearchLens RAG engine.
Loads environment variables safely without hardcoding secrets.
"""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RAGSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", _PROJECT_ROOT / "backend" / ".env", _PROJECT_ROOT / "rag" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_env: Literal["development", "testing", "production"] = "development"
    log_level: str = "INFO"

    # ChromaDB
    chroma_persist_dir: str = ".chroma"
    chroma_collection_name: str = "research_papers"
    chroma_namespace_by_embedding: bool = True
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_use_http: bool = False

    # Embedding Settings
    embedding_provider: Literal["mock", "openai"] = "mock"
    embedding_model: str = "mock-dense-384"
    embedding_dimension: int = 384
    embedding_api_key: str = Field(default="", repr=False)
    embedding_batch_size: int = 32

    # LLM Settings
    llm_provider: Literal["mock", "openai"] = "mock"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = Field(default="", repr=False)
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 30.0
    claim_verification_use_llm: bool = False
    claim_repair_enabled: bool = True

    # Chunking Settings
    chunk_size: int = 500
    chunk_overlap: int = 80

    # Retrieval & Context Settings
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.0
    context_max_tokens: int = 3500
    enable_reranking: bool = False

    # Bounded research orchestration
    research_max_subquestions: int = Field(default=3, ge=0, le=3)
    research_max_queries: int = Field(default=4, ge=1, le=4)
    research_max_retrieval_rounds: int = Field(default=2, ge=1, le=2)
    research_candidates_per_query: int = Field(default=4, ge=1, le=10)
    research_max_total_candidates: int = Field(default=20, ge=1, le=40)


# Singleton settings instance
settings = RAGSettings()

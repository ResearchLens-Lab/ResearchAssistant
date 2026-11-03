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

    # General & Modes
    app_env: Literal["development", "testing", "production"] = "development"
    log_level: str = "INFO"
    rag_mode: str = "local"
    llm_enabled: bool = False
    retrieval_mode: Literal["hybrid", "dense", "bm25"] = "hybrid"

    # ChromaDB
    chroma_persist_dir: str = ".chroma"
    chroma_collection_name: str = "research_papers"
    chroma_namespace_by_embedding: bool = True
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_use_http: bool = False

    # Embedding Settings
    embedding_provider: Literal["fastembed", "gemini", "mock", "local"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    gemini_api_key: str = Field(default="", repr=False)
    embedding_batch_size: int = 128
    embedding_cache_path: str = ""
    fastembed_cache_dir: str = ".model_cache"

    # LLM Settings
    llm_provider: Literal["local", "mock", "gemini"] = "gemini"
    llm_model: str = "gemini-3.8-flash"
    llm_api_key: str = Field(default="", repr=False)
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 30.0
    # Per-provider outbound generation requests, reset at 00:00 UTC.
    llm_daily_call_budget: int = Field(default=25, ge=0)
    claim_verification_use_llm: bool = False
    claim_repair_enabled: bool = True

    # Chunking Settings (Token-budgeted section-aware chunking)
    chunk_size: int = 500
    chunk_overlap: int = 80
    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 120

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

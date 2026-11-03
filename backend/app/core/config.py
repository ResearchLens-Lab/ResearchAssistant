"""Application configuration loaded from environment variables (see backend/.env.example)."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Keep API-only secrets and settings in the backend's local file.
        # The root .env is reserved for the RAG engine and is loaded there.
        env_file=_PROJECT_ROOT / "backend" / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "ResearchAssistant"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/researchassistant"
    )

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: str = "http://localhost:3000"

    rag_service_url: str = ""
    rag_timeout_seconds: float = 60
    rag_ingest_timeout_seconds: float = 600

    knowledge_graph_url: str = ""

    upload_dir: str = "./storage/uploads"
    max_upload_file_bytes: Optional[int] = None
    max_upload_size_mb: Optional[int] = None
    max_upload_batch_bytes: Optional[int] = None
    max_upload_batch_size_mb: Optional[int] = None
    max_upload_batch_files: int = 100
    max_zip_entries: int = 100
    max_zip_entry_size_mb: int = 100
    max_zip_expanded_size_mb: int = 100
    max_zip_compression_ratio: int = 200

    rag_mode: str = "local"
    llm_enabled: bool = False
    retrieval_mode: str = "hybrid"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        if self.max_upload_file_bytes is not None:
            return self.max_upload_file_bytes
        if self.max_upload_size_mb is not None:
            return self.max_upload_size_mb * 1024 * 1024
        return 1073741824  # 1 GiB default

    @property
    def effective_max_upload_size_mb(self) -> int:
        return max(1, self.max_upload_size_bytes // (1024 * 1024))

    @property
    def max_upload_batch_size_bytes(self) -> int:
        if self.max_upload_batch_bytes is not None:
            return self.max_upload_batch_bytes
        if self.max_upload_batch_size_mb is not None:
            return self.max_upload_batch_size_mb * 1024 * 1024
        return 1073741824  # 1 GiB default

    @property
    def effective_max_upload_batch_size_mb(self) -> int:
        return max(1, self.max_upload_batch_size_bytes // (1024 * 1024))

    @property
    def max_zip_entry_size_bytes(self) -> int:
        return self.max_zip_entry_size_mb * 1024 * 1024

    @property
    def max_zip_expanded_size_bytes(self) -> int:
        return self.max_zip_expanded_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()

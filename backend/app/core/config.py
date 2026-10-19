"""Application configuration loaded from environment variables (see backend/.env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", _PROJECT_ROOT / "backend" / ".env"),
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

    knowledge_graph_url: str = ""

    upload_dir: str = "./storage/uploads"
    max_upload_size_mb: int = 25

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()

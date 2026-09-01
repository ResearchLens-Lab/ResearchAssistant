import enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, TimestampMixin, generate_uuid


class DocumentStatus(str, enum.Enum):
    """Single source of truth for processing status; RAG reports results back
    to the backend rather than keeping its own status system."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Base, TimestampMixin):
    """Uploaded/local representation of a paper (the stored PDF)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.UPLOADED.value, nullable=False, index=True
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer)

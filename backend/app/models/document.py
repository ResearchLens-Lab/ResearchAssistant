import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, TimestampMixin, generate_uuid


class DocumentStatus(str, enum.Enum):
    """Single source of truth for processing status; RAG reports results back
    to the backend rather than keeping its own status system."""

    UPLOADED = "uploaded"
    VALIDATING = "validating"
    QUEUED = "queued"
    INSPECTING = "inspecting"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    OCR_PROCESSING = "ocr_processing"
    STRUCTURING = "structuring"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "indexed"
    INDEXED = "indexed"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    processing_stage: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    processing_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_progress_type: Mapped[str] = mapped_column(String(16), default="estimated", nullable=False)
    processing_completed_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_total_units: Mapped[Optional[int]] = mapped_column(Integer)
    processing_unit: Mapped[Optional[str]] = mapped_column(String(16))
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    processing_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer)

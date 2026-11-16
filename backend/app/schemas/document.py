from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class DocumentResponse(BaseModel):
    """`storage_path` is internal and deliberately never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    paper_id: str
    filename: str
    content_type: str
    file_size: int
    processing_status: str
    processing_error: Optional[str] = None
    processing_stage: str = "uploaded"
    processing_progress: int = 0
    processing_progress_type: str = "estimated"
    processing_completed_units: int = 0
    processing_total_units: Optional[int] = None
    processing_unit: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_heartbeat_at: Optional[datetime] = None
    chunk_count: Optional[int] = None
    cleanup_status: Optional[str] = None
    operation_type: Optional[str] = None
    index_version: int = 1
    reindex_required: bool = False
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "processing_started_at",
        "processing_heartbeat_at",
        "created_at",
        "updated_at",
        when_used="json",
    )
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.isoformat() + "Z"
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class DocumentUploadOutcome(str):
    """Per-file upload result type."""
    STORED_NEW = "stored_new"
    ALREADY_INDEXED = "already_indexed"
    EXISTING_JOB = "existing_job"
    RETRY_AVAILABLE = "retry_available"
    CLEANUP_IN_PROGRESS = "cleanup_in_progress"
    CLEANUP_FAILED = "cleanup_failed"
    FAILED = "failed"


class DocumentUploadResult(BaseModel):
    """Per-file upload result."""
    filename: Optional[str] = None
    document: Optional[DocumentResponse] = None
    outcome: str  # DocumentUploadOutcome values
    success: bool = True
    error: Optional[str] = None
    message: Optional[str] = None


class DocumentBatchUploadResponse(BaseModel):
    """Batch upload response with per-file results."""
    results: list[DocumentUploadResult]
    success_count: int
    failure_count: int


class PaperDocumentsRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=1, max_length=100)

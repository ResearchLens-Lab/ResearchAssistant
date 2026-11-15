from datetime import datetime, timezone
from typing import Optional

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
    reindex_required: bool = False
    index_version: int = 2
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


class PaperDocumentsRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=1, max_length=100)

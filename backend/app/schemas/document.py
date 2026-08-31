from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    chunk_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

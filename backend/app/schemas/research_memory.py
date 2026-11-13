from pydantic import BaseModel, Field


class MemoryFormationRequest(BaseModel):
    node_ids: list[str] = Field(default_factory=list, max_length=200)
    relationship_ids: list[str] = Field(default_factory=list, max_length=200)
    allow_private: bool = False


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    scope_id: str | None = None
    document_ids: list[str] | None = Field(default=None, max_length=200)
    memory_types: list[str] | None = Field(default=None, max_length=7)
    limit: int = Field(default=20, ge=1, le=100)


class MemoryAssociationReview(BaseModel):
    action: str


class MemoryGapCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    gap_type: str
    scope: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=4000)
    inspected_sources: list[dict] = Field(default_factory=list, max_length=200)


class MemoryGapResolution(BaseModel):
    status: str
    resolution_memory_id: str | None = None


class MemoryContradictionResolution(BaseModel):
    outcome: str
    context: dict = Field(default_factory=dict)


class MemoryFeedbackRequest(BaseModel):
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str
    action: str
    details: dict = Field(default_factory=dict)


class SessionMemoryOptInRequest(BaseModel):
    enabled: bool


class SessionMemoryCaptureRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)

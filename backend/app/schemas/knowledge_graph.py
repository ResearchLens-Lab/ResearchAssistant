from pydantic import BaseModel, Field


class GraphImportRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=100)
    extraction_run_id: str = Field(min_length=1, max_length=100)
    allow_private: bool = False


class GraphImportConfirmRequest(GraphImportRequest):
    confirm: bool


class CandidateReviewRequest(BaseModel):
    action: str
    node_type: str | None = None
    canonical_name: str | None = None
    existing_node_id: str | None = None
    allow_private: bool = False


class RelationshipCreateRequest(BaseModel):
    candidate_id: str
    source_node_id: str
    relationship_type: str
    target_node_id: str
    allow_private: bool = False


class NodeCorrectionRequest(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=500)
    node_type: str = Field(min_length=1, max_length=40)
    identifiers: dict = Field(default_factory=dict)


class RelationshipCorrectionRequest(BaseModel):
    source_node_id: str
    relationship_type: str
    target_node_id: str


class RelationshipStatusRequest(BaseModel):
    status: str
    reason: str = Field(min_length=1, max_length=2000)


class AliasCreateRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=500)


class IdentityDecisionRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    reason: str = Field(min_length=1, max_length=2000)


class MergeRequest(BaseModel):
    primary_node_id: str
    duplicate_node_id: str
    reason: str = Field(min_length=1, max_length=2000)


class UndoMergeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class GraphRollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

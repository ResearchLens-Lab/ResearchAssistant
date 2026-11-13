from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class EvidenceRequest(QuestionRequest):
    paper_ids: list[str] = Field(default_factory=list, max_length=20)
    document_ids: list[str] = Field(default_factory=list, max_length=40)
    result_limit: int = Field(default=20, ge=1, le=50)


class ClaimRequest(EvidenceRequest):
    pass


class CompareRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=2, max_length=4)


class ExternalLookupRequest(BaseModel):
    doi: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=250)
    authors: list[str] = Field(default_factory=list, max_length=20)
    year: int | None = Field(default=None, ge=1400, le=2200)


class QualityReviewRequest(BaseModel):
    profile: dict[str, str]
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)

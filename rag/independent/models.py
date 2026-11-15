from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource


class QuestionIntent(str, Enum):
    AUTHOR_LOOKUP = "AUTHOR_LOOKUP"
    DEFINITION = "DEFINITION"
    EXPLANATION = "EXPLANATION"
    FACT_LOOKUP = "FACT_LOOKUP"
    NUMERICAL_QUERY = "NUMERICAL_QUERY"
    DATE_LOOKUP = "DATE_LOOKUP"
    LIST_EXTRACTION = "LIST_EXTRACTION"
    COMPARISON = "COMPARISON"
    SUMMARY = "SUMMARY"
    METHODOLOGY_EXTRACTION = "METHODOLOGY_EXTRACTION"
    DATASET_EXTRACTION = "DATASET_EXTRACTION"
    METRIC_EXTRACTION = "METRIC_EXTRACTION"
    ADVANTAGES_DISADVANTAGES = "ADVANTAGES_DISADVANTAGES"
    PROCEDURAL_QUESTION = "PROCEDURAL_QUESTION"
    EVIDENCE_LOOKUP = "EVIDENCE_LOOKUP"
    TABLE_SYNTHESIS = "TABLE_SYNTHESIS"
    CHART_SYNTHESIS = "CHART_SYNTHESIS"
    DIAGRAM_SYNTHESIS = "DIAGRAM_SYNTHESIS"
    LIMITATIONS_EXTRACTION = "LIMITATIONS_EXTRACTION"
    ALGORITHMS_EXTRACTION = "ALGORITHMS_EXTRACTION"
    DEEP_EXPLANATION = "DEEP_EXPLANATION"
    SIMPLIFIED_EXPLANATION = "SIMPLIFIED_EXPLANATION"
    PRACTICAL_EXAMPLE = "PRACTICAL_EXAMPLE"
    UNKNOWN = "UNKNOWN"


class QueryAnalysis(BaseModel):
    intent: QuestionIntent
    normalized_question: str
    search_query: str
    entities: list[str] = Field(default_factory=list)
    important_terms: list[str] = Field(default_factory=list)
    expanded_terms: list[str] = Field(default_factory=list)
    document_filters: dict[str, Any] = Field(default_factory=dict)
    retrieval_strategy: list[str] = Field(default_factory=list)
    expected_answer_structure: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)


class ExtractedFact(BaseModel):
    fact_type: str
    value: str
    source_id: str
    paper_id: str
    document_id: str
    source_filename: str | None = None
    physical_page: int | None = None
    chunk_id: str
    section: str
    supporting_passage: str
    extraction_method: str
    verification_status: str


class EvidenceDecision(BaseModel):
    status: str
    reasons: list[str] = Field(default_factory=list)
    supported_source_ids: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class IndependentAnswer(BaseModel):
    answer: str
    intent: QuestionIntent
    analysis: QueryAnalysis
    facts: list[ExtractedFact] = Field(default_factory=list)
    evidence_decision: EvidenceDecision
    sources: list[RetrievedSource] = Field(default_factory=list)
    retrieval_explanations: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

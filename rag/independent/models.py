from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource


class QuestionIntent(str, Enum):
    TOPIC_COUNT_RANKING = "TOPIC_COUNT_RANKING"
    TOPIC_COVERAGE_ANALYSIS = "TOPIC_COVERAGE_ANALYSIS"
    TOPIC_EXTRACTION = "TOPIC_EXTRACTION"
    SECTION_COMPARISON = "SECTION_COMPARISON"
    SECTION_SUMMARY = "SECTION_SUMMARY"
    DIRECT_DEFINITION = "DIRECT_DEFINITION"
    CONCEPT_EXPLANATION = "CONCEPT_EXPLANATION"
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    DOCUMENT_COMPARISON = "DOCUMENT_COMPARISON"
    METHOD_EXTRACTION = "METHOD_EXTRACTION"
    ALGORITHM_EXTRACTION = "ALGORITHM_EXTRACTION"
    DATASET_EXTRACTION = "DATASET_EXTRACTION"
    NUMERICAL_RESULT_LOOKUP = "NUMERICAL_RESULT_LOOKUP"
    LIMITATIONS_EXTRACTION = "LIMITATIONS_EXTRACTION"
    RESEARCH_GAP_ANALYSIS = "RESEARCH_GAP_ANALYSIS"
    CONTRADICTION_ANALYSIS = "CONTRADICTION_ANALYSIS"
    BIBLIOGRAPHIC_LOOKUP = "BIBLIOGRAPHIC_LOOKUP"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
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
    METRIC_EXTRACTION = "METRIC_EXTRACTION"
    ADVANTAGES_DISADVANTAGES = "ADVANTAGES_DISADVANTAGES"
    PROCEDURAL_QUESTION = "PROCEDURAL_QUESTION"
    EVIDENCE_LOOKUP = "EVIDENCE_LOOKUP"
    TABLE_SYNTHESIS = "TABLE_SYNTHESIS"
    CHART_SYNTHESIS = "CHART_SYNTHESIS"
    DIAGRAM_SYNTHESIS = "DIAGRAM_SYNTHESIS"
    ALGORITHMS_EXTRACTION = "ALGORITHMS_EXTRACTION"
    DEEP_EXPLANATION = "DEEP_EXPLANATION"
    SIMPLIFIED_EXPLANATION = "SIMPLIFIED_EXPLANATION"
    PRACTICAL_EXAMPLE = "PRACTICAL_EXAMPLE"
    PROCEDURE = "PROCEDURE"
    COMPLEXITY = "COMPLEXITY"
    THEOREM_LOOKUP = "THEOREM_LOOKUP"
    EXAMPLE = "EXAMPLE"
    LIST_PROPERTIES = "LIST_PROPERTIES"
    LOCATE = "LOCATE"
    SUMMARIZATION = "SUMMARIZATION"
    COUNT_RANKING = "COUNT_RANKING"
    RELATIONSHIP = "RELATIONSHIP"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class QueryAnalysis(BaseModel):
    intent: QuestionIntent
    normalized_question: str
    search_query: str
    target_concept: str | None = None
    entities: list[str] = Field(default_factory=list)
    important_terms: list[str] = Field(default_factory=list)
    expanded_terms: list[str] = Field(default_factory=list)
    document_filters: dict[str, Any] = Field(default_factory=dict)
    section_priors: dict[str, float] = Field(default_factory=dict)
    slot_constraints: dict[str, Any] = Field(default_factory=dict)
    retrieval_strategy: list[str] = Field(default_factory=list)
    expected_answer_structure: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    primary_phrase: str = ""


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

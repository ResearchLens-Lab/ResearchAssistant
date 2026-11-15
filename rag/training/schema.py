from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskType(StrEnum):
    INTENT = "intent"
    ENTITY = "entity"
    PASSAGE_RELEVANCE = "passage_relevance"
    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"
    CLAIM = "claim"
    RELATIONSHIP = "relationship"


class ExampleStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


ALLOWED_LABELS: dict[TaskType, set[str]] = {
    TaskType.INTENT: {
        "AUTHOR_LOOKUP", "DEFINITION", "EXPLANATION", "FACT_LOOKUP",
        "NUMERICAL_QUERY", "DATE_LOOKUP", "LIST_EXTRACTION", "COMPARISON",
        "SUMMARY", "METHODOLOGY_EXTRACTION", "DATASET_EXTRACTION",
        "METRIC_EXTRACTION", "ADVANTAGES_DISADVANTAGES", "PROCEDURAL_QUESTION",
        "EVIDENCE_LOOKUP", "UNKNOWN",
    },
    TaskType.PASSAGE_RELEVANCE: {"0", "1", "2", "3"},
    TaskType.EVIDENCE_SUFFICIENCY: {"sufficient", "insufficient", "conflicting", "partial"},
    TaskType.CLAIM: {"supported", "contradicted", "neutral", "unsupported"},
    TaskType.ENTITY: {
        "SEQUENCE", "PERSON", "AUTHOR", "ORGANIZATION", "INSTITUTION", "METHOD", "ALGORITHM",
        "DATASET", "METRIC", "TASK", "PROBLEM", "CONCEPT", "TOOL", "SOFTWARE", "NUMBER", "DATE", "OTHER",
    },
    TaskType.RELATIONSHIP: {
        "USES", "EVALUATED_ON", "REPORTS", "AUTHORED_BY", "CONTRADICTS", "RELATED_TO",
        "PROPOSES", "USES_METHOD", "REPORTS_METRIC", "COMPARED_WITH", "AFFILIATED_WITH",
        "DERIVED_FROM", "NO_RELATION",
    },
}


class DatasetExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: TaskType
    input_text: str = Field(min_length=1, max_length=20_000)
    candidate_passage: str | None = Field(default=None, max_length=50_000)
    expected_label: str = Field(min_length=1, max_length=100)
    expected_output: Any = None
    source_document_id: str | None = None
    paper_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    annotator: str | None = None
    reviewer: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = None
    review_status: ExampleStatus = ExampleStatus.PENDING
    dataset_version: str = "unversioned"
    source_group_id: str | None = None
    private_source: bool = False
    training_permission: bool = False

    @field_validator("expected_label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip().upper() if value.strip().upper() in {
            "AUTHOR_LOOKUP", "DEFINITION", "EXPLANATION", "FACT_LOOKUP", "NUMERICAL_QUERY",
            "DATE_LOOKUP", "LIST_EXTRACTION", "COMPARISON", "SUMMARY", "METHODOLOGY_EXTRACTION",
            "DATASET_EXTRACTION", "METRIC_EXTRACTION", "ADVANTAGES_DISADVANTAGES",
            "PROCEDURAL_QUESTION", "EVIDENCE_LOOKUP", "UNKNOWN", "AUTHOR", "METHOD",
            "PERSON", "ORGANIZATION", "INSTITUTION", "ALGORITHM", "TASK", "PROBLEM", "CONCEPT", "TOOL", "SOFTWARE", "SEQUENCE",
            "DATASET", "METRIC", "NUMBER", "DATE", "OTHER", "USES", "EVALUATED_ON",
            "REPORTS", "AUTHORED_BY", "CONTRADICTS", "RELATED_TO", "PROPOSES", "USES_METHOD",
            "REPORTS_METRIC", "COMPARED_WITH", "AFFILIATED_WITH", "DERIVED_FROM", "NO_RELATION",
        } else value.strip().lower()

    @model_validator(mode="after")
    def validate_task_fields(self) -> "DatasetExample":
        if self.expected_label not in ALLOWED_LABELS[self.task_type]:
            raise ValueError(f"Invalid label {self.expected_label!r} for task {self.task_type.value}")
        if self.task_type == TaskType.PASSAGE_RELEVANCE and not self.candidate_passage:
            raise ValueError("passage_relevance examples require candidate_passage")
        if self.task_type == TaskType.ENTITY and self.expected_label == "SEQUENCE":
            self._validate_spans(self.expected_output.get("entities") if isinstance(self.expected_output, dict) else None)
        if self.task_type == TaskType.RELATIONSHIP:
            if not isinstance(self.expected_output, dict):
                raise ValueError("relationship examples require subject/object spans in expected_output")
            self._validate_spans([self.expected_output.get("subject"), self.expected_output.get("object")])
            additional = self.expected_output.get("additional_relationships", [])
            if not isinstance(additional, list) or any(label not in ALLOWED_LABELS[TaskType.RELATIONSHIP] - {"NO_RELATION"} for label in additional):
                raise ValueError("additional_relationships must contain valid positive relationship labels")
            if len(additional) != len(set(additional)) or self.expected_label in additional:
                raise ValueError("relationship labels for one pair must be unique")
            if self.expected_label == "NO_RELATION" and additional:
                raise ValueError("NO_RELATION examples cannot include additional positive relationships")
            if self.expected_label != "NO_RELATION" and "NO_RELATION" in additional:
                raise ValueError("positive relationship examples cannot include NO_RELATION")
        if self.review_status == ExampleStatus.APPROVED:
            if not self.reviewer or not self.reviewed_at:
                raise ValueError("approved examples require reviewer and reviewed_at")
            if self.private_source and not self.training_permission:
                raise ValueError("private-source examples require explicit training_permission")
        return self

    def _validate_spans(self, spans: Any) -> None:
        text = self.candidate_passage or self.input_text
        if not isinstance(spans, list) or (not spans and self.task_type == TaskType.RELATIONSHIP):
            raise ValueError("expected_output requires a span list (relationship pairs cannot be empty)")
        for span in spans:
            if not isinstance(span, dict):
                raise ValueError("span annotations must be JSON objects")
            start, end = span.get("start"), span.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(text):
                raise ValueError("span offsets are invalid for the original passage")
            if span.get("text") is not None and text[start:end] != span["text"]:
                raise ValueError("annotated span text does not match its exact passage offsets")
            span_label = span.get("label", "")
            if self.task_type in {TaskType.ENTITY, TaskType.RELATIONSHIP} and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", str(span_label).upper()):
                raise ValueError("entity span label must be a valid ontology identifier")

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.linear_model import LogisticRegression

from rag.training.datasets import validate_dataset
from rag.training.schema import DatasetExample, ExampleStatus, TaskType
from rag.training.nlp.tokenization import Token, char_span_to_token_range, tokenize, token_feature_rows
from rag.training.nlp.features import HASH_BINS, hashed_row, make_hasher


DEFAULT_ENTITY_TYPES = (
    "PERSON", "ORGANIZATION", "METHOD", "DATASET", "METRIC", "TASK", "CONCEPT", "TOOL",
)
ENTITY_ALIASES = {
    "AUTHOR": "PERSON", "PERSON": "PERSON", "INSTITUTION": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION", "ALGORITHM": "METHOD", "METHOD": "METHOD",
    "DATASET": "DATASET", "METRIC": "METRIC", "PROBLEM": "TASK", "TASK": "TASK",
    "CONCEPT": "CONCEPT", "SOFTWARE": "TOOL", "TOOL": "TOOL",
}


class InsufficientTrainingData(ValueError):
    def __init__(self, message: str, readiness: dict[str, Any]):
        super().__init__(message)
        self.readiness = readiness


class SourceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_document_id: str
    paper_id: str | None = None
    page_number: int = Field(ge=1)
    chunk_id: str
    source_id: str | None = None
    filename: str | None = None
    locator: str | None = None


class EntitySpanAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    label: str
    text: str | None = None

    @model_validator(mode="after")
    def validate_order(self):
        if self.end <= self.start:
            raise ValueError("entity span end must be greater than start")
        return self


class EntityPrediction(EntitySpanAnnotation):
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    provenance: SourceProvenance


def canonical_entity_type(label: str, ontology: dict[str, str] | None = None) -> str:
    mapping = {**ENTITY_ALIASES, **(ontology or {})}
    normalized = label.strip().upper()
    if normalized not in mapping:
        raise ValueError(f"Entity type {label!r} is outside the configured ontology")
    return mapping[normalized]


def _span_rows(example: DatasetExample, ontology: dict[str, str] | None) -> list[dict[str, Any]]:
    if example.task_type != TaskType.ENTITY or example.expected_label != "SEQUENCE":
        return []
    expected = example.expected_output
    if not isinstance(expected, dict) or not isinstance(expected.get("entities"), list):
        raise ValueError(f"{example.example_id}: entity sequence requires expected_output.entities")
    text = example.candidate_passage or example.input_text
    spans = []
    for span in expected["entities"]:
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or text[start:end] != span.get("text", text[start:end]):
            raise ValueError(f"{example.example_id}: entity span does not match exact passage offsets")
        spans.append({"start": start, "end": end, "label": canonical_entity_type(span["label"], ontology), "text": text[start:end]})
    return spans


def encode_bio(text: str, spans: list[dict[str, Any]], tokens: list[Token] | None = None,
               ontology: dict[str, str] | None = None) -> tuple[list[Token], list[str]]:
    tokens = tokens if tokens is not None else tokenize(text)
    tags = ["O"] * len(tokens)
    occupied: set[int] = set()
    for span in sorted(spans, key=lambda item: (item["start"], item["end"])):
        start, end = span["start"], span["end"]
        label = canonical_entity_type(span["label"], ontology)
        if text[start:end] != span.get("text", text[start:end]):
            raise ValueError("span text does not exactly match source passage")
        first, last = char_span_to_token_range(text, tokens, start, end)
        indices = set(range(first, last + 1))
        if occupied & indices:
            raise ValueError("overlapping entity spans are not supported")
        occupied |= indices
        tags[first] = f"B-{label}"
        for index in range(first + 1, last + 1):
            tags[index] = f"I-{label}"
    return tokens, tags


def decode_bio(text: str, tokens: list[Token], tags: list[str], confidence: list[float] | None = None,
               provenance: SourceProvenance | None = None,
               allowed_types: set[str] | None = None) -> tuple[list[EntityPrediction], int]:
    if len(tokens) != len(tags) or (confidence is not None and len(confidence) != len(tags)):
        raise ValueError("BIO output length does not match token sequence")
    scores = confidence or [1.0] * len(tags)
    output: list[EntityPrediction] = []
    malformed = 0
    active_label: str | None = None
    active_start: int | None = None
    active_scores: list[float] = []

    def close(end_token_index: int) -> None:
        nonlocal active_label, active_start, active_scores
        if active_label is not None and active_start is not None:
            start = tokens[active_start].start
            end = tokens[end_token_index].end
            exact = text[start:end]
            if text[start:end] != exact:
                raise ValueError("decoded offsets do not match original passage")
            score = float(math.exp(sum(math.log(max(x, 1e-12)) for x in active_scores) / len(active_scores)))
            provenance_value = provenance or SourceProvenance(source_document_id="unresolved", page_number=1, chunk_id="unresolved")
            output.append(EntityPrediction(
                start=start, end=end, text=exact, label=active_label, confidence=score,
                uncertainty=1-score, provenance=provenance_value,
            ))
        active_label, active_start, active_scores = None, None, []

    for index, raw_tag in enumerate(tags):
        if index and tokens[index - 1].sentence_id != tokens[index].sentence_id:
            close(index - 1)
        if raw_tag == "O":
            close(index - 1)
            continue
        match = re.fullmatch(r"([BI])-([A-Z_]+)", raw_tag)
        valid_types = allowed_types or set(DEFAULT_ENTITY_TYPES)
        if not match or match.group(2) not in valid_types:
            malformed += 1
            close(index - 1)
            continue
        prefix, label = match.groups()
        if prefix == "I" and active_label != label:
            malformed += 1
            close(index - 1)
            prefix = "B"  # deterministic repair of orphan/mismatched I tags
        if prefix == "B":
            close(index - 1)
            active_label, active_start, active_scores = label, index, [float(scores[index])]
        else:
            active_scores.append(float(scores[index]))
    close(len(tokens) - 1)
    return output, malformed


def viterbi_bio_decode(emissions: np.ndarray, labels: list[str], sentence_ids: list[int] | None = None) -> list[int]:
    """Maximum-emission path under strict BIO start/continuation constraints."""
    if emissions.ndim != 2 or emissions.shape[1] != len(labels):
        raise ValueError("emission matrix and label list have incompatible shapes")
    if emissions.shape[0] == 0:
        return []
    parsed = [re.fullmatch(r"([BI])-([A-Z_]+)", label) if label != "O" else None for label in labels]
    n_tokens, n_labels = emissions.shape
    neg = -1e30
    dp = np.full((n_tokens, n_labels), neg, dtype=np.float64)
    back = np.zeros((n_tokens, n_labels), dtype=np.int32)
    for label_index, label in enumerate(labels):
        if label == "O" or (parsed[label_index] and parsed[label_index].group(1) == "B"):
            dp[0, label_index] = math.log(max(float(emissions[0, label_index]), 1e-12))
    for position in range(1, n_tokens):
        new_sentence = sentence_ids is not None and sentence_ids[position] != sentence_ids[position - 1]
        for current, label in enumerate(labels):
            current_match = parsed[current]
            allowed_previous = []
            for previous, prev_label in enumerate(labels):
                prev_match = parsed[previous]
                valid = label == "O" or (current_match and current_match.group(1) == "B")
                if current_match and current_match.group(1) == "I":
                    valid = bool(not new_sentence and prev_match and prev_match.group(2) == current_match.group(2))
                if valid:
                    allowed_previous.append(previous)
            if allowed_previous:
                candidates = [(dp[position - 1, prev] + math.log(max(float(emissions[position, current]), 1e-12)), prev) for prev in allowed_previous]
                value, prior = max(candidates, key=lambda pair: (pair[0], -pair[1]))
                dp[position, current], back[position, current] = value, prior
    cursor = int(np.argmax(dp[-1]))
    output = [cursor]
    for position in range(n_tokens - 1, 0, -1):
        cursor = int(back[position, cursor])
        output.append(cursor)
    output.reverse()
    return output


@dataclass
class EntityRecognizer:
    vectorizer: Any
    classifier: LogisticRegression
    ontology: dict[str, str]
    label_config: tuple[str, ...]
    model_version: str = "1"

    def extract(self, text: str, provenance: SourceProvenance, min_confidence: float = 0.0) -> dict[str, Any]:
        tokens = tokenize(text)
        if not tokens:
            return {"entities": [], "malformed_span_count": 0, "model_version": self.model_version}
        matrix = self.vectorizer.transform([hashed_row(row) for row in token_feature_rows(tokens)])
        probabilities = self.classifier.predict_proba(matrix)
        path = viterbi_bio_decode(probabilities, list(self.classifier.classes_), [token.sentence_id for token in tokens])
        tags = [self.classifier.classes_[index] for index in path]
        scores = [float(probabilities[i, path[i]]) for i in range(len(path))]
        entities, malformed = decode_bio(text, tokens, tags, scores, provenance,
                                         set(DEFAULT_ENTITY_TYPES) | set(self.ontology.values()))
        entities = [entity for entity in entities if entity.confidence >= min_confidence]
        for entity in entities:
            if text[entity.start:entity.end] != entity.text:
                raise ValueError("entity span failed exact source-text validation")
        return {"entities": entities, "malformed_span_count": malformed, "model_version": self.model_version}


def train_entity_recognizer(items: list[DatasetExample], split_manifest: dict,
                            ontology: dict[str, str] | None = None,
                            min_spans: int = 50, min_documents: int = 5,
                            min_per_type: int = 5) -> EntityRecognizer:
    selected = [item for item in items if item.task_type == TaskType.ENTITY]
    train_ids = set(split_manifest.get("train_ids", []))
    if not train_ids or any(item.example_id not in train_ids for item in selected):
        raise ValueError("entity fitting accepts only examples assigned to the frozen training split")
    if any(item.review_status != ExampleStatus.APPROVED for item in selected):
        raise ValueError("entity training requires approved annotations only")
    if any(item.private_source and not item.training_permission for item in selected):
        raise ValueError("private entity examples require explicit training permission")
    if any(_is_synthetic(item) for item in selected):
        raise ValueError("synthetic examples are excluded from real-data entity candidate training")
    docs = {item.source_group_id or item.paper_id or item.source_document_id for item in selected}
    quality = validate_dataset(selected, require_reviewed=True)
    if not quality["valid"]:
        raise ValueError(f"entity dataset failed provenance/quality validation: {quality['errors']}")
    counts: Counter[str] = Counter()
    token_features: list[dict[str, Any]] = []
    token_labels: list[str] = []
    total_spans = 0
    for example in selected:
        text = example.candidate_passage or example.input_text
        spans = _span_rows(example, ontology)
        counts.update(span["label"] for span in spans)
        total_spans += len(spans)
        tokens, tags = encode_bio(text, spans, ontology=ontology)
        token_features.extend(token_feature_rows(tokens))
        token_labels.extend(tags)
    readiness = {"approved_real_examples": len(selected), "entity_spans": total_spans,
                 "independent_documents": len(docs), "span_counts_by_type": dict(counts)}
    lacking = [label for label, count in counts.items() if count < min_per_type]
    if total_spans < min_spans or len(docs) < min_documents or not counts or lacking:
        raise InsufficientTrainingData(
            f"entity candidate refused: needs >= {min_spans} spans across >= {min_documents} documents and >= {min_per_type} per observed type",
            {**readiness, "minimums": {"spans": min_spans, "documents": min_documents, "per_type": min_per_type}, "underrepresented_types": lacking},
        )
    if len(set(token_labels)) < 2:
        raise InsufficientTrainingData("entity candidate requires at least two BIO labels including background", readiness)
    vectorizer = make_hasher()
    matrix = vectorizer.transform([hashed_row(row) for row in token_features])
    classifier = LogisticRegression(max_iter=200, solver="lbfgs", class_weight="balanced", random_state=17)
    classifier.fit(matrix, token_labels)
    return EntityRecognizer(vectorizer, classifier, ontology or {}, tuple(sorted(counts)))


def _is_synthetic(item: DatasetExample) -> bool:
    version = item.dataset_version.casefold()
    provenance = item.provenance
    return version.startswith(("synthetic", "phase2-smoke", "phase3-smoke")) or bool(provenance.get("not_real_document")) or provenance.get("data_origin") == "synthetic"

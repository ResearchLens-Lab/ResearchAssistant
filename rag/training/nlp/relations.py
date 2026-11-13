from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from rag.training.datasets import validate_dataset
from rag.training.nlp.entities import (
    EntityPrediction, EntitySpanAnnotation, InsufficientTrainingData, SourceProvenance,
    _is_synthetic,
)
from rag.training.nlp.tokenization import Token, char_span_to_token_range, sentence_bounds, tokenize
from rag.training.nlp.features import hashed_row, make_hasher
from rag.training.schema import DatasetExample, ExampleStatus, TaskType


RELATION_TYPES = (
    "AUTHORED_BY", "PROPOSES", "USES_METHOD", "EVALUATED_ON", "REPORTS_METRIC",
    "COMPARED_WITH", "AFFILIATED_WITH", "DERIVED_FROM", "NO_RELATION",
)


class CandidateEntity(EntitySpanAnnotation):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class CandidatePair:
    subject: CandidateEntity
    object: CandidateEntity
    subject_token_start: int
    subject_token_end: int
    object_token_start: int
    object_token_end: int


class RelationshipPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: EntitySpanAnnotation
    relationship: str
    object: EntitySpanAnnotation
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    supporting_sentence: str
    sentence_start: int = Field(ge=0)
    sentence_end: int = Field(gt=0)
    provenance: SourceProvenance


def generate_candidate_pairs(text: str, entities: list[EntitySpanAnnotation | dict[str, Any]],
                             tokens: list[Token] | None = None, max_token_distance: int = 40,
                             max_pairs: int = 300) -> tuple[list[CandidatePair], list[Token]]:
    if max_token_distance < 0 or max_pairs < 1:
        raise ValueError("max_token_distance must be nonnegative and max_pairs must be positive")
    tokens = tokens or tokenize(text)
    normalized: list[tuple[CandidateEntity, int, int, int]] = []
    for raw in entities:
        if isinstance(raw, EntitySpanAnnotation):
            payload = raw.model_dump(include={"start", "end", "label", "text"})
        elif isinstance(raw, dict):
            payload = {key: raw.get(key) for key in ("start", "end", "label", "text")}
        else:
            payload = raw
        entity = CandidateEntity.model_validate(payload)
        if text[entity.start:entity.end] != (entity.text or text[entity.start:entity.end]):
            raise ValueError("candidate entity does not match exact source offsets")
        first, last = char_span_to_token_range(text, tokens, entity.start, entity.end)
        normalized.append((entity.model_copy(update={"text": text[entity.start:entity.end]}), first, last, tokens[first].sentence_id))
    normalized.sort(key=lambda row: (row[1], row[2]))
    pairs: list[CandidatePair] = []
    for subject_index, subject in enumerate(normalized):
        for object_index, object_ in enumerate(normalized):
            if subject_index == object_index or subject[3] != object_[3]:
                continue
            if subject[0].start < object_[0].end and object_[0].start < subject[0].end:
                continue
            distance = max(0, max(object_[1] - subject[2] - 1, subject[1] - object_[2] - 1))
            if distance > max_token_distance:
                continue
            pairs.append(CandidatePair(subject[0], object_[0], subject[1], subject[2], object_[1], object_[2]))
            if len(pairs) >= max_pairs:
                return pairs, tokens
    return pairs, tokens


def _pair_features(text: str, tokens: list[Token], pair: CandidatePair) -> dict[str, str | int | bool]:
    s0, s1 = pair.subject_token_start, pair.subject_token_end
    o0, o1 = pair.object_token_start, pair.object_token_end
    left0, right0 = sorted((s0, o0))
    left1 = s1 if s0 < o0 else o1
    right1 = o0 if s0 < o0 else s1
    between = [token.text.casefold() for token in tokens[left1 + 1:right0]]
    sentence_start, sentence_end, sentence = sentence_bounds(text, tokens, s0)
    features: dict[str, str | int | bool] = {
        "subject_type": pair.subject.label.upper(), "object_type": pair.object.label.upper(),
        "subject_text": (pair.subject.text or "").casefold(),
        "object_text": (pair.object.text or "").casefold(),
        "token_distance": min(abs(o0 - s1), 100), "same_sentence": True,
        "subject_before_object": s0 < o0,
        "between_text": " ".join(between[:20]),
        "sentence_first": tokens[sentence_start].text.casefold(),
        "sentence_last": tokens[sentence_end].text.casefold(),
        "sentence_length": min(sentence_end - sentence_start + 1, 100),
    }
    for offset, index in enumerate(range(max(0, left0 - 4), left0)):
        if tokens[index].sentence_id == tokens[left0].sentence_id:
            features[f"before_{offset}"] = tokens[index].text.casefold()
    for offset, index in enumerate(range(right1 + 1, min(len(tokens), right1 + 5))):
        if tokens[index].sentence_id == tokens[right1].sentence_id:
            features[f"after_{offset}"] = tokens[index].text.casefold()
    # Bounded lexical context features from the supporting sentence.
    for word in re.findall(r"[\w-]+", sentence.casefold())[:80]:
        features[f"ctx={word}"] = True
    return features


def _example_pair(example: DatasetExample) -> tuple[str, CandidatePair, list[Token]]:
    text = example.candidate_passage or example.input_text
    output = example.expected_output
    if not isinstance(output, dict) or not isinstance(output.get("subject"), dict) or not isinstance(output.get("object"), dict):
        raise ValueError(f"{example.example_id}: relationship annotation requires subject and object spans")
    pair_rows, tokens = generate_candidate_pairs(text, [output["subject"], output["object"]], max_token_distance=10_000)
    expected_starts = (output["subject"]["start"], output["object"]["start"])
    pair = next((p for p in pair_rows if p.subject.start == expected_starts[0] and p.object.start == expected_starts[1]), None)
    if pair is None:
        raise ValueError(f"{example.example_id}: annotated entity pair is not a same-sentence candidate")
    return text, pair, tokens


@dataclass
class RelationshipExtractor:
    vectorizer: Any
    classifier: Any
    label_config: tuple[str, ...]
    model_version: str = "1"
    confidence_threshold: float = .65

    def extract(self, text: str, entities: list[EntityPrediction | EntitySpanAnnotation | dict[str, Any]],
                provenance: SourceProvenance, min_confidence: float | None = None,
                max_token_distance: int = 40) -> dict[str, Any]:
        min_confidence = self.confidence_threshold if min_confidence is None else min_confidence
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between zero and one")
        candidates, tokens = generate_candidate_pairs(text, list(entities), max_token_distance=max_token_distance)
        if not candidates:
            return {"relationships": [], "candidate_count": 0, "model_version": self.model_version}
        matrix = self.vectorizer.transform([hashed_row(_pair_features(text, tokens, pair)) for pair in candidates])
        probabilities = self.classifier.predict_proba(matrix)
        classes = list(self.label_config)
        output: list[RelationshipPrediction] = []
        for pair, row in zip(candidates, probabilities):
            positive = [(classes[i], float(prob)) for i, prob in enumerate(row)
                        if classes[i] != "NO_RELATION" and prob >= min_confidence]
            if not positive:
                idx = classes.index("NO_RELATION")
                selected = [("NO_RELATION", float(row[idx]))]
            else:
                selected = positive  # preserve each independently supported relation above threshold
            sentence_start, sentence_end, sentence = sentence_bounds(text, tokens, pair.subject_token_start)
            for label, confidence in selected:
                output.append(RelationshipPrediction(
                    subject=pair.subject, relationship=label, object=pair.object,
                    confidence=confidence, uncertainty=1-confidence,
                    supporting_sentence=sentence, sentence_start=sentence_start,
                    sentence_end=sentence_end, provenance=provenance,
                ))
        return {"relationships": output, "candidate_count": len(candidates), "model_version": self.model_version}


def train_relationship_extractor(items: list[DatasetExample], split_manifest: dict,
                                 min_pairs: int = 50, min_documents: int = 5,
                                 min_per_label: int = 5) -> RelationshipExtractor:
    selected = [item for item in items if item.task_type == TaskType.RELATIONSHIP]
    train_ids = set(split_manifest.get("train_ids", []))
    if not train_ids or any(item.example_id not in train_ids for item in selected):
        raise ValueError("relationship fitting accepts only examples assigned to the frozen training split")
    if any(item.review_status != ExampleStatus.APPROVED for item in selected):
        raise ValueError("relationship training requires reviewed approved examples")
    if any(item.private_source and not item.training_permission for item in selected):
        raise ValueError("private relationship examples require explicit permission")
    if any(_is_synthetic(item) for item in selected):
        raise ValueError("synthetic examples are excluded from real-data relationship candidate training")
    quality = validate_dataset(selected, require_reviewed=True)
    if not quality["valid"]:
        raise ValueError(f"relationship dataset failed provenance/quality validation: {quality['errors']}")
    labels: Counter[str] = Counter()
    target_sets = []
    for item in selected:
        label_set = {item.expected_label}
        label_set.update((item.expected_output or {}).get("additional_relationships", []))
        target_sets.append(label_set)
        labels.update(label_set)
    docs = {item.source_group_id or item.paper_id or item.source_document_id for item in selected}
    lacking = [label for label, count in labels.items() if count < min_per_label]
    readiness = {"approved_real_pairs": len(selected), "independent_documents": len(docs), "label_counts": dict(labels)}
    if (len(selected) < min_pairs or len(docs) < min_documents or "NO_RELATION" not in labels
            or not (set(labels) - {"NO_RELATION"}) or lacking):
        raise InsufficientTrainingData(
            f"relationship candidate refused: needs >= {min_pairs} labelled pairs across >= {min_documents} papers, both NO_RELATION and positive labels, and >= {min_per_label} per observed label",
            {**readiness, "minimums": {"pairs": min_pairs, "documents": min_documents, "per_label": min_per_label}, "underrepresented_labels": lacking},
        )
    feature_rows: list[dict[str, Any]] = []
    for example in selected:
        text, pair, tokens = _example_pair(example)
        feature_rows.append(_pair_features(text, tokens, pair))
    if len(labels) < 2:
        raise InsufficientTrainingData("relationship model requires NO_RELATION and a positive relationship class", readiness)
    vectorizer = make_hasher()
    matrix = vectorizer.transform([hashed_row(row) for row in feature_rows])
    mlb = MultiLabelBinarizer(classes=sorted(labels))
    binary_target = mlb.fit_transform(target_sets)
    classifier = OneVsRestClassifier(LogisticRegression(max_iter=250, solver="lbfgs", class_weight="balanced", random_state=17))
    classifier.fit(matrix, binary_target)
    return RelationshipExtractor(vectorizer, classifier, tuple(mlb.classes_))

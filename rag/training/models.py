from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from rag.training.schema import DatasetExample, TaskType


MAX_FEATURES = 20_000


def _training_text(item: DatasetExample) -> str:
    return f"{item.input_text}\n{item.candidate_passage or ''}"


def _assert_training_eligible(items: list[DatasetExample]) -> None:
    for item in items:
        if item.review_status.value != "approved":
            raise ValueError(f"training rejected unreviewed example {item.example_id}")
        if item.private_source and not item.training_permission:
            raise ValueError(f"training rejected private example without explicit permission: {item.example_id}")


def train_intent_classifier(items: list[DatasetExample]) -> Pipeline:
    return train_task_classifier(items, TaskType.INTENT)


def train_task_classifier(items: list[DatasetExample], task: TaskType) -> Pipeline:
    """Classical categorical classifier. Entity labels apply to supplied spans, not token NER."""
    if task == TaskType.PASSAGE_RELEVANCE:
        return train_passage_ranker(items)
    _assert_training_eligible(items)
    selected = [item for item in items if item.task_type == task]
    labels = [item.expected_label for item in selected]
    if len(selected) < 6 or len(set(labels)) < 2:
        raise ValueError(f"{task.value} training requires at least six examples and two classes")
    model = Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True, strip_accents="unicode", ngram_range=(1, 2),
            max_features=MAX_FEATURES, min_df=1, sublinear_tf=True,
            dtype=np.float32, token_pattern=r"(?u)\b\w+\b",
        )),
        ("classifier", LogisticRegression(
            max_iter=300, solver="lbfgs", class_weight="balanced", random_state=17,
        )),
    ])
    model.fit([item.input_text for item in selected], labels)
    return model


def train_passage_ranker(items: list[DatasetExample]) -> Pipeline:
    _assert_training_eligible(items)
    selected = [item for item in items if item.task_type == TaskType.PASSAGE_RELEVANCE]
    labels = [int(item.expected_label) >= 2 for item in selected]
    if len(selected) < 8 or len(set(labels)) < 2:
        raise ValueError("ranker training requires at least eight approved pairs and relevant/irrelevant labels")
    model = Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True, strip_accents="unicode", ngram_range=(1, 2),
            max_features=MAX_FEATURES, min_df=1, sublinear_tf=True,
            dtype=np.float32, token_pattern=r"(?u)\b\w+\b",
        )),
        ("classifier", LogisticRegression(
            max_iter=300, solver="lbfgs", class_weight="balanced", random_state=17,
        )),
    ])
    model.fit([_training_text(item) for item in selected], labels)
    return model


def predict_relevance(model: Pipeline, question: str, passage: str) -> float:
    return float(model.predict_proba([f"{question}\n{passage}"])[0][list(model.classes_).index(True)])


def lexical_relevance_baseline(question: str, passage: str) -> float:
    tokens = lambda text: set(re.findall(r"[\w]+", text.casefold()))
    q = tokens(question)
    p = tokens(passage)
    return len(q & p) / len(q) if q else 0.0


def deterministic_intent_baseline(question: str) -> str:
    from rag.independent.intent_classifier import QuestionIntentClassifier
    return QuestionIntentClassifier().classify(question).intent.value


def class_counts(items: list[DatasetExample], task: TaskType) -> dict[str, int]:
    return dict(Counter(item.expected_label for item in items if item.task_type == task))


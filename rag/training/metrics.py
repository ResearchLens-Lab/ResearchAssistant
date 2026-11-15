from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from rag.training.schema import DatasetExample, TaskType


def classification_metrics(expected: list[str], predicted: list[str], labels: list[str] | None = None) -> dict[str, object]:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("expected and predicted must be nonempty and have equal length")
    names = labels or sorted(set(expected) | set(predicted))
    precision, recall, f1, support = precision_recall_fscore_support(
        expected, predicted, labels=names, average=None, zero_division=0,
    )
    macro = precision_recall_fscore_support(expected, predicted, labels=names, average="macro", zero_division=0)
    return {
        "accuracy": float(accuracy_score(expected, predicted)),
        "macro_precision": float(macro[0]), "macro_recall": float(macro[1]), "macro_f1": float(macro[2]),
        "per_class": {
            label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(s)}
            for label, p, r, f, s in zip(names, precision, recall, f1, support)
        },
        "confusion_matrix": confusion_matrix(expected, predicted, labels=names).tolist(),
        "labels": names,
    }


def ranking_metrics(groups: dict[str, list[tuple[float, int]]], k: int = 5) -> dict[str, float]:
    if not groups:
        raise ValueError("ranking evaluation requires query groups")
    recall_values, reciprocal_ranks, ndcg_values = [], [], []
    for pairs in groups.values():
        ordered = sorted(pairs, key=lambda pair: pair[0], reverse=True)
        relevant_total = sum(1 for _, grade in pairs if grade > 0)
        found = next((rank for rank, (_, grade) in enumerate(ordered, 1) if grade > 0), None)
        recall_values.append(sum(1 for _, grade in ordered[:k] if grade > 0) / relevant_total if relevant_total else 0.0)
        reciprocal_ranks.append(1 / found if found else 0.0)
        dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, (_, grade) in enumerate(ordered[:k], 1))
        ideal = sorted((grade for _, grade in pairs), reverse=True)[:k]
        idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, 1))
        ndcg_values.append(dcg / idcg if idcg else 0.0)
    mean = lambda xs: sum(xs) / len(xs)
    return {f"recall@{k}": mean(recall_values), "mrr": mean(reciprocal_ranks), f"ndcg@{k}": mean(ndcg_values)}


def evidence_metrics(expected: list[str], predicted: list[str]) -> dict[str, float]:
    positive = {"sufficient", "supported"}
    gold = [label.casefold() in positive for label in expected]
    pred = [label.casefold() in positive for label in predicted]
    tp = sum(g and p for g, p in zip(gold, pred)); fp = sum(not g and p for g, p in zip(gold, pred))
    fn = sum(g and not p for g, p in zip(gold, pred)); tn = sum(not g and not p for g, p in zip(gold, pred))
    return {
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_support_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_abstention_rate": fn / (fn + tp) if fn + tp else 0.0,
    }


def exact_entity_metrics(expected: list[set[str]], predicted: list[set[str]]) -> dict[str, float]:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("entity lists must be nonempty and equally sized")
    tp = sum(len(a & b) for a, b in zip(expected, predicted))
    fp = sum(len(b - a) for a, b in zip(expected, predicted))
    fn = sum(len(a - b) for a, b in zip(expected, predicted))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"exact_match_precision": p, "exact_match_recall": r, "exact_match_f1": 2*p*r/(p+r) if p+r else 0.0}


def evaluate_intent_model(model, test_items: Iterable[DatasetExample]) -> dict[str, object]:
    items = [item for item in test_items if item.task_type == TaskType.INTENT]
    if not items:
        raise ValueError("no intent test examples")
    expected = [item.expected_label for item in items]
    predicted = list(model.predict([item.input_text for item in items]))
    result = classification_metrics(expected, predicted)
    from rag.training.models import deterministic_intent_baseline
    baseline = [deterministic_intent_baseline(item.input_text) for item in items]
    result["deterministic_baseline"] = classification_metrics(expected, baseline)
    return result


def evaluate_passage_model(model, test_items: Iterable[DatasetExample], k: int = 5) -> dict[str, object]:
    from rag.training.models import lexical_relevance_baseline, predict_relevance
    items = [item for item in test_items if item.task_type == TaskType.PASSAGE_RELEVANCE]
    if not items:
        raise ValueError("no passage-relevance test examples")
    model_groups: dict[str, list[tuple[float, int]]] = defaultdict(list)
    baseline_groups: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for item in items:
        group = str(item.provenance.get("query_group_id", item.input_text.strip().casefold()))
        grade = int(item.expected_label)
        passage = item.candidate_passage or ""
        model_groups[group].append((predict_relevance(model, item.input_text, passage), grade))
        baseline_groups[group].append((lexical_relevance_baseline(item.input_text, passage), grade))
    return {"trained_model": ranking_metrics(model_groups, k), "deterministic_baseline": ranking_metrics(baseline_groups, k)}

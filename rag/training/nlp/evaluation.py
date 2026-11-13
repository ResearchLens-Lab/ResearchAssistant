from __future__ import annotations

from collections import Counter
from typing import Any

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from rag.training.metrics import exact_entity_metrics
from rag.training.nlp.entities import SourceProvenance, canonical_entity_type, encode_bio
from rag.training.nlp.relations import _example_pair, _pair_features
from rag.training.nlp.tokenization import token_feature_rows
from rag.training.schema import DatasetExample, TaskType


def _provenance(example: DatasetExample) -> SourceProvenance:
    raw = example.provenance
    return SourceProvenance(
        source_document_id=example.source_document_id or "unknown",
        paper_id=example.paper_id, page_number=example.page_number or 1,
        chunk_id=example.chunk_id or "unknown", source_id=raw.get("source_id"),
        filename=raw.get("filename"), locator=raw.get("locator"),
    )


def evaluate_entity_model(model, examples: list[DatasetExample], split_manifest: dict,
                          partition: str = "test") -> dict[str, Any]:
    allowed_ids = set(split_manifest.get(f"{partition}_ids", [])); train_ids = set(split_manifest.get("train_ids", []))
    selected = [item for item in examples if item.task_type == TaskType.ENTITY]
    if not selected or any(item.example_id not in allowed_ids or (partition != "train" and item.example_id in train_ids) for item in selected):
        raise ValueError(f"entity evaluation requires frozen {partition} examples only")
    pred_sets: list[set[str]] = []; gold_sets: list[set[str]] = []
    type_totals: dict[str, tuple[list[set[str]], list[set[str]]]] = {}
    token_gold: list[str] = []; token_pred: list[str] = []
    malformed_total = 0
    for item in selected:
        text = item.candidate_passage or item.input_text
        spans = (item.expected_output or {}).get("entities", [])
        tokens, gold_tags = encode_bio(text, spans, ontology=model.ontology)
        provenance = _provenance(item)
        result = model.extract(text, provenance)
        malformed_total += result["malformed_span_count"]
        predicted = result["entities"]
        gold = {f"{span['start']}:{span['end']}:{canonical_entity_type(span['label'], model.ontology)}" for span in spans}
        pred = {f"{span.start}:{span.end}:{span.label}" for span in predicted}
        gold_sets.append(gold); pred_sets.append(pred)
        token_gold.extend(gold_tags)
        from rag.training.nlp.features import hashed_row
        token_matrix = model.vectorizer.transform([hashed_row(row) for row in token_feature_rows(tokens)])
        probabilities = model.classifier.predict_proba(token_matrix)
        from rag.training.nlp.entities import viterbi_bio_decode
        path = viterbi_bio_decode(probabilities, list(model.classifier.classes_), [token.sentence_id for token in tokens])
        token_pred.extend(model.classifier.classes_[index] for index in path)
    exact = exact_entity_metrics(gold_sets, pred_sets)
    all_types = {value.rsplit(":", 1)[-1] for group in (*gold_sets, *pred_sets) for value in group}
    all_types.update(model.label_config)
    for label in sorted(all_types):
        gold_rows = [{value for value in group if value.endswith(f":{label}")} for group in gold_sets]
        pred_rows = [{value for value in group if value.endswith(f":{label}")} for group in pred_sets]
        type_totals[label] = (gold_rows, pred_rows)
    per_type = {label: exact_entity_metrics(gold_rows, pred_rows) for label, (gold_rows, pred_rows) in type_totals.items() if any(gold_rows) or any(pred_rows)}
    labels = sorted(set(token_gold) | set(token_pred))
    precision, recall, f1, support = precision_recall_fscore_support(token_gold, token_pred, labels=labels, average=None, zero_division=0)
    return {
        "dataset_examples": len(selected),
        "independent_papers": len({item.source_group_id or item.paper_id or item.source_document_id for item in selected}),
        "exact_span": exact, "per_entity_type": per_type,
        "token_confusion_matrix": {"labels": labels, "matrix": confusion_matrix(token_gold, token_pred, labels=labels).tolist(),
                                    "per_label": {label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(s)}
                                                  for label, p, r, f, s in zip(labels, precision, recall, f1, support)}},
        "invalid_bio_transition_or_malformed_span_count": malformed_total,
        "deterministic_baseline": {"exact_span": exact_entity_metrics(gold_sets, [set() for _ in gold_sets]),
                                   "baseline": "all tokens outside entities (all-O)"},
    }


def evaluate_relationship_model(model, examples: list[DatasetExample], split_manifest: dict,
                                partition: str = "test", threshold: float = .5) -> dict[str, Any]:
    allowed_ids, train_ids = set(split_manifest.get(f"{partition}_ids", [])), set(split_manifest.get("train_ids", []))
    selected = [item for item in examples if item.task_type == TaskType.RELATIONSHIP]
    if not selected or any(item.example_id not in allowed_ids or (partition != "train" and item.example_id in train_ids) for item in selected):
        raise ValueError(f"relationship evaluation requires frozen {partition} examples only")
    expected_sets: list[set[str]] = []
    predicted_sets: list[set[str]] = []
    errors = []
    classes = list(model.label_config)
    for item in selected:
        text, pair, tokens = _example_pair(item)
        from rag.training.nlp.features import hashed_row
        features = model.vectorizer.transform([hashed_row(_pair_features(text, tokens, pair))])
        probs = model.classifier.predict_proba(features)[0]
        gold = {item.expected_label}
        gold.update((item.expected_output or {}).get("additional_relationships", []))
        guess = {classes[index] for index, score in enumerate(probs) if score >= threshold}
        if guess - {"NO_RELATION"}:
            guess.discard("NO_RELATION")
        if not guess:
            guess = {"NO_RELATION"} if "NO_RELATION" in classes else {classes[int(probs.argmax())]}
        expected_sets.append(gold); predicted_sets.append(guess)
        false_positive, false_negative = sorted(guess - gold), sorted(gold - guess)
        if false_positive or false_negative:
            errors.append({"example_id": item.example_id, "document_id": item.source_document_id,
                           "false_positive": false_positive, "false_negative": false_negative, "text": text})
    labels = classes
    from sklearn.preprocessing import MultiLabelBinarizer
    mlb = MultiLabelBinarizer(classes=labels)
    y_true = mlb.fit_transform(expected_sets); y_pred = mlb.transform(predicted_sets)
    micro = precision_recall_fscore_support(y_true, y_pred, average="micro", zero_division=0)
    macro = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    per = precision_recall_fscore_support(y_true, y_pred, average=None, zero_division=0)
    baseline_sets = [{"NO_RELATION"} for _ in expected_sets]
    baseline_y = mlb.transform(baseline_sets)
    baseline_micro = precision_recall_fscore_support(y_true, baseline_y, average="micro", zero_division=0)
    matrices = {}
    for index, label in enumerate(labels):
        matrices[label] = confusion_matrix(y_true[:, index], y_pred[:, index], labels=[0, 1]).tolist()
    gold_no_relation = sum(group == {"NO_RELATION"} for group in expected_sets)
    pred_no_relation = sum(group == {"NO_RELATION"} for group in predicted_sets)
    true_no_relation = sum(g == {"NO_RELATION"} and p == {"NO_RELATION"} for g, p in zip(expected_sets, predicted_sets))
    return {
        "dataset_examples": len(selected),
        "independent_papers": len({item.source_group_id or item.paper_id or item.source_document_id for item in selected}),
        "micro": {"precision": float(micro[0]), "recall": float(micro[1]), "f1": float(micro[2])},
        "macro": {"precision": float(macro[0]), "recall": float(macro[1]), "f1": float(macro[2])},
        "per_relationship_type": {label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(s)}
                                  for label, p, r, f, s in zip(labels, *per)},
        "confusion_matrices_by_relationship_type": matrices,
        "false_positive_and_false_negative_examples": errors,
        "no_relation": {"gold_count": gold_no_relation, "predicted_count": pred_no_relation,
                        "precision": true_no_relation / max(1, pred_no_relation),
                        "recall": true_no_relation / max(1, gold_no_relation)},
        "deterministic_baseline": {"label": "NO_RELATION for every candidate pair", "micro_f1": float(baseline_micro[2])},
    }


def select_relationship_threshold(model, validation_items: list[DatasetExample], split_manifest: dict,
                                  thresholds: tuple[float, ...] = (.4, .5, .6, .65, .7, .8)) -> dict[str, Any]:
    """Choose only on the frozen validation partition; never consult test labels here."""
    candidates = []
    for threshold in thresholds:
        result = evaluate_relationship_model(model, validation_items, split_manifest, "validation", threshold)
        candidates.append({"threshold": threshold, "macro_f1": result["macro"]["f1"],
                           "micro_f1": result["micro"]["f1"]})
    best = max(candidates, key=lambda row: (row["macro_f1"], row["micro_f1"], -row["threshold"]))
    return {"selected_threshold": best["threshold"], "validation_scores": candidates}

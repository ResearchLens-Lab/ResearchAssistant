from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rag.training.datasets import DatasetError, DatasetStore, detect_label_conflicts, validate_dataset
from rag.training.metrics import classification_metrics, evaluate_intent_model, evidence_metrics, exact_entity_metrics, ranking_metrics
from rag.training.models import train_intent_classifier
from rag.training.registry import ModelRegistry, RegistryError, SafeModelHandle
from rag.training.schema import DatasetExample, ExampleStatus, TaskType
from rag.training.splits import freeze_split_manifest, split_by_document


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _approved(example_id: str, group: str, question: str, label: str) -> DatasetExample:
    return DatasetExample(
        example_id=example_id, task_type=TaskType.INTENT, input_text=question,
        expected_label=label, source_group_id=group,
        provenance={"manual_annotation": True}, review_status=ExampleStatus.APPROVED,
        reviewer="reviewer", reviewed_at=NOW, annotator="annotator",
    )


def _intent_corpus():
    topics = ["graph traversal", "sorting algorithms", "database indexing", "machine learning", "network routing", "data compression"]
    rows = []
    for index, topic in enumerate(topics):
        group = f"paper-{index}"
        for suffix, question, label in [
            ("d", f"What is {topic}?", "DEFINITION"),
            ("a", f"Who authored the paper about {topic}?", "AUTHOR_LOOKUP"),
            ("m", f"Which methodology is used for {topic}?", "METHODOLOGY_EXTRACTION"),
        ]:
            rows.append(_approved(f"{group}-{suffix}", group, question, label))
    return rows


def test_schema_label_and_passage_requirements():
    with pytest.raises(ValueError, match="Invalid label"):
        DatasetExample(task_type="intent", input_text="hi", expected_label="MADE_UP")
    with pytest.raises(ValueError, match="candidate_passage"):
        DatasetExample(task_type="passage_relevance", input_text="query", expected_label="3")


def test_pending_approval_correction_history_and_versioned_export(tmp_path):
    store = DatasetStore(tmp_path / "data")
    example = DatasetExample(task_type="intent", input_text="What is a graph?", expected_label="FACT_LOOKUP", annotator="researcher")
    store.add(example)
    approved = store.review(example.example_id, ExampleStatus.APPROVED, "reviewer", expected_label="DEFINITION")
    assert approved.review_status == ExampleStatus.APPROVED
    path = store.export_approved("v1.0.0")
    assert "v1.0.0" in str(path)
    assert (path.parent / "manifest.json").exists()
    assert store.history_path.exists()
    assert '"label_correction": "DEFINITION"' in store.history_path.read_text(encoding="utf-8")
    with pytest.raises(DatasetError, match="already exists"):
        store.export_approved("v1.0.0")


def test_private_example_requires_explicit_permission(tmp_path):
    store = DatasetStore(tmp_path)
    item = DatasetExample(task_type="intent", input_text="question", expected_label="UNKNOWN", private_source=True)
    store.add(item)
    with pytest.raises(ValueError, match="training_permission"):
        store.review(item.example_id, ExampleStatus.APPROVED, "reviewer")
    assert validate_dataset([item], require_reviewed=False)["valid"] is False


def test_duplicate_and_conflicting_annotation_detection():
    a = _approved("a", "p1", "What is a graph?", "DEFINITION")
    b = a.model_copy(update={"example_id": "b", "expected_label": "FACT_LOOKUP"})
    result = validate_dataset([a, a.model_copy(update={"example_id": "c"})])
    assert "duplicate examples detected" in result["errors"]
    assert detect_label_conflicts([a, b])


def test_document_split_has_no_group_leak_and_manifest_freezes(tmp_path):
    rows = _intent_corpus()
    splits = split_by_document(rows)
    group_sets = [{row.source_group_id for row in part} for part in splits.values()]
    assert not (group_sets[0] & group_sets[1] or group_sets[0] & group_sets[2] or group_sets[1] & group_sets[2])
    manifest = freeze_split_manifest(rows, tmp_path / "split.json")
    assert manifest["test_ids"]
    with pytest.raises(ValueError, match="dataset changed"):
        freeze_split_manifest(rows[:-1], tmp_path / "split.json")


def test_intent_training_evaluation_and_baseline_comparison():
    rows = _intent_corpus()
    split = split_by_document(rows)
    model = train_intent_classifier(split["train"])
    result = evaluate_intent_model(model, split["test"])
    assert "accuracy" in result and "macro_f1" in result and "confusion_matrix" in result
    assert "deterministic_baseline" in result
    assert result["accuracy"] >= 0


def test_training_refuses_pending_examples():
    with pytest.raises(ValueError, match="unreviewed"):
        train_intent_classifier([DatasetExample(task_type="intent", input_text="question", expected_label="UNKNOWN")])


def test_metrics_cover_classification_ranking_and_evidence():
    result = classification_metrics(["a", "b"], ["a", "a"])
    assert result["accuracy"] == .5 and "confusion_matrix" in result
    ranked = ranking_metrics({"q": [(.9, 3), (.1, 0)]}, 2)
    assert ranked["recall@2"] == 1 and ranked["mrr"] == 1 and ranked["ndcg@2"] == 1
    evidence = evidence_metrics(["sufficient", "insufficient"], ["sufficient", "sufficient"])
    assert evidence["precision"] == .5 and evidence["false_support_rate"] == 1
    entities = exact_entity_metrics([{"Cormen", "Leiserson"}], [{"Cormen"}])
    assert entities["exact_match_precision"] == 1 and entities["exact_match_recall"] == .5


def test_registry_approval_loading_checksum_rollback_and_fallback(tmp_path):
    rows = _intent_corpus()
    model = train_intent_classifier(rows)
    registry = ModelRegistry(tmp_path / "models")
    first = registry.register(model, name="intent", task="intent", version="1.0", dataset_version="v1", feature_config={"tfidf_max_features": 20000}, metrics={"evaluation_split": "test", "held_out_accuracy": .8})
    fallback = SafeModelHandle(registry, "intent", lambda text: "BASELINE")
    assert fallback.predict("a question") == "BASELINE"
    with pytest.raises(RegistryError, match="did not measurably improve"):
        registry.approve(first["model_id"], metric="held_out_accuracy", baseline_score=.8)
    registry.approve(first["model_id"], metric="held_out_accuracy", baseline_score=.7)
    loaded = registry.load_approved("intent")
    assert loaded.predict(["What is graph traversal?"])[0]

    second = registry.register(model, name="intent", task="intent", version="1.1", dataset_version="v1", feature_config={}, metrics={"evaluation_split": "test", "held_out_accuracy": .9})
    registry.approve(second["model_id"], metric="held_out_accuracy", baseline_score=.8)
    assert registry.rollback("intent") == first["model_id"]
    artifact = tmp_path / "models" / first["artifact_path"]
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(RegistryError, match="checksum"):
        registry.load_approved("intent")


def test_registry_rejects_unapproved_or_incompatible_model(tmp_path):
    registry = ModelRegistry(tmp_path)
    with pytest.raises(RegistryError, match="No approved"):
        registry.load_approved("intent")


def test_registry_rejects_incompatible_library_format(tmp_path):
    model = train_intent_classifier(_intent_corpus())
    registry = ModelRegistry(tmp_path)
    record = registry.register(model, name="intent", task="intent", version="1", dataset_version="v1", feature_config={}, metrics={"evaluation_split": "test", "accuracy": .99})
    registry.approve(record["model_id"], metric="accuracy", baseline_score=.5)
    manifest = registry._read()
    manifest["models"][record["model_id"]]["scikit_learn_version"] = "0.0.1"
    registry._write(manifest)
    with pytest.raises(RegistryError, match="scikit-learn major version"):
        registry.load_approved("intent")


def test_registry_requires_explicit_held_out_test_metrics(tmp_path):
    model = train_intent_classifier(_intent_corpus())
    registry = ModelRegistry(tmp_path)
    record = registry.register(model, name="intent", task="intent", version="1", dataset_version="v1", feature_config={}, metrics={"accuracy": .99})
    with pytest.raises(RegistryError, match="held-out test"):
        registry.approve(record["model_id"], metric="accuracy", baseline_score=.5)


def test_training_runs_without_network_or_pretrained_model_calls(monkeypatch):
    import socket
    import urllib.request
    def forbidden(*args, **kwargs):
        raise AssertionError("training attempted an external request")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    model = train_intent_classifier(_intent_corpus())
    assert model.predict(["What is a graph traversal?"])[0] == "DEFINITION"

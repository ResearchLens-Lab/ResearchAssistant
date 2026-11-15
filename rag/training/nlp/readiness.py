from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rag.training.datasets import DatasetError, DatasetStore, load_dataset, validate_dataset
from rag.training.schema import DatasetExample, ExampleStatus, TaskType
from rag.training.nlp.entities import canonical_entity_type
from rag.training.splits import split_from_manifest


DEFAULT_STORE = Path("rag/training/local_data")


def is_synthetic(example: DatasetExample) -> bool:
    version = example.dataset_version.casefold()
    return (version.startswith(("synthetic", "phase2-smoke", "phase3-smoke"))
            or (example.source_group_id or "").casefold().startswith("synthetic-")
            or bool(example.provenance.get("not_real_document"))
            or example.provenance.get("data_origin") == "synthetic")


def inspect_readiness(store_root: str | Path = DEFAULT_STORE) -> dict[str, Any]:
    root = Path(store_root)
    store = DatasetStore(root)
    queue = store.list_examples()
    snapshots: list[DatasetExample] = []
    versions = root / "versions"
    if versions.exists():
        for path in versions.glob("*/approved.jsonl"):
            try:
                snapshots.extend(load_dataset(path, approved_only=True))
            except DatasetError:
                continue
    # Prefer the current queue version of an example; exported copies are de-duplicated by ID.
    by_id = {item.example_id: item for item in snapshots}
    for item in queue:
        if item.review_status != ExampleStatus.APPROVED or item.example_id not in by_id:
            by_id[item.example_id] = item
    all_examples = list(by_id.values())
    pending = [item for item in all_examples if item.review_status == ExampleStatus.PENDING]
    approved = [item for item in all_examples if item.review_status == ExampleStatus.APPROVED]
    rejected = [item for item in all_examples if item.review_status == ExampleStatus.REJECTED]
    real_approved = [item for item in approved if not is_synthetic(item)]
    per_task: dict[str, dict[str, int]] = {task.value: {} for task in TaskType}
    docs_by_task: dict[str, set[str]] = {}
    for item in real_approved:
        task = item.task_type.value
        labels = per_task.setdefault(task, {})
        labels[item.expected_label] = labels.get(item.expected_label, 0) + 1
        docs_by_task.setdefault(task, set()).add(item.source_group_id or item.paper_id or item.source_document_id or "")
    entity_span_types: Counter[str] = Counter()
    entity_examples = 0
    relation_types: Counter[str] = Counter()
    relationship_pairs = 0
    for item in real_approved:
        if item.task_type == TaskType.ENTITY and item.expected_label == "SEQUENCE":
            spans = (item.expected_output or {}).get("entities", []) if isinstance(item.expected_output, dict) else []
            entity_examples += 1
            entity_span_types.update(_entity_label(str(span.get("label", "UNKNOWN"))) for span in spans)
        if item.task_type == TaskType.RELATIONSHIP:
            relationship_pairs += 1
            relation_types[item.expected_label] += 1
            if isinstance(item.expected_output, dict):
                relation_types.update(set(item.expected_output.get("additional_relationships", [])))

    missing_provenance = []
    private = []
    private_unapproved_permission = []
    for item in all_examples:
        if item.private_source:
            private.append(item.example_id)
            if not item.training_permission:
                private_unapproved_permission.append(item.example_id)
        if item.task_type in {TaskType.ENTITY, TaskType.RELATIONSHIP}:
            if not item.source_document_id or not item.page_number or not item.chunk_id:
                missing_provenance.append(item.example_id)

    split_reports = _inspect_splits(root, all_examples)
    valid_split_versions = {report["dataset_version"] for report in split_reports if report.get("status") == "valid"}
    entity_versions = {item.dataset_version for item in real_approved if item.task_type == TaskType.ENTITY}
    relation_versions = {item.dataset_version for item in real_approved if item.task_type == TaskType.RELATIONSHIP}
    entity_ready = _task_ready(real_approved, TaskType.ENTITY, min_examples=50, min_documents=5,
                               min_labels=1, extra_count=entity_span_types.total(), min_extra=50)
    entity_ready["entity_type_counts"] = dict(entity_span_types)
    if len(entity_span_types) < 2 or any(count < 5 for count in entity_span_types.values()):
        entity_ready["reasons"].append("needs at least two entity types with five or more reviewed spans each")
        entity_ready["ready"] = False
    relationship_ready = _task_ready(real_approved, TaskType.RELATIONSHIP, min_examples=50, min_documents=5,
                                     min_labels=2, extra_count=relationship_pairs, min_extra=50)
    relationship_ready["requires_no_relation"] = relation_types.get("NO_RELATION", 0) > 0
    relation_limited = [label for label, count in relation_types.items() if count < 5]
    relationship_ready["underrepresented_relationship_types"] = relation_limited
    relationship_ready["ready"] = relationship_ready["ready"] and relationship_ready["requires_no_relation"]
    if not relationship_ready["requires_no_relation"]:
        relationship_ready["reasons"].append("needs explicitly reviewed NO_RELATION pairs")
    if relation_limited:
        relationship_ready["reasons"].append("each observed relationship label needs at least five reviewed pairs")
        relationship_ready["ready"] = False
    entity_ready["frozen_split_valid"] = bool(entity_versions) and entity_versions.issubset(valid_split_versions)
    if not entity_ready["frozen_split_valid"]:
        entity_ready["reasons"].append("needs a valid frozen document-level split manifest")
        entity_ready["ready"] = False
    relationship_ready["frozen_split_valid"] = bool(relation_versions) and relation_versions.issubset(valid_split_versions)
    if not relationship_ready["frozen_split_valid"]:
        relationship_ready["reasons"].append("needs a valid frozen document-level split manifest")
        relationship_ready["ready"] = False
    synthetic_fixture_path = Path(__file__).parents[1] / "fixtures" / "phase2_smoke.jsonl"
    fixture_ids: set[str] = set()
    fixture_count = 0
    if synthetic_fixture_path.is_file():
        try:
            fixture_rows = load_dataset(synthetic_fixture_path, approved_only=False)
            fixture_ids = {item.example_id for item in fixture_rows}
            fixture_count = len(fixture_rows)
        except DatasetError:
            fixture_count = -1
    synthetic_ids = {item.example_id for item in all_examples if is_synthetic(item)}
    return {
        "store_path": str(root.resolve()),
        "store_exists": root.exists(),
        "annotations": {"pending": len(pending), "approved": len(approved), "rejected": len(rejected)},
        "approved_real_examples_by_task_and_label": per_task,
        "distinct_source_documents_by_task": {task: len(docs) - (1 if "" in docs else 0) for task, docs in docs_by_task.items()},
        "entity_spans": {"annotated_examples": entity_examples, "span_count": entity_span_types.total(), "counts_by_type": dict(entity_span_types)},
        "relationship_pairs": {"annotated_pairs": relationship_pairs, "counts_by_type": dict(relation_types), "has_no_relation_examples": relation_types.get("NO_RELATION", 0) > 0},
        "synthetic_examples_excluded": len(synthetic_ids | fixture_ids),
        "separate_repository_synthetic_fixture": {"path": str(synthetic_fixture_path.resolve()), "example_count": fixture_count,
                                                   "included_in_local_training_store": False, "excluded_from_training": True},
        "private_examples": len(private), "private_examples_missing_training_permission": len(private_unapproved_permission),
        "examples_missing_required_provenance": missing_provenance,
        "frozen_split_checks": split_reports,
        "task_readiness": {"entity": entity_ready, "relationship": relationship_ready},
        "training_allowed": {"entity": entity_ready["ready"], "relationship": relationship_ready["ready"]},
        "excluded_synthetic_fixture": "rag/training/fixtures/phase2_smoke.jsonl",
    }


def validate_training_readiness(examples: list[DatasetExample], task: TaskType,
                                split_manifest: dict) -> dict[str, Any]:
    """Strict per-version gate used by the trainer before any estimator is fitted."""
    selected = [item for item in examples if item.task_type == task]
    real = [item for item in selected if not is_synthetic(item)]
    quality = validate_dataset(examples, require_reviewed=True)
    reasons = list(quality["errors"])
    if len(real) < 50:
        reasons.append(f"requires 50 approved real examples for {task.value}; found {len(real)}")
    documents = {item.source_group_id or item.paper_id or item.source_document_id for item in real}
    if len(documents) < 5 or "" in documents:
        reasons.append("requires five identifiable independent real source documents")
    if len(real) != len(selected):
        reasons.append("synthetic examples are excluded from real-data training")
    if any(item.private_source and not item.training_permission for item in selected):
        reasons.append("private examples without explicit training permission are present")
    split_from_manifest(examples, split_manifest)
    groups = [set(split_manifest.get(f"{part}_groups", [])) for part in ("train", "validation", "test")]
    if any(not group for group in groups) or groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
        reasons.append("frozen train/validation/test document partitions are empty or overlapping")
    task_counts: Counter[str] = Counter()
    for item in real:
        if task == TaskType.RELATIONSHIP and isinstance(item.expected_output, dict):
            task_counts[item.expected_label] += 1
            task_counts.update(set(item.expected_output.get("additional_relationships", [])))
        else:
            task_counts[item.expected_label] += 1
    if task == TaskType.ENTITY:
        entity_types: Counter[str] = Counter()
        for item in real:
            spans = (item.expected_output or {}).get("entities", []) if isinstance(item.expected_output, dict) else []
            entity_types.update(_entity_label(str(span.get("label", "UNKNOWN"))))
        if entity_types.total() < 50:
            reasons.append(f"requires at least 50 reviewed entity spans; found {entity_types.total()}")
        if len(entity_types) < 2 or any(count < 5 for count in entity_types.values()):
            reasons.append("requires two entity types with at least five reviewed spans each")
        task_counts = entity_types
    else:
        if "NO_RELATION" not in task_counts or not (set(task_counts) - {"NO_RELATION"}):
            reasons.append("requires reviewed NO_RELATION and positive relationship examples")
        if any(count < 5 for count in task_counts.values()):
            reasons.append("requires at least five examples for every observed relationship type")
    report = {"task": task.value, "approved_real_examples": len(real), "independent_documents": len(documents) - (1 if "" in documents else 0),
              "label_counts": dict(task_counts), "frozen_split_valid": not any("frozen" in reason for reason in reasons),
              "ready": not reasons, "reasons": reasons}
    if reasons:
        raise ValueError(f"{task.value} training readiness blocked: {json.dumps(report, ensure_ascii=False)}")
    return report


def _entity_label(label: str) -> str:
    try:
        return canonical_entity_type(label)
    except ValueError:
        return label.upper()


def _task_ready(examples: list[DatasetExample], task: TaskType, min_examples: int,
                min_documents: int, min_labels: int, extra_count: int, min_extra: int) -> dict[str, Any]:
    selected = [item for item in examples if item.task_type == task]
    documents = {item.source_group_id or item.paper_id or item.source_document_id for item in selected}
    labels = Counter(item.expected_label for item in selected)
    reasons = []
    if len(selected) < min_examples:
        reasons.append(f"needs at least {min_examples} reviewed real examples; found {len(selected)}")
    if len(documents) < min_documents or "" in documents:
        reasons.append(f"needs at least {min_documents} identifiable source papers/documents; found {len(documents) - (1 if '' in documents else 0)}")
    if len(labels) < min_labels:
        reasons.append(f"needs at least {min_labels} labels; found {len(labels)}")
    if extra_count < min_extra:
        reasons.append(f"needs at least {min_extra} task annotations; found {extra_count}")
    return {"approved_real_examples": len(selected), "distinct_documents": len(documents) - (1 if "" in documents else 0),
            "label_counts": dict(labels), "ready": not reasons, "reasons": reasons}


def _inspect_splits(root: Path, items: list[DatasetExample]) -> list[dict[str, Any]]:
    reports = []
    approved_real = [item for item in items if item.review_status == ExampleStatus.APPROVED and not is_synthetic(item)]
    if not approved_real:
        return [{"status": "not_available", "reason": "No approved real-document examples; synthetic fixture excluded."}]
    versions = {item.dataset_version for item in approved_real}
    for version in sorted(versions):
        dataset = [item for item in approved_real if item.dataset_version == version]
        candidates = [root / "versions" / version / "split_manifest.json",
                      root / "versions" / version / "splits.json", root / "splits" / f"{version}.json"]
        manifest_path = next((path for path in candidates if path.is_file()), None)
        if manifest_path is None:
            reports.append({"dataset_version": version, "status": "missing", "document_count": len({i.source_group_id or i.paper_id or i.source_document_id for i in dataset})})
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            split_from_manifest(dataset, manifest)
            reports.append({"dataset_version": version, "status": "valid", "manifest": str(manifest_path), "document_count": len({i.source_group_id or i.paper_id or i.source_document_id for i in dataset})})
        except Exception as exc:
            reports.append({"dataset_version": version, "status": "invalid", "manifest": str(manifest_path), "error": str(exc)})
    return reports

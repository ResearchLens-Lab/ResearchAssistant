from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from rag.training.schema import DatasetExample, ExampleStatus, TaskType


class DatasetError(ValueError):
    pass


def _jsonl_read(path: Path) -> list[DatasetExample]:
    if not path.exists():
        return []
    items: list[DatasetExample] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            items.append(DatasetExample.model_validate_json(line))
        except ValidationError as exc:
            raise DatasetError(f"{path}:{line_number}: {exc}") from exc
    return items


def _jsonl_write(path: Path, items: Iterable[DatasetExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(item.model_dump_json() + "\n" for item in items)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(path)


def example_fingerprint(item: DatasetExample) -> str:
    identity = ""
    if item.task_type == TaskType.RELATIONSHIP and isinstance(item.expected_output, dict):
        subject, object_ = item.expected_output.get("subject", {}), item.expected_output.get("object", {})
        identity = json.dumps({"subject": [subject.get("start"), subject.get("end"), subject.get("label")],
                               "object": [object_.get("start"), object_.get("end"), object_.get("label")]}, sort_keys=True)
    raw = "\0".join((item.task_type.value, item.input_text.strip().casefold(), (item.candidate_passage or "").strip().casefold(), identity))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DatasetStore:
    """Review queue and immutable approved JSONL snapshots stored outside user indexes."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.queue_path = self.root / "annotations.jsonl"
        self.history_path = self.root / "correction_history.jsonl"
        self.versions_path = self.root / "versions"

    def list_examples(self, status: ExampleStatus | None = None) -> list[DatasetExample]:
        items = _jsonl_read(self.queue_path)
        return [item for item in items if status is None or item.review_status == status]

    def add(self, example: DatasetExample) -> DatasetExample:
        items = self.list_examples()
        if any(item.example_id == example.example_id for item in items):
            raise DatasetError(f"Duplicate example_id: {example.example_id}")
        if any(example_fingerprint(item) == example_fingerprint(example) for item in items):
            raise DatasetError("Duplicate task/input/passage example")
        _jsonl_write(self.queue_path, [*items, example])
        return example

    def review(self, example_id: str, status: ExampleStatus, reviewer: str,
               expected_label: str | None = None, expected_output: object = None) -> DatasetExample:
        if status == ExampleStatus.PENDING:
            raise DatasetError("Review action must approve or reject an example")
        items = self.list_examples()
        found = next((i for i, item in enumerate(items) if item.example_id == example_id), None)
        if found is None:
            raise DatasetError(f"Unknown example_id: {example_id}")
        old = items[found]
        history = {
            "example_id": old.example_id,
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": reviewer,
            "previous": old.model_dump(mode="json"),
            "action": status.value,
            "label_correction": expected_label,
            "output_correction": expected_output,
        }
        history_path = self.history_path
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(history, ensure_ascii=False) + "\n")
        changes: dict[str, object] = {
            "review_status": status,
            "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc),
        }
        if expected_label is not None:
            changes["expected_label"] = expected_label
        if expected_output is not None:
            changes["expected_output"] = expected_output
        updated = old.model_copy(update=changes)
        # Re-parse to ensure corrections remain task-label compatible.
        updated = DatasetExample.model_validate(updated.model_dump())
        items[found] = updated
        _jsonl_write(self.queue_path, items)
        return updated

    def export_approved(self, version: str) -> Path:
        if not version or "/" in version or "\\" in version or version in {".", ".."}:
            raise DatasetError("Invalid dataset version")
        approved = self.list_examples(ExampleStatus.APPROVED)
        if not approved:
            raise DatasetError("No approved examples to export")
        seen: set[str] = set()
        for item in approved:
            if item.private_source and not item.training_permission:
                raise DatasetError(f"Private example {item.example_id} lacks training permission")
            key = example_fingerprint(item)
            if key in seen:
                raise DatasetError(f"Duplicate approved example: {item.example_id}")
            seen.add(key)
        output = [item.model_copy(update={"dataset_version": version}) for item in approved]
        version_dir = self.versions_path / version
        destination = version_dir / "approved.jsonl"
        if version_dir.exists():
            raise DatasetError(f"Dataset version already exists: {version}")
        _jsonl_write(destination, output)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        manifest = {
            "dataset_version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "example_count": len(output),
            "approved_only": True,
            "sha256": digest,
        }
        destination.with_name("manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return destination


def load_dataset(path: str | Path, approved_only: bool = True) -> list[DatasetExample]:
    items = _jsonl_read(Path(path))
    if approved_only:
        items = [item for item in items if item.review_status == ExampleStatus.APPROVED]
    return items


def validate_dataset(items: list[DatasetExample], *, require_reviewed: bool = True) -> dict[str, object]:
    errors: list[str] = []
    duplicates: list[str] = []
    fingerprints: set[str] = set()
    ids: set[str] = set()
    labels: dict[str, int] = {}
    provenance_missing: list[str] = []
    for item in items:
        if item.example_id in ids:
            duplicates.append(item.example_id)
        ids.add(item.example_id)
        fingerprint = example_fingerprint(item)
        if fingerprint in fingerprints:
            duplicates.append(item.example_id)
        fingerprints.add(fingerprint)
        if require_reviewed and item.review_status != ExampleStatus.APPROVED:
            errors.append(f"{item.example_id}: not approved")
        if item.private_source and not item.training_permission:
            errors.append(f"{item.example_id}: private source lacks explicit training permission")
        if item.task_type in {TaskType.PASSAGE_RELEVANCE, TaskType.EVIDENCE_SUFFICIENCY, TaskType.CLAIM, TaskType.ENTITY, TaskType.RELATIONSHIP}:
            if not item.source_document_id or not item.page_number or not item.chunk_id:
                provenance_missing.append(item.example_id)
        elif not item.provenance and not item.source_document_id:
            provenance_missing.append(item.example_id)
        observed_labels = [item.expected_label]
        if item.task_type == TaskType.RELATIONSHIP and isinstance(item.expected_output, dict):
            observed_labels.extend(item.expected_output.get("additional_relationships", []))
        for label in set(observed_labels):
            labels[label] = labels.get(label, 0) + 1
    if duplicates:
        errors.append("duplicate examples detected")
    conflicts = detect_label_conflicts(items)
    if conflicts:
        errors.append("contradictory annotations require reviewer resolution")
    if provenance_missing:
        errors.append("missing source provenance detected")
    counts = sorted(labels.values())
    imbalance = (max(counts) / min(counts)) if counts and min(counts) else None
    return {
        "valid": not errors,
        "errors": errors,
        "duplicate_example_ids": duplicates,
        "label_conflicts": conflicts,
        "missing_provenance_ids": provenance_missing,
        "label_counts": labels,
        "class_imbalance_ratio": imbalance,
        "class_imbalance_warning": bool(imbalance and imbalance > 5),
        "example_count": len(items),
    }


def detect_label_conflicts(items: list[DatasetExample]) -> list[dict[str, str]]:
    grouped: dict[str, list[DatasetExample]] = {}
    for item in items:
        grouped.setdefault(example_fingerprint(item), []).append(item)
    conflicts = []
    for group in grouped.values():
        observed: set[str] = set()
        expected_labels: set[str] = set()
        for example in group:
            observed.add(example.expected_label)
            expected_labels.add(example.expected_label)
            if example.task_type == TaskType.RELATIONSHIP and isinstance(example.expected_output, dict):
                observed.update(example.expected_output.get("additional_relationships", []))
        is_relationship = group[0].task_type == TaskType.RELATIONSHIP
        contradictory = (("NO_RELATION" in observed and bool(observed - {"NO_RELATION"}))
                         if is_relationship else len(expected_labels) > 1)
        if contradictory:
            conflicts.append({"input": group[0].input_text, "labels": ",".join(sorted(observed))})
    return conflicts

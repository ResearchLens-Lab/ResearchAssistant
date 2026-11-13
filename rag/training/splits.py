from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from rag.training.schema import DatasetExample


def split_by_document(items: list[DatasetExample], seed: int = 17,
                      train_ratio: float = .70, validation_ratio: float = .15,
                      test_ratio: float = .15) -> dict[str, list[DatasetExample]]:
    if abs(train_ratio + validation_ratio + test_ratio - 1.0) > 1e-8:
        raise ValueError("split ratios must sum to 1")
    groups: dict[str, list[DatasetExample]] = defaultdict(list)
    for item in items:
        key = item.source_group_id or item.paper_id or item.source_document_id
        if not key:
            raise ValueError(f"{item.example_id}: source_group_id or source document is required for leakage-safe splitting")
        groups[key].append(item)
    if len(groups) < 3:
        raise ValueError("at least three independent source documents/groups are required for train/validation/test")
    keys = sorted(groups, key=lambda k: hashlib.sha256(f"{seed}:{k}".encode()).hexdigest())
    n = len(keys)
    n_test = max(1, round(n * test_ratio))
    n_val = max(1, round(n * validation_ratio))
    if n_test + n_val >= n:
        n_test, n_val = 1, 1
    test_keys = set(keys[:n_test])
    val_keys = set(keys[n_test:n_test+n_val])
    train_keys = set(keys[n_test+n_val:])
    return {
        "train": [item for key in keys if key in train_keys for item in groups[key]],
        "validation": [item for key in keys if key in val_keys for item in groups[key]],
        "test": [item for key in keys if key in test_keys for item in groups[key]],
    }


def freeze_split_manifest(items: list[DatasetExample], path: str | Path, seed: int = 17) -> dict:
    """Persist group assignments once; later runs reject silent dataset drift."""
    destination = Path(path)
    canonical = "\n".join(sorted(item.model_dump_json() for item in items))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    if destination.exists():
        current = json.loads(destination.read_text(encoding="utf-8"))
        if current.get("dataset_sha256") != digest:
            raise ValueError("dataset changed after split freeze; use a new dataset version and manifest")
        expected = split_by_document(items, seed=int(current.get("seed", seed)))
        for name in ("train", "validation", "test"):
            if set(current.get(f"{name}_ids", [])) != {item.example_id for item in expected[name]}:
                raise ValueError("frozen document split assignment was edited; create a new dataset version")
        return current
    split = split_by_document(items, seed=seed)
    group = lambda rows: sorted({item.source_group_id or item.paper_id or item.source_document_id for item in rows})
    manifest = {
        "seed": seed, "dataset_sha256": digest,
        "train_ids": [item.example_id for item in split["train"]],
        "validation_ids": [item.example_id for item in split["validation"]],
        "test_ids": [item.example_id for item in split["test"]],
        "train_groups": group(split["train"]),
        "validation_groups": group(split["validation"]),
        "test_groups": group(split["test"]),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def split_from_manifest(items: list[DatasetExample], manifest: dict) -> dict[str, list[DatasetExample]]:
    """Apply frozen IDs and reject leakage, missing rows, or changed labels/content."""
    canonical = "\n".join(sorted(item.model_dump_json() for item in items))
    if hashlib.sha256(canonical.encode()).hexdigest() != manifest.get("dataset_sha256"):
        raise ValueError("dataset content differs from frozen split; create a new version")
    by_id = {item.example_id: item for item in items}
    result = {
        name: [by_id[example_id] for example_id in manifest[f"{name}_ids"] if example_id in by_id]
        for name in ("train", "validation", "test")
    }
    assigned = [item.example_id for part in result.values() for item in part]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(by_id):
        raise ValueError("frozen split has duplicate or missing example IDs")
    expected = split_by_document(items, seed=int(manifest.get("seed", 17)))
    if any(set(manifest.get(f"{name}_ids", [])) != {item.example_id for item in expected[name]}
           for name in ("train", "validation", "test")):
        raise ValueError("frozen split assignment is not the deterministic document-level split")
    groups = [{item.source_group_id or item.paper_id or item.source_document_id for item in part} for part in result.values()]
    if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
        raise ValueError("frozen split leaks a document group across partitions")
    return result

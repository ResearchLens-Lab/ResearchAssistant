from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
import sklearn


class RegistryError(ValueError):
    pass


class ModelRegistry:
    """Local registry. Loads only approved, checksum-matching artifacts under its root."""

    FORMAT_VERSION = 1

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.artifacts = self.root / "artifacts"
        self.manifest_path = self.root / "registry.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self._write({"format_version": self.FORMAT_VERSION, "models": {}, "active": {}, "history": {}})

    def _read(self) -> dict:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(f"Registry manifest cannot be read: {exc}") from exc
        if data.get("format_version") != self.FORMAT_VERSION:
            raise RegistryError("Incompatible model registry format")
        return data

    def _write(self, data: dict) -> None:
        temp = self.manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.manifest_path)

    def register(self, model, *, name: str, task: str, version: str,
                 dataset_version: str, feature_config: dict, metrics: dict,
                 dataset_content_hash: str | None = None,
                 split_manifest_reference: str | None = None,
                 split_manifest_content_hash: str | None = None,
                 label_configuration: dict | None = None,
                 baseline_metrics: dict | None = None,
                 approval_status: str = "candidate") -> dict:
        if approval_status != "candidate":
            raise RegistryError("Models must be registered as candidate and explicitly approved later")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
            raise RegistryError("Invalid model version")
        model_id = f"{task}-{version}-{uuid4().hex[:8]}"
        artifact = self.artifacts / f"{model_id}.joblib"
        joblib.dump(model, artifact, compress=3)
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        record = {
            "model_id": model_id, "model_name": name, "task": task, "version": version,
            "training_dataset_version": dataset_version, "feature_configuration": feature_config,
            "training_dataset_content_hash": dataset_content_hash,
            "frozen_split_manifest_reference": split_manifest_reference,
            "frozen_split_manifest_content_hash": split_manifest_content_hash,
            "label_configuration": label_configuration or {},
            "baseline_metrics": baseline_metrics or {},
            "training_date": datetime.now(timezone.utc).isoformat(), "evaluation_metrics": metrics,
            "artifact_path": str(artifact.relative_to(self.root)), "sha256": checksum,
            "approval_status": "candidate", "format_version": self.FORMAT_VERSION,
            "scikit_learn_version": sklearn.__version__,
            "software_versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
        }
        data = self._read(); data["models"][model_id] = record; self._write(data)
        return record

    def approve(self, model_id: str, *, metric: str, baseline_score: float) -> dict:
        data = self._read(); record = data["models"].get(model_id)
        if not record:
            raise RegistryError("Unknown model")
        metrics = record["evaluation_metrics"]
        test_record = metrics.get("test") if isinstance(metrics.get("test"), dict) else metrics
        if not (metrics.get("evaluation_split") == "test" or isinstance(metrics.get("test"), dict)):
            raise RegistryError("Approval requires metrics explicitly evaluated on the held-out test split")
        score = _find_metric(test_record, metric)
        if score is None or score <= baseline_score:
            raise RegistryError(f"Model did not measurably improve held-out {metric} over baseline")
        old = data["active"].get(record["task"])
        if old:
            data["history"].setdefault(record["task"], []).append(old)
        record["approval_status"] = "approved"
        record["approved_at"] = datetime.now(timezone.utc).isoformat()
        record["approval_metric"] = metric
        record["held_out_score"] = score
        record["baseline_score"] = baseline_score
        data["active"][record["task"]] = model_id
        self._write(data)
        return record

    def load_approved(self, task: str, model_id: str | None = None):
        data = self._read()
        selected = model_id or data["active"].get(task)
        if not selected or selected not in data["models"]:
            raise RegistryError(f"No approved model registered for task {task}")
        record = data["models"][selected]
        if record["task"] != task or record["approval_status"] != "approved":
            raise RegistryError("Model is unapproved or task-incompatible")
        if record.get("format_version") != self.FORMAT_VERSION:
            raise RegistryError("Incompatible model artifact format")
        if record.get("scikit_learn_version", "").split(".", 1)[0] != sklearn.__version__.split(".", 1)[0]:
            raise RegistryError("Incompatible scikit-learn major version")
        return self._load_record(record)

    def load_candidate(self, model_id: str, task: str):
        data = self._read()
        record = data["models"].get(model_id)
        if not record or record["task"] != task or record["approval_status"] != "candidate":
            raise RegistryError("Unknown, incompatible, or non-candidate model")
        if record.get("format_version") != self.FORMAT_VERSION:
            raise RegistryError("Incompatible model artifact format")
        if record.get("scikit_learn_version", "").split(".", 1)[0] != sklearn.__version__.split(".", 1)[0]:
            raise RegistryError("Incompatible scikit-learn major version")
        return self._load_record(record)

    def _load_record(self, record: dict):
        artifact = (self.root / record["artifact_path"]).resolve()
        if self.artifacts.resolve() not in artifact.parents:
            raise RegistryError("Artifact path escapes registry root")
        if not artifact.is_file():
            raise RegistryError("Model artifact is missing")
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if checksum != record["sha256"]:
            raise RegistryError("Model checksum verification failed")
        try:
            return joblib.load(artifact)
        except Exception as exc:
            raise RegistryError(f"Model artifact could not be loaded: {exc}") from exc

    def record_evaluation(self, model_id: str, *, evaluation_split: str, metrics: dict) -> dict:
        if evaluation_split not in {"validation", "test"}:
            raise RegistryError("evaluation split must be validation or test")
        data = self._read(); record = data["models"].get(model_id)
        if not record or record["approval_status"] != "candidate":
            raise RegistryError("Only registered candidate models can receive evaluations")
        record["evaluation_metrics"][evaluation_split] = metrics
        if evaluation_split == "test":
            record["evaluation_split"] = "test"
        self._write(data)
        return record

    def rollback(self, task: str) -> str:
        data = self._read()
        history = data["history"].get(task, [])
        if not history:
            raise RegistryError(f"No previous approved model for task {task}")
        current = data["active"].get(task)
        previous = history.pop()
        data["active"][task] = previous
        if current:
            data["history"].setdefault(task, []).append(current)
        self._write(data)
        return previous

    def records(self) -> list[dict]:
        return list(self._read()["models"].values())


def _find_metric(metrics: dict, name: str) -> float | None:
    value = metrics.get(name)
    if isinstance(value, (int, float)):
        return float(value)
    for key in ("candidate", "test", "model", "trained_model"):
        nested = metrics.get(key)
        if isinstance(nested, dict) and isinstance(nested.get(name), (int, float)):
            return float(nested[name])
    return None


class SafeModelHandle:
    """Controlled opt-in adapter: baseline remains fallback until an approved model exists."""

    def __init__(self, registry: ModelRegistry, task: str, baseline):
        self.registry, self.task, self.baseline = registry, task, baseline

    def predict(self, *args, **kwargs):
        try:
            model = self.registry.load_approved(self.task)
        except RegistryError:
            return self.baseline(*args, **kwargs)
        return model.predict(*args, **kwargs)

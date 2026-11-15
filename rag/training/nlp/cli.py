from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rag.training.datasets import DatasetError, DatasetStore, load_dataset, validate_dataset
from rag.training.nlp.entities import InsufficientTrainingData, train_entity_recognizer
from rag.training.nlp.evaluation import evaluate_entity_model, evaluate_relationship_model, select_relationship_threshold
from rag.training.nlp.readiness import DEFAULT_STORE, inspect_readiness, is_synthetic, validate_training_readiness
from rag.training.nlp.relations import train_relationship_extractor
from rag.training.registry import ModelRegistry, RegistryError
from rag.training.schema import DatasetExample, ExampleStatus, TaskType
from rag.training.splits import freeze_split_manifest, split_from_manifest


def _read_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_version(store: Path, version: str) -> tuple[list[DatasetExample], Path, dict]:
    directory = store / "versions" / version
    data_path, manifest_path = directory / "approved.jsonl", directory / "manifest.json"
    if not data_path.is_file() or not manifest_path.is_file():
        raise DatasetError(f"approved dataset version {version!r} is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("approved_only") or hashlib.sha256(data_path.read_bytes()).hexdigest() != manifest.get("sha256"):
        raise DatasetError("approved dataset manifest/checksum validation failed")
    rows = load_dataset(data_path, approved_only=True)
    quality = validate_dataset(rows, require_reviewed=True)
    if not quality["valid"]:
        raise DatasetError(f"dataset quality validation failed: {quality['errors']}")
    if any(is_synthetic(row) for row in rows):
        raise DatasetError("synthetic datasets are excluded from real-document model training")
    return rows, data_path, manifest


def _flatten_entity(report: dict) -> dict[str, float]:
    return {f"exact_match_{key}": value for key, value in report["exact_span"].items()}


def _flatten_relation(report: dict) -> dict[str, float]:
    return {f"micro_{key}": value for key, value in report["micro"].items()}


def _readiness(store: Path) -> dict:
    report = inspect_readiness(store)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Review-gated entity and relationship NLP workflow")
    parser.add_argument("--store", default=str(DEFAULT_STORE), help="Phase 2 JSONL annotation store")
    parser.add_argument("--registry", default="rag/training/model_registry", help="Local model registry directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("readiness")
    validate = commands.add_parser("validate"); validate.add_argument("--version", required=True)
    freeze = commands.add_parser("freeze-split"); freeze.add_argument("--version", required=True)
    pending = commands.add_parser("list-pending")
    commands.add_parser("list-approved")
    commands.add_parser("list-rejected")
    history = commands.add_parser("history"); history.add_argument("--example-id")
    entity = commands.add_parser("annotate-entity")
    entity.add_argument("--text", required=True); entity.add_argument("--spans-json", required=True, help="Path to JSON array of {start,end,label,text} spans")
    relation = commands.add_parser("annotate-relationship")
    relation.add_argument("--text", required=True); relation.add_argument("--subject-json", required=True); relation.add_argument("--object-json", required=True)
    relation.add_argument("--label", required=True, help="Relationship type, including NO_RELATION")
    relation.add_argument("--additional-label", action="append", default=[], help="Additional supported relationship for this entity pair (repeatable)")
    for command in (entity, relation):
        command.add_argument("--document-id", required=True); command.add_argument("--paper-id", required=True)
        command.add_argument("--page", required=True, type=int); command.add_argument("--chunk-id", required=True)
        command.add_argument("--source-group-id", required=True); command.add_argument("--annotator", required=True)
        command.add_argument("--private", action="store_true"); command.add_argument("--training-permission", action="store_true")
        command.add_argument("--filename"); command.add_argument("--source-id")
    review = commands.add_parser("review"); review.add_argument("example_id"); review.add_argument("--status", choices=["approved", "rejected"], required=True); review.add_argument("--reviewer", required=True); review.add_argument("--correct-label"); review.add_argument("--correct-output-json")
    for name in ("train-entity", "train-relationship", "evaluate-candidate"):
        cmd = commands.add_parser(name); cmd.add_argument("--version", required=True)
    for name in ("train-entity", "train-relationship"):
        commands.choices[name].add_argument("--model-version", default="1.0.0")
    commands.choices["train-entity"].add_argument("--ontology-json", help="Optional JSON alias-to-canonical entity type map")
    evaluate = commands.choices["evaluate-candidate"]; evaluate.add_argument("--model-id", required=True)
    evaluate.add_argument("--task", choices=["entity_ner", "relationship_extraction"], required=True)
    approve = commands.add_parser("approve-candidate"); approve.add_argument("--model-id", required=True); approve.add_argument("--metric", required=True)
    commands.add_parser("inspect-registry")

    args = parser.parse_args(); store_path = Path(args.store); store = DatasetStore(store_path)
    if args.command == "readiness":
        _readiness(store_path)
    elif args.command == "list-pending":
        print(json.dumps([item.model_dump(mode="json") for item in store.list_examples(ExampleStatus.PENDING)], indent=2, ensure_ascii=False))
    elif args.command == "list-approved":
        print(json.dumps([item.model_dump(mode="json") for item in store.list_examples(ExampleStatus.APPROVED)], indent=2, ensure_ascii=False))
    elif args.command == "list-rejected":
        print(json.dumps([item.model_dump(mode="json") for item in store.list_examples(ExampleStatus.REJECTED)], indent=2, ensure_ascii=False))
    elif args.command == "history":
        events = []
        if store.history_path.is_file():
            events = [json.loads(line) for line in store.history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.example_id:
            events = [event for event in events if event.get("example_id") == args.example_id]
        print(json.dumps(events, indent=2, ensure_ascii=False))
    elif args.command in {"annotate-entity", "annotate-relationship"}:
        if args.command == "annotate-entity":
            task, label = TaskType.ENTITY, "SEQUENCE"
            output = {"entities": _read_json(args.spans_json)}
        else:
            task, label = TaskType.RELATIONSHIP, args.label.upper()
            output = {"subject": _read_json(args.subject_json), "object": _read_json(args.object_json)}
            if args.additional_label:
                output["additional_relationships"] = [label.upper() for label in args.additional_label]
        example = DatasetExample(
            task_type=task, input_text=args.text, candidate_passage=args.text, expected_label=label,
            expected_output=output, source_document_id=args.document_id, paper_id=args.paper_id,
            page_number=args.page, chunk_id=args.chunk_id, source_group_id=args.source_group_id,
            provenance={"annotation_method": "manual", "source_id": args.source_id, "filename": args.filename},
            annotator=args.annotator, private_source=args.private, training_permission=args.training_permission,
        )
        print(store.add(example).example_id)
    elif args.command == "review":
        item = store.review(args.example_id, ExampleStatus(args.status), args.reviewer,
                            args.correct_label, _read_json(args.correct_output_json))
        print(item.model_dump_json(indent=2))
    elif args.command == "validate":
        rows, _, _ = _load_version(store_path, args.version)
        print(json.dumps(validate_dataset(rows, require_reviewed=True), indent=2))
    elif args.command == "freeze-split":
        rows, _, _ = _load_version(store_path, args.version)
        target = store_path / "versions" / args.version / "split_manifest.json"
        manifest = freeze_split_manifest(rows, target)
        split_from_manifest(rows, manifest)
        print(json.dumps({"path": str(target), "train": len(manifest["train_ids"]),
                          "validation": len(manifest["validation_ids"]), "test": len(manifest["test_ids"])}, indent=2))
    elif args.command in {"train-entity", "train-relationship"}:
        rows, data_path, data_manifest = _load_version(store_path, args.version)
        split_path = store_path / "versions" / args.version / "split_manifest.json"
        if not split_path.is_file():
            raise DatasetError("freeze the document-level split first; training never creates or changes test assignment")
        split_manifest = json.loads(split_path.read_text(encoding="utf-8"))
        partitions = split_from_manifest(rows, split_manifest)
        target_task = TaskType.ENTITY if args.command == "train-entity" else TaskType.RELATIONSHIP
        readiness = validate_training_readiness(rows, target_task, split_manifest)
        if args.command == "train-entity":
            ontology = _read_json(args.ontology_json) or {}
            task, model = "entity_ner", train_entity_recognizer(partitions["train"], split_manifest,
                                                                  ontology=ontology, min_spans=30,
                                                                  min_documents=3, min_per_type=3)
            validation = evaluate_entity_model(model, partitions["validation"], split_manifest, "validation")
            model.model_version = args.model_version
            metrics = {"exact_match_f1": validation["exact_span"]["exact_match_f1"]}
            baseline = {"exact_match_f1": validation["deterministic_baseline"]["exact_span"]["exact_match_f1"]}
            labels = {"entity_types": list(model.label_config), "aliases": ontology, "representation": "BIO"}
            features = {"type": "hashed sparse token features", "hash_bins": 32768, "ngram_context": "sentence +/-3 tokens"}
        else:
            task, model = "relationship_extraction", train_relationship_extractor(partitions["train"], split_manifest,
                                                                                      min_pairs=30, min_documents=3, min_per_label=3)
            threshold = select_relationship_threshold(model, partitions["validation"], split_manifest)
            model.confidence_threshold = threshold["selected_threshold"]
            validation = evaluate_relationship_model(model, partitions["validation"], split_manifest, "validation", model.confidence_threshold)
            model.model_version = args.model_version
            metrics = {f"micro_{key}": value for key, value in validation["micro"].items()}
            baseline = {"micro_f1": validation["deterministic_baseline"]["micro_f1"]}
            labels = {"relationship_types": list(model.label_config)}
            features = {"type": "hashed sparse entity-pair/context features", "hash_bins": 32768, "same_sentence": True,
                        "confidence_threshold_selected_on": "validation", "confidence_threshold": model.confidence_threshold,
                        "threshold_validation_scores": threshold["validation_scores"]}
        registry = ModelRegistry(args.registry)
        record = registry.register(model, name=task, task=task, version=args.model_version,
                                   dataset_version=args.version, dataset_content_hash=data_manifest["sha256"],
                                   split_manifest_reference=str(split_path.resolve()),
                                   split_manifest_content_hash=hashlib.sha256(split_path.read_bytes()).hexdigest(),
                                   feature_config=features,
                                   label_configuration=labels, metrics={"validation": metrics}, baseline_metrics={"validation": baseline})
        print(json.dumps({"registered": "candidate", "model_id": record["model_id"], "readiness": readiness, "validation": validation,
                          "activated": False}, indent=2, ensure_ascii=False))
    elif args.command == "evaluate-candidate":
        rows, _, dataset_manifest = _load_version(store_path, args.version)
        split_path = store_path / "versions" / args.version / "split_manifest.json"
        split_manifest = json.loads(split_path.read_text(encoding="utf-8"))
        partitions = split_from_manifest(rows, split_manifest)
        registry = ModelRegistry(args.registry)
        record = next((row for row in registry.records() if row["model_id"] == args.model_id), None)
        split_digest = hashlib.sha256(split_path.read_bytes()).hexdigest()
        if (not record or record["training_dataset_version"] != args.version
                or record["training_dataset_content_hash"] != dataset_manifest["sha256"]
                or record.get("frozen_split_manifest_content_hash") != split_digest):
            raise RegistryError("candidate dataset version/content hash does not match evaluation data")
        model = registry.load_candidate(args.model_id, args.task)
        if args.task == "entity_ner":
            report = evaluate_entity_model(model, partitions["test"], split_manifest, "test")
            candidate_metrics = {"exact_match_f1": report["exact_span"]["exact_match_f1"]}
            baseline_metrics = {"exact_match_f1": report["deterministic_baseline"]["exact_span"]["exact_match_f1"]}
        else:
            report = evaluate_relationship_model(model, partitions["test"], split_manifest, "test", model.confidence_threshold)
            candidate_metrics = {f"micro_{key}": value for key, value in report["micro"].items()}
            baseline_metrics = {"micro_f1": report["deterministic_baseline"]["micro_f1"]}
        registry.record_evaluation(args.model_id, evaluation_split="test", metrics={"candidate": candidate_metrics, "baseline": baseline_metrics, "report": report})
        print(json.dumps({"model_id": args.model_id, "evaluation_split": "test", "metrics": report,
                          "approved": False}, indent=2, ensure_ascii=False))
    elif args.command == "approve-candidate":
        registry = ModelRegistry(args.registry)
        record = next((row for row in registry.records() if row["model_id"] == args.model_id), None)
        if not record:
            raise RegistryError("unknown model ID")
        test_metrics = record["evaluation_metrics"].get("test", {})
        baseline = test_metrics.get("baseline", {}).get(args.metric)
        if baseline is None:
            raise RegistryError("requested baseline metric is missing from held-out test evaluation")
        approved = registry.approve(args.model_id, metric=args.metric, baseline_score=float(baseline))
        print(json.dumps({"model_id": approved["model_id"], "approval_status": approved["approval_status"],
                          "metric": args.metric, "held_out_score": approved["held_out_score"],
                          "baseline_score": approved["baseline_score"]}, indent=2))
    elif args.command == "inspect-registry":
        manifest = Path(args.registry) / "registry.json"
        records = ModelRegistry(args.registry).records() if manifest.is_file() else []
        print(json.dumps(records, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

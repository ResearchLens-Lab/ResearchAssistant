from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.document_intelligence.extractor import DocumentIntelligenceExtractor
from rag.document_intelligence.store import ExtractionStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in local Phase 4 document intelligence extraction")
    parser.add_argument("--store", default="rag/document_intelligence/local_data")
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract one explicitly selected document")
    extract.add_argument("--document-id", required=True); extract.add_argument("--paper-id")
    extract.add_argument("--file", required=True); extract.add_argument("--private", action="store_true")
    get = commands.add_parser("show"); get.add_argument("--document-id", required=True); get.add_argument("--run-id")
    runs = commands.add_parser("runs"); runs.add_argument("--document-id", required=True)
    queue = commands.add_parser("review-queue", help="List pending knowledge records for one selected document")
    queue.add_argument("--document-id", required=True); queue.add_argument("--run-id")
    review = commands.add_parser("review"); review.add_argument("--document-id", required=True); review.add_argument("--run-id", required=True)
    review.add_argument("--record-id", required=True); review.add_argument("--action", choices=["approve", "reject", "correct"], required=True)
    review.add_argument("--reviewer", required=True); review.add_argument("--correction-json")
    review.add_argument("--training-permission", action="store_true")
    args = parser.parse_args(); store = ExtractionStore(args.store)
    if args.command == "extract":
        source = Path(args.file)
        if not source.is_file(): parser.error("--file must identify an existing file")
        try:
            result = DocumentIntelligenceExtractor().extract_file(source, args.document_id, args.paper_id, args.private)
        except Exception as exc:
            failure_path = store.save_failure(args.document_id, type(exc).__name__)
            parser.exit(2, f"Extraction failed ({type(exc).__name__}); failure recorded at {failure_path}\n")
        target, created = store.save(result)
        print(json.dumps({"run_id": result.run_id, "status": result.extraction_status,
                          "records": len(result.knowledge_records), "references": len(result.references),
                          "saved": created, "path": str(target), "duration_seconds": result.duration_seconds}, indent=2))
    elif args.command == "show": print(store.get(args.document_id, args.run_id).model_dump_json(indent=2))
    elif args.command == "runs": print(json.dumps(store.list_runs(args.document_id), indent=2))
    elif args.command == "review-queue":
        result = store.get(args.document_id, args.run_id)
        pending = [r.model_dump(mode="json") for r in result.knowledge_records if r.review_status == "pending"]
        print(json.dumps(pending, ensure_ascii=False, indent=2))
    elif args.command == "review":
        correction = json.loads(args.correction_json) if args.correction_json else None
        event = store.review(args.document_id, args.run_id, args.record_id, args.action, args.reviewer, correction, args.training_permission)
        print(event.model_dump_json(indent=2))


if __name__ == "__main__": main()

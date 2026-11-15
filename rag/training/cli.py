from __future__ import annotations

import argparse
import json

from rag.training.datasets import DatasetStore
from rag.training.schema import DatasetExample, ExampleStatus, TaskType


def main() -> None:
    parser = argparse.ArgumentParser(description="Local ResearchLens training-data annotation tools")
    parser.add_argument("--store", default="rag/training/local_data", help="Local annotation store directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-pending")
    add = commands.add_parser("add"); add.add_argument("--task", choices=[t.value for t in TaskType], required=True); add.add_argument("--input", required=True); add.add_argument("--label", required=True); add.add_argument("--passage"); add.add_argument("--document-id"); add.add_argument("--paper-id"); add.add_argument("--page", type=int); add.add_argument("--chunk-id"); add.add_argument("--source-group-id"); add.add_argument("--annotator", required=True); add.add_argument("--private", action="store_true"); add.add_argument("--training-permission", action="store_true")
    review = commands.add_parser("review"); review.add_argument("example_id"); review.add_argument("--status", choices=["approved", "rejected"], required=True); review.add_argument("--reviewer", required=True); review.add_argument("--correct-label"); review.add_argument("--correct-output")
    export = commands.add_parser("export-approved"); export.add_argument("--version", required=True)
    args = parser.parse_args(); store = DatasetStore(args.store)
    if args.command == "list-pending":
        print(json.dumps([item.model_dump(mode="json") for item in store.list_examples(ExampleStatus.PENDING)], indent=2))
    elif args.command == "add":
        example = DatasetExample(
            task_type=TaskType(args.task), input_text=args.input, candidate_passage=args.passage,
            expected_label=args.label, source_document_id=args.document_id, paper_id=args.paper_id,
            page_number=args.page, chunk_id=args.chunk_id, source_group_id=args.source_group_id, annotator=args.annotator,
            provenance={"entry_method": "local_cli"}, private_source=args.private,
            training_permission=args.training_permission,
        )
        print(store.add(example).example_id)
    elif args.command == "review":
        output = json.loads(args.correct_output) if args.correct_output else None
        item = store.review(args.example_id, ExampleStatus(args.status), args.reviewer, args.correct_label, output)
        print(item.model_dump_json(indent=2))
    elif args.command == "export-approved":
        print(store.export_approved(args.version))


if __name__ == "__main__":
    main()

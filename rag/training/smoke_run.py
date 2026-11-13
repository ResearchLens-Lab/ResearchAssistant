from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rag.training.datasets import validate_dataset
from rag.training.metrics import evaluate_intent_model, evaluate_passage_model
from rag.training.models import train_intent_classifier, train_passage_ranker
from rag.training.schema import DatasetExample, ExampleStatus, TaskType
from rag.training.splits import freeze_split_manifest, split_from_manifest


FIXTURE = Path(__file__).parent / "fixtures" / "phase2_smoke.jsonl"


def create_fixture() -> list[DatasetExample]:
    topics = [
        ("graph traversal", "breadth-first search"),
        ("sorting algorithms", "merge sort"),
        ("database indexing", "B-tree indexing"),
        ("machine learning", "cross-validation"),
        ("network routing", "shortest-path routing"),
        ("data compression", "Huffman coding"),
    ]
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index, (topic, method) in enumerate(topics, 1):
        group = f"synthetic-paper-{index:02d}"
        common = dict(
            review_status=ExampleStatus.APPROVED, reviewer="fixture-curator", reviewed_at=now,
            created_at=now, annotator="fixture-curator", source_group_id=group, source_document_id=group,
            paper_id=group, page_number=1, chunk_id=f"{group}-c1",
            provenance={"curation": "synthetic smoke fixture", "not_real_document": True},
            dataset_version="phase2-smoke-1", private_source=False,
        )
        intents = [
            (f"What is {topic}?", "DEFINITION"),
            (f"Who authored the paper about {topic}?", "AUTHOR_LOOKUP"),
            (f"Which methodology is used for {topic}?", "METHODOLOGY_EXTRACTION"),
        ]
        for offset, (question, label) in enumerate(intents):
            rows.append(DatasetExample(
                example_id=f"smoke-intent-{index}-{offset}", task_type=TaskType.INTENT,
                input_text=question, expected_label=label, **common,
            ))
        query = f"Which method is used for {topic}?"
        passages = [
            (f"The study uses {method} to address {topic}.", "3", "support"),
            (f"The paper discusses unrelated ocean temperature measurements.", "0", "distractor"),
        ]
        for passage, grade, suffix in passages:
            rows.append(DatasetExample(
                example_id=f"smoke-rank-{index}-{suffix}", task_type=TaskType.PASSAGE_RELEVANCE,
                input_text=query, candidate_passage=passage, expected_label=grade,
                provenance={**common["provenance"], "query_group_id": f"query-{index}"}, **{k:v for k,v in common.items() if k != "provenance"},
            ))
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text("".join(item.model_dump_json() + "\n" for item in rows), encoding="utf-8")
    return rows


def run() -> dict:
    items = create_fixture()
    quality = validate_dataset(items, require_reviewed=True)
    if not quality["valid"]:
        raise ValueError(quality)
    split_manifest = freeze_split_manifest(items, FIXTURE.with_name("phase2_smoke_split_v2.json"), seed=17)
    splits = split_from_manifest(items, split_manifest)
    intent = train_intent_classifier(splits["train"])
    ranker = train_passage_ranker(splits["train"])
    result = {
        "dataset": str(FIXTURE), "synthetic_only": True,
        "counts": {key: len(value) for key, value in splits.items()},
        "group_counts": {key: len({x.source_group_id for x in value}) for key, value in splits.items()},
        "quality": quality,
        "intent_test": evaluate_intent_model(intent, splits["test"]),
        "passage_ranking_test": evaluate_passage_model(ranker, splits["test"], k=2),
        "model_activated": False,
    }
    output = Path(__file__).parent / "fixtures" / "phase2_smoke_results.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

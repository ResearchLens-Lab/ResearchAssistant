"""Run the versioned Phase 1 gold set against a temporary, synthetic FTS5 corpus."""

import json
import re
import math
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from rag.config.settings import settings
from rag.independent.engine import IndependentResearchEngine
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.retriever import IndependentRetriever
from rag.independent.retriever import configured_lexical_collection_name


HERE = Path(__file__).parent
CORPUS = json.loads((HERE / "phase1_fixture_corpus.json").read_text(encoding="utf-8"))
DATASET = json.loads((HERE / "phase1_independent_dataset.json").read_text(encoding="utf-8"))


def build_index(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE VIRTUAL TABLE lexical_chunks USING fts5(chunk_id UNINDEXED, owner_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61')")
        db.executemany(
            "INSERT INTO lexical_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(row["chunk_id"], row.get("owner_id", "phase1_eval_owner"), configured_lexical_collection_name(), row["paper_id"], row["document_id"], row["section"], row["page"], row["page"], row["title"], row["filename"], f"Page {row['page']}", row["text"]) for row in CORPUS],
        )
        db.commit()


def run() -> dict:
    cases = DATASET["cases"]
    rows = []
    with tempfile.TemporaryDirectory(prefix="researchlens_phase1_eval_") as directory:
        index = Path(directory) / "researchlens_lexical.sqlite3"
        build_index(index)
        engine = IndependentResearchEngine(IndependentRetriever(index))
        classifier = QuestionIntentClassifier()
        for case in cases:
            analysis = classifier.classify(case["question"], paper_ids=case["papers"])
            result = engine.answer(case["question"], paper_ids=case["papers"], top_k=DATASET["top_k"])
            chunk_ids = [source.chunk_id for source in result.sources]
            found_rank = next((i for i, chunk in enumerate(chunk_ids, 1) if chunk in case["expected_chunks"]), None)
            expected_chunks = case["expected_chunks"]
            citation_ids = re.findall(r"\[(S\d+)\]", result.answer)
            source_ids = {source.source_id for source in result.sources}
            source_by_id = {source.source_id: source for source in result.sources}
            cited_chunks = {source_by_id[sid].chunk_id for sid in citation_ids if sid in source_by_id}
            evidence_check = result.metadata.get("independent_research", {}).get("evidence_decision", {})
            supported_ids = set(evidence_check.get("supported_source_ids", []))
            bad_citation_claims = [claim for claim in evidence_check.get("unsupported_claims", []) if "citation [" in claim and "does not map" in claim]
            expected_fact = case["expected_fact"].casefold()
            answer_low = result.answer.casefold()
            abstained = "not found in your selected documents." in answer_low
            rows.append({
                "id": case["id"], "question": case["question"],
                "expected_intent": case["intent"], "predicted_intent": analysis.intent.value,
                "intent_correct": analysis.intent.value == case["intent"],
                "expected_chunks": expected_chunks, "retrieved_chunks": chunk_ids,
                "relevant_retrieved": [chunk for chunk in chunk_ids if chunk in expected_chunks],
                "reciprocal_rank": 1 / found_rank if found_rank else 0.0,
                "citation_correct": (bool(citation_ids) and set(citation_ids) <= source_ids and set(citation_ids) <= supported_ids and not bad_citation_claims) if not case["abstain"] else (not citation_ids),
                "evidence_covered": bool(expected_chunks) and any(chunk in chunk_ids for chunk in expected_chunks),
                "cited_expected_chunks": len(cited_chunks.intersection(expected_chunks)),
                "expected_page": case["expected_page"],
                "page_correct": case["expected_page"] is None or any(source.chunk_id in expected_chunks and source.page_start == case["expected_page"] for source in result.sources),
                "expected_fact": case["expected_fact"],
                "extraction_correct": expected_fact in answer_low,
                "expected_abstain": case["abstain"], "abstained": abstained,
                "expected_conflict": case.get("expect_conflict", False),
                "abstention_correct": abstained == case["abstain"],
                "evidence_state": result.metadata.get("independent_research", {}).get("evidence_decision", {}).get("status"),
                "execution_time_seconds": result.metadata.get("execution_time_seconds", 0.0),
                "answer": result.answer,
            })
    n = len(rows)
    positive = [row for row in rows if row["expected_chunks"]]
    page_cases = [row for row in rows if row["expected_page"] is not None]
    abstention_cases = [row for row in rows if row["expected_abstain"]]
    expected_chunk_count = sum(len(row["expected_chunks"]) for row in positive)
    expected_conflicts = [row for row in rows if row["expected_conflict"]]
    latencies = sorted(row["execution_time_seconds"] for row in rows)
    metrics = {
        "cases": n,
        "intent_accuracy": sum(row["intent_correct"] for row in rows) / n,
        "recall_at_k": sum(row["evidence_covered"] for row in positive) / len(positive),
        "mrr": sum(row["reciprocal_rank"] for row in positive) / len(positive),
        "citation_correctness": sum(row["citation_correct"] for row in rows) / n,
        "evidence_coverage": sum(row["cited_expected_chunks"] for row in positive) / max(expected_chunk_count, 1),
        "physical_page_accuracy_when_expected": sum(row["page_correct"] for row in page_cases) / max(len(page_cases), 1),
        "extraction_correctness": sum(row["extraction_correct"] for row in positive) / max(len(positive), 1),
        "abstention_accuracy": sum(row["abstention_correct"] for row in abstention_cases) / max(len(abstention_cases), 1),
        "abstention_cases": len(abstention_cases),
        "conflict_cases_detected": sum(row["evidence_state"] == "CONFLICTING EVIDENCE" for row in expected_conflicts),
        "conflict_cases_expected": len(expected_conflicts),
        "mean_query_latency_seconds": sum(latencies) / max(len(latencies), 1),
        "p95_query_latency_seconds": latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)],
        "positive_evidence_cases": len(positive),
        "page_evaluation_cases": len(page_cases),
        "definition": "Recall@K is the fraction of answerable cases with any expected chunk in top K; MRR uses the first expected chunk. Evidence coverage is expected gold chunks that were actually cited divided by expected chunks. Citation correctness checks that citations map to returned source IDs (and abstentions contain no citations). Page accuracy uses only cases with a gold page. Synthetic smoke evaluation only; no confidence intervals or production claims.",
    }
    return {"dataset": DATASET["title"], "provenance": DATASET["provenance"], "metrics": metrics, "cases": rows}


if __name__ == "__main__":
    output = run()
    out_path = HERE / "phase1_evaluation_run.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output["metrics"], indent=2))
    print(f"Detailed case output: {out_path}")

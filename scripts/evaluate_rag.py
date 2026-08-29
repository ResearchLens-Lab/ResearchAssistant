#!/usr/bin/env python3
"""
CLI tool to run the practical RAG evaluation benchmark.

Usage:
    python scripts/evaluate_rag.py
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.evaluation.evaluator import RAGEvaluator


def main():
    parser = argparse.ArgumentParser(description="Evaluate ResearchLens RAG retrieval and generation metrics.")
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=str(Path(__file__).parent.parent / "rag" / "evaluation" / "datasets" / "sample_questions.json"),
        help="Path to evaluation questions JSON",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Top-K retrieval depth",
    )
    parser.add_argument(
        "--auto-ingest-fixture",
        action="store_true",
        default=True,
        help="Ensure benchmark papers are indexed before running evaluation",
    )

    args = parser.parse_args()

    print("\n🎯 ResearchLens RAG Evaluation Suite")
    print(f"   Dataset: {args.dataset_path}")
    print(f"   Top-K:   {args.top_k}\n")

    # Ingest benchmark fixture paper if needed
    if args.auto_ingest_fixture:
        sample_path = str(Path(__file__).parent / "sample_data" / "sample_paper.txt")
        ingest_p = IngestionPipeline()
        ingest_res = ingest_p.ingest_file(
            file_path=sample_path,
            paper_id="paper_attention_2017",
            metadata={"title": "Attention Is All You Need", "year": 2017},
        )
        print(f"📦 Pre-indexing fixture: {ingest_res.paper_id} ({ingest_res.chunk_count} chunks indexed)")

    evaluator = RAGEvaluator()
    summary = evaluator.run_evaluation(top_k=args.top_k)

    print("\n" + "=" * 70)
    print("📈 EVALUATION RESULTS SUMMARY:")
    print("=" * 70)
    print(f"Total Questions Evaluated:  {summary.total_questions}")
    print(f"Mean Hit@{args.top_k}:               {summary.mean_hit_at_k * 100:.1f}%")
    print(f"Mean Source Relevance:      {summary.mean_source_relevance * 100:.1f}%")
    print(f"Mean Answer Grounding:      {summary.mean_answer_grounding * 100:.1f}%")
    print(f"Mean Citation Correctness:  {summary.mean_citation_correctness * 100:.1f}%")
    print("=" * 70)

    print("\n📝 Per-Question Breakdown:")
    for item in summary.item_results:
        print(f"\n[{item.question_id}] {item.question}")
        print(f"    Hit@{args.top_k}: {item.hit_at_k} | Relevance: {item.source_relevance} | Grounding: {item.answer_grounding} | Citation: {item.citation_correctness}")
        print(f"    Retrieved: {item.retrieved_count} sources | Cited: {item.cited_count} sources")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI tool to query ResearchLens RAG for grounded answers with citation mapping.

Usage:
    python scripts/query_rag.py --question "What is the main contribution of this paper?" --paper-ids paper_sample_01
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.query_pipeline import QueryPipeline


def main():
    parser = argparse.ArgumentParser(description="Query ResearchLens RAG engine.")
    parser.add_argument(
        "--question",
        type=str,
        default="What is the core architecture and contribution of the Transformer?",
        help="Research question to ask",
    )
    parser.add_argument(
        "--paper-ids",
        nargs="+",
        default=["paper_sample_01"],
        help="List of paper IDs to search within",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of chunks to retrieve",
    )

    args = parser.parse_args()

    print("\n🔍 Querying ResearchLens RAG:")
    print(f"   Question:  {args.question}")
    print(f"   Paper IDs: {args.paper_ids}")
    print(f"   Top-K:     {args.top_k}\n")

    pipeline = QueryPipeline()
    result = pipeline.answer_question(
        question=args.question,
        paper_ids=args.paper_ids,
        top_k=args.top_k,
    )

    print("=" * 70)
    print("🤖 GROUNDED ANSWER:")
    print("=" * 70)
    print(result.answer)
    print("\n" + "=" * 70)
    print("📚 SUPPORTING SOURCES & CITATIONS:")
    print("=" * 70)

    if not result.sources:
        print("  (No supporting sources retrieved)")
    else:
        for idx, src in enumerate(result.sources, start=1):
            print(f"[{src.source_id}] Paper ID: {src.paper_id} | {src.page_display} | Section: {src.section}")
            print(f"    Chunk ID: {src.chunk_id}")
            print(f"    Score:    {src.score}")
            print(f"    Snippet:  \"{src.text.strip()[:200]}...\"\n")

    print("=" * 70)
    print(f"⏱  Execution Time: {result.metadata.get('execution_time_seconds', 0.0)}s\n")


if __name__ == "__main__":
    main()

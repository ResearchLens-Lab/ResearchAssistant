#!/usr/bin/env python3
"""
CLI tool to compare multiple research papers using comparative RAG.

Usage:
    python scripts/compare_papers.py --paper-ids paper_sample_01 paper_sample_02
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.query_pipeline import QueryPipeline


def main():
    parser = argparse.ArgumentParser(description="Compare multiple research papers using RAG.")
    parser.add_argument(
        "--paper-ids",
        nargs="+",
        default=["paper_sample_01", "paper_sample_02"],
        help="List of paper IDs to compare",
    )
    parser.add_argument(
        "--focus-area",
        type=str,
        default="Compare architectures, representations, and experimental findings.",
        help="Specific focus area for comparison",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of context chunks to assemble",
    )

    args = parser.parse_args()

    print("\n⚖️  Comparing Research Papers:")
    print(f"   Papers:     {args.paper_ids}")
    print(f"   Focus Area: {args.focus_area}\n")

    pipeline = QueryPipeline()
    result = pipeline.compare_papers(
        paper_ids=args.paper_ids,
        focus_area=args.focus_area,
        top_k=args.top_k,
    )

    print("=" * 70)
    print("📊 COMPARATIVE ANALYSIS:")
    print("=" * 70)
    print(result.answer)
    print("\n" + "=" * 70)
    print("📚 ATTRIBUTED SOURCES BY PAPER:")
    print("=" * 70)
    for src in result.sources:
        print(f"[{src.source_id}] Paper: {src.paper_id} | {src.page_display} (Section: {src.section})")
        print(f"    Text: \"{src.text.strip()[:150]}...\"\n")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

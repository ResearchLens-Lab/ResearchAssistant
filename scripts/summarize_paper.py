#!/usr/bin/env python3
"""
CLI tool to generate structured grounded paper summaries.

Usage:
    python scripts/summarize_paper.py --paper-id paper_sample_01
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.query_pipeline import QueryPipeline


def main():
    parser = argparse.ArgumentParser(description="Generate structured research paper summary.")
    parser.add_argument(
        "--paper-id",
        type=str,
        default="paper_sample_01",
        help="Paper ID to summarize",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Number of context chunks to assemble",
    )

    args = parser.parse_args()

    print(f"\n📋 Generating Structured Summary for Paper: {args.paper_id}\n")

    pipeline = QueryPipeline()
    result = pipeline.summarize_paper(paper_id=args.paper_id, top_k=args.top_k)

    print("=" * 70)
    print("📄 STRUCTURED RESEARCH SUMMARY:")
    print("=" * 70)
    print(result.answer)
    print("\n" + "=" * 70)
    print("📚 CITATION EVIDENCE:")
    print("=" * 70)
    for src in result.sources:
        print(f"- [{src.source_id}] {src.page_display} ({src.section}): \"{src.text.strip()[:140]}...\"")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI tool to ingest research papers into ChromaDB.

Usage:
    python scripts/ingest_sample.py
    python scripts/ingest_sample.py --file-path path/to/paper.pdf --paper-id paper_123
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.ingest_pipeline import IngestionPipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest research paper into ResearchLens RAG vector store.")
    parser.add_argument(
        "--file-path",
        type=str,
        default=str(Path(__file__).parent / "sample_data" / "sample_paper.txt"),
        help="Path to PDF or text file",
    )
    parser.add_argument(
        "--paper-id",
        type=str,
        default="paper_sample_01",
        help="Unique identifier for the research paper",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Attention Is All You Need",
        help="Paper title",
    )
    parser.add_argument(
        "--authors",
        type=str,
        default="Vaswani et al.",
        help="Comma-separated authors",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2017,
        help="Publication year",
    )

    args = parser.parse_args()

    print(f"\n🚀 Ingesting Document: {args.file_path}")
    print(f"   Paper ID: {args.paper_id}")
    print(f"   Title:    {args.title}\n")

    pipeline = IngestionPipeline()
    result = pipeline.ingest_file(
        file_path=args.file_path,
        paper_id=args.paper_id,
        metadata={
            "title": args.title,
            "authors": args.authors,
            "year": args.year,
        },
    )

    if result.success:
        print("✅ Ingestion Successful!")
        print(f"   Document ID:  {result.document_id}")
        print(f"   Total Pages:  {result.total_pages}")
        print(f"   Chunks Count: {result.chunk_count}")
        print(f"   Elapsed Time: {result.execution_time_seconds}s\n")
    else:
        print("❌ Ingestion Failed!")
        print(f"   Error: {result.error}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

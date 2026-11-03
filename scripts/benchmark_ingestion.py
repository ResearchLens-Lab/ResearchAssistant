"""Offline PDF ingestion benchmark; never calls Gemini.

Run from the repository root with:
    python scripts/benchmark_ingestion.py --pages 3 --words-per-page 50

The default vector sink is a no-op so results isolate parser, chunker, and mock
embedding CPU cost. Pass --with-chroma to measure local Chroma and lexical
index writes in a temporary directory.
"""

import argparse
import json
import tempfile
import time
import sys
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.chunking.metadata import DocumentChunk
from rag.embeddings.embedder import DeterministicMockEmbedder
from rag.ingestion.document_loader import PDFDocumentLoader
from rag.pipelines.ingest_pipeline import IngestionPipeline


class NullVectorRepository:
    def upsert_chunks(self, chunks, embeddings):
        return len(chunks)

    def delete_document_chunks(self, document_id):
        return 0


def make_pdf(path: Path, pages: int, words_per_page: int) -> None:
    passage = " ".join(f"algorithm theorem search graph evidence {index}" for index in range(words_per_page))
    with pymupdf.open() as pdf:
        for page_number in range(1, pages + 1):
            page = pdf.new_page()
            page.insert_textbox(
                pymupdf.Rect(40, 40, 550, 780),
                f"Page {page_number}\n{passage}", fontsize=10,
            )
        pdf.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--words-per-page", type=int, default=50)
    parser.add_argument("--with-chroma", action="store_true")
    args = parser.parse_args()
    if args.pages < 1 or args.words_per_page < 1:
        parser.error("pages and words-per-page must be positive")

    with tempfile.TemporaryDirectory(prefix="researchlens-benchmark-") as tmp:
        root = Path(tmp)
        source = root / "fixture.pdf"
        make_pdf(source, args.pages, args.words_per_page)

        repo = NullVectorRepository()
        chroma_client = None
        if args.with_chroma:
            import chromadb
            from rag.vectorstore.chroma_client import ChromaClientFactory
            from rag.vectorstore.collection_manager import CollectionManager
            from rag.vectorstore.vector_repository import VectorRepository

            chroma_client = chromadb.PersistentClient(path=str(root / "chroma"))
            ChromaClientFactory._client_persist_dirs[id(chroma_client)] = str(root / "chroma")

            class BenchmarkCollectionManager(CollectionManager):
                def get_or_create_collection(self, name=None, metadata=None):
                    return super().get_or_create_collection(
                        name="benchmark_mock_768",
                        metadata={"hnsw:space": "cosine", "embedding_model": "deterministic-mock", "embedding_dimension": 768},
                    )

            repo = VectorRepository(collection_manager=BenchmarkCollectionManager(chroma_client))

        timings = {"extraction_seconds": 0.0, "chunking_seconds": 0.0,
                   "embedding_seconds": 0.0, "indexing_seconds": 0.0}
        started = time.perf_counter()
        normalized = PDFDocumentLoader().load(
            str(source), {"document_id": "benchmark-document", "paper_id": "benchmark-paper"}
        )
        timings["extraction_seconds"] = time.perf_counter() - started

        embedder = DeterministicMockEmbedder(dimension=768)
        pipeline = IngestionPipeline(embedder=embedder, vector_repo=repo)
        original_chunk = pipeline.chunker.chunk_document
        def timed_chunk(document):
            stage = time.perf_counter()
            result = original_chunk(document)
            timings["chunking_seconds"] += time.perf_counter() - stage
            return result
        pipeline.chunker.chunk_document = timed_chunk

        original_embed = embedder.embed_documents
        def timed_embed(texts):
            stage = time.perf_counter()
            result = original_embed(texts)
            timings["embedding_seconds"] += time.perf_counter() - stage
            return result
        embedder.embed_documents = timed_embed

        original_upsert = repo.upsert_chunks
        def timed_upsert(chunks: list[DocumentChunk], vectors):
            stage = time.perf_counter()
            result = original_upsert(chunks, vectors)
            timings["indexing_seconds"] += time.perf_counter() - stage
            return result
        repo.upsert_chunks = timed_upsert

        result = pipeline._process_normalized_doc(normalized, time.perf_counter())
        timings["total_seconds"] = timings["extraction_seconds"] + timings["chunking_seconds"] + timings["embedding_seconds"] + timings["indexing_seconds"]
        print(json.dumps({
            "fixture_bytes": source.stat().st_size,
            "pages": result.total_pages,
            "chunks": result.chunk_count,
            "success": result.success,
            "vector_sink": "chromadb+sqlite_fts" if args.with_chroma else "no-op",
            **{key: round(value, 4) for key, value in timings.items()},
        }, indent=2))
        if chroma_client is not None:
            chroma_system = getattr(chroma_client, "_system", None)
            stop = getattr(chroma_system, "stop", None)
            if callable(stop):
                stop()


if __name__ == "__main__":
    main()

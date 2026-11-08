"""
Ingestion Pipeline for ResearchLens RAG.
Orchestrates: File -> Load -> Normalize -> Chunk -> Batch Embed -> ChromaDB Index.
"""

import time
import logging
from threading import Event
from typing import Optional, Dict, Any, List, Callable
from pydantic import BaseModel, Field

from rag.ingestion.document_loader import DocumentLoaderFactory, BaseDocumentLoader, PDFDocumentLoader, TextDocumentLoader
from rag.ingestion.document_normalizer import NormalizedDocument
from rag.chunking.chunker import DocumentChunker
from rag.embeddings.embedder import BaseEmbedder, FastEmbedder
from rag.embeddings.model_registry import EmbeddingModelRegistry
from rag.embeddings.batch_generator import BatchEmbeddingGenerator
from rag.config.settings import settings
from rag.vectorstore.vector_repository import VectorRepository

logger = logging.getLogger(__name__)


class IngestionCancelled(RuntimeError):
    """Cooperative stop requested between synchronous ingestion stages."""


class IngestResult(BaseModel):
    """
    Standard result returned after document ingestion.
    """
    success: bool
    status: str = Field(..., description="'indexed' or 'failed'")
    document_id: str
    paper_id: str
    chunk_count: int = 0
    total_pages: int = 0
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionPipeline:
    """
    End-to-end ingestion pipeline for indexing research documents into ChromaDB.
    """

    def __init__(
        self,
        chunker: Optional[DocumentChunker] = None,
        embedder: Optional[BaseEmbedder] = None,
        vector_repo: Optional[VectorRepository] = None,
    ):
        self.embedder = embedder or EmbeddingModelRegistry.get_embedder()
        if chunker is None:
            token_limiter = self.embedder.split_text_for_embedding if isinstance(self.embedder, FastEmbedder) else None
            self.chunker = DocumentChunker(token_limiter=token_limiter)
        else:
            self.chunker = chunker
            if isinstance(self.embedder, FastEmbedder):
                self.chunker.token_limiter = self.embedder.split_text_for_embedding
        self.vector_repo = vector_repo or VectorRepository()
        self.batch_generator = BatchEmbeddingGenerator(self.embedder, batch_size=settings.embedding_batch_size)

    def ingest_file(
        self,
        file_path: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[Event] = None,
    ) -> IngestResult:
        """
        Loads a document file (PDF, TXT, MD), processes, chunks, embeds, and indexes it.
        """
        start_time = time.perf_counter()
        meta = metadata.copy() if metadata else {}
        if paper_id:
            meta["paper_id"] = paper_id

        try:
            self._check_cancel(cancel_event, "before extraction")
            if progress_callback:
                progress_callback({"stage": "extracting_text", "progress": 5, "progress_type": "estimated"})
            loader: BaseDocumentLoader = DocumentLoaderFactory.get_loader(file_path)
            stage_started = time.perf_counter()
            if isinstance(loader, PDFDocumentLoader):
                normalized_doc = loader.load(file_path, metadata=meta, progress_callback=progress_callback)
            else:
                normalized_doc = loader.load(file_path, metadata=meta)
            self._check_cancel(cancel_event, "after extraction")
            logger.info(
                "Ingestion stage complete document_id=%s stage=extracting_text duration_seconds=%.3f pages=%d characters=%d",
                meta.get("document_id", "unknown_doc"), time.perf_counter() - stage_started,
                normalized_doc.total_pages, sum(len(page.text) for page in normalized_doc.pages),
            )
            if progress_callback:
                progress_callback({"stage": "chunking", "progress": 25, "progress_type": "estimated",
                                   "completed_pages": normalized_doc.total_pages, "total_pages": normalized_doc.total_pages})

            result = self._process_normalized_doc(normalized_doc, start_time, progress_callback, cancel_event)
            return result

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error("Ingestion failed exception_type=%s", type(e).__name__)
            doc_id = meta.get("document_id", "unknown_doc")
            pid = meta.get("paper_id", paper_id or "unknown_paper")
            error = str(e)
            if doc_id != "unknown_doc":
                try:
                    self.vector_repo.delete_document_chunks(doc_id)
                except Exception as cleanup_error:
                    logger.exception("Failed to clean partial document index document_id=%s", doc_id)
                    error = f"{error}; index cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
            return IngestResult(
                success=False,
                status="failed",
                document_id=doc_id,
                paper_id=pid,
                chunk_count=0,
                total_pages=0,
                error=error,
                execution_time_seconds=round(elapsed, 3),
            )

    def ingest_text(
        self,
        content: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[Event] = None,
    ) -> IngestResult:
        """
        Directly ingests a raw string or markdown text.
        """
        start_time = time.perf_counter()
        meta = metadata.copy() if metadata else {}
        if paper_id:
            meta["paper_id"] = paper_id

        try:
            self._check_cancel(cancel_event, "before extraction")
            loader = TextDocumentLoader()
            normalized_doc: NormalizedDocument = loader.load_text(content=content, metadata=meta)
            self._check_cancel(cancel_event, "after extraction")
            if progress_callback:
                progress_callback({"stage": "chunking", "progress": 25, "progress_type": "estimated",
                                   "completed_pages": normalized_doc.total_pages, "total_pages": normalized_doc.total_pages})
            return self._process_normalized_doc(normalized_doc, start_time, progress_callback, cancel_event)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error("Text ingestion failed exception_type=%s", type(e).__name__)
            doc_id = meta.get("document_id", "unknown_doc")
            error = str(e)
            if doc_id != "unknown_doc":
                try:
                    self.vector_repo.delete_document_chunks(doc_id)
                except Exception as cleanup_error:
                    logger.exception("Failed to clean partial document index document_id=%s", doc_id)
                    error = f"{error}; index cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
            return IngestResult(
                success=False,
                status="failed",
                document_id=doc_id,
                paper_id=meta.get("paper_id", paper_id or "unknown_paper"),
                chunk_count=0,
                total_pages=0,
                error=error,
                execution_time_seconds=round(elapsed, 3),
            )

    def _process_normalized_doc(
        self,
        doc: NormalizedDocument,
        start_time: float,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[Event] = None,
    ) -> IngestResult:
        # 1. Chunk document
        self._check_cancel(cancel_event, "before chunking")
        chunk_started = time.perf_counter()
        chunks = self.chunker.chunk_document(doc)
        self._check_cancel(cancel_event, "after chunking")
        chunk_seconds = time.perf_counter() - chunk_started
        logger.info(
            "Ingestion stage complete document_id=%s stage=chunking duration_seconds=%.3f chunks=%d",
            doc.document_id, chunk_seconds, len(chunks),
        )
        if progress_callback:
            progress_callback({"stage": "generating_embeddings", "progress": 30,
                               "progress_type": "estimated", "completed_chunks": 0,
                               "total_chunks": len(chunks)})
        if not chunks:
            raise RuntimeError("No text chunks could be extracted from the document.")

        # Bound vector memory by embedding and indexing one batch at a time.
        # Remove earlier batches if a later one fails so partial documents are
        # never reported as indexed or left searchable.
        upserted_count = 0
        embedding_seconds = 0.0
        indexing_seconds = 0.0
        embedding_batches_attempted = 0
        embedding_batches_completed = 0
        active_stage = "generating_embeddings"
        batch_count = (len(chunks) + self.batch_generator.batch_size - 1) // self.batch_generator.batch_size
        try:
            for batch_index, start in enumerate(range(0, len(chunks), self.batch_generator.batch_size)):
                self._check_cancel(cancel_event, "before embedding batch")
                batch = chunks[start:start + self.batch_generator.batch_size]
                if progress_callback:
                    progress_callback({"stage": "generating_embeddings", "progress": round(30 + 65 * (2 * batch_index) / (2 * batch_count)),
                                       "progress_type": "estimated", "completed_chunks": start,
                                       "total_chunks": len(chunks)})
                active_stage = "generating_embeddings"
                stage_started = time.perf_counter()
                embedding_batches_attempted += 1
                try:
                    vectors = self.embedder.embed_documents([chunk.text for chunk in batch])
                finally:
                    embedding_seconds += time.perf_counter() - stage_started
                embedding_batches_completed += 1
                if len(vectors) != len(batch):
                    raise RuntimeError(f"Embedding provider returned {len(vectors)} vectors for {len(batch)} chunks.")
                if any(len(vector) != self.embedder.dimension for vector in vectors):
                    raise RuntimeError(f"Embedding provider returned a vector with an unexpected dimension; expected {self.embedder.dimension}.")
                self._check_cancel(cancel_event, "after embedding batch")
                if progress_callback:
                    progress_callback({"stage": "indexing", "progress": round(30 + 65 * (2 * batch_index + 1) / (2 * batch_count)),
                                       "progress_type": "estimated", "completed_chunks": start,
                                       "total_chunks": len(chunks)})
                active_stage = "indexing"
                stage_started = time.perf_counter()
                upserted_count += self.vector_repo.upsert_chunks(batch, vectors)
                self._check_cancel(cancel_event, "after indexing batch")
                indexing_seconds += time.perf_counter() - stage_started
                if progress_callback:
                    progress_callback({"stage": "generating_embeddings" if batch_index + 1 < batch_count else "indexing",
                                       "progress": round(30 + 65 * (2 * batch_index + 2) / (2 * batch_count)),
                                       "progress_type": "estimated", "completed_chunks": start + len(batch),
                                       "total_chunks": len(chunks)})
        except Exception as exc:
            logger.error(
                "Ingestion stage failed document_id=%s stage=%s pages=%d chunks=%d embedding_batches=%d/%d completed_batches=%d retries=0 embedded_seconds=%.3f indexed_chunks_before_cleanup=%d exception_type=%s error=%s",
                doc.document_id, active_stage, doc.total_pages, len(chunks),
                embedding_batches_attempted, batch_count, embedding_batches_completed,
                embedding_seconds, upserted_count,
                type(exc).__name__, str(exc)[:500],
            )
            raise

        expected_ids = {chunk.metadata.chunk_id for chunk in chunks}
        self._check_cancel(cancel_event, "before index reconciliation")
        self.vector_repo.reconcile_document_chunks(doc.document_id, expected_ids)
        counts = self.vector_repo.document_index_counts(doc.document_id)
        if (not counts["ids_match"] or counts["chroma_count"] != len(expected_ids)
                or counts["fts_count"] != len(expected_ids)):
            raise RuntimeError(
                "Index consistency check failed after ingestion "
                f"(expected={len(expected_ids)}, Chroma={counts['chroma_count']}, FTS5={counts['fts_count']}, "
                f"ids_match={counts['ids_match']})."
            )
        self._check_cancel(cancel_event, "after index reconciliation")
        elapsed = time.perf_counter() - start_time
        if progress_callback:
            progress_callback({"stage": "ready", "progress": 100, "progress_type": "actual",
                               "completed_chunks": upserted_count, "total_chunks": len(chunks)})
        logger.info(
            "Ingestion successful paper_id=%s document_id=%s pages=%d chunks=%d duration_seconds=%.3f chunk_seconds=%.3f embedding_seconds=%.3f indexing_seconds=%.3f embedding_batches=%d",
            doc.paper_id,
            doc.document_id,
            doc.total_pages,
            upserted_count,
            elapsed,
            chunk_seconds,
            embedding_seconds,
            indexing_seconds,
            batch_count,
        )

        return IngestResult(
            success=True,
            status="indexed",
            document_id=doc.document_id,
            paper_id=doc.paper_id,
            chunk_count=upserted_count,
            total_pages=doc.total_pages,
            execution_time_seconds=round(elapsed, 3),
            metadata={
                "title": doc.title,
                "authors": doc.authors,
                "year": doc.year,
                "sections": [s.name for s in doc.sections],
            },
        )

    @staticmethod
    def _check_cancel(cancel_event: Optional[Event], stage: str) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise IngestionCancelled(f"Ingestion cancelled at safe boundary: {stage}.")

    def delete_paper(self, paper_id: str) -> int:
        """
        Deletes indexed chunks for a paper.
        """
        return self.vector_repo.delete_paper_chunks(paper_id)

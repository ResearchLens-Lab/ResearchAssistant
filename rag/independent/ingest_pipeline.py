"""Document and text ingestion into the local FTS5 index without model calls."""

import logging
import time
from threading import Event
from typing import Any, Callable

from rag.chunking.chunker import DocumentChunker
from rag.config.settings import settings
from rag.independent.index_writer import IndependentIndexWriter
from rag.ingestion.document_loader import DocumentLoaderFactory, PDFDocumentLoader, TextDocumentLoader
from rag.pipelines.ingest_pipeline import IngestResult, IngestionCancelled


logger = logging.getLogger(__name__)


class IndependentIngestionPipeline:
    """Text extraction, page-aware chunking and transactional FTS5 writes only."""

    def __init__(self, chunker: DocumentChunker | None = None, index_writer: IndependentIndexWriter | None = None):
        self.chunker = chunker or DocumentChunker()
        self.index_writer = index_writer or IndependentIndexWriter()

    def ingest_file(self, file_path: str, paper_id: str | None = None,
                    metadata: dict[str, Any] | None = None,
                    progress_callback: Callable[[dict], None] | None = None,
                    cancel_event: Event | None = None) -> IngestResult:
        started = time.perf_counter()
        meta = dict(metadata or {})
        if paper_id:
            meta["paper_id"] = paper_id
        document_id = str(meta.get("document_id") or file_path)
        try:
            self._check_cancel(cancel_event, "before extraction")
            self._emit(progress_callback, {"stage": "extracting_text", "progress": 5, "progress_type": "estimated"})
            loader = DocumentLoaderFactory.get_loader(file_path)
            if isinstance(loader, PDFDocumentLoader):
                normalized = loader.load(file_path, metadata=meta, progress_callback=progress_callback, cancel_event=cancel_event)
            else:
                normalized = loader.load(file_path, metadata=meta)
            self._check_cancel(cancel_event, "after extraction")
            self._emit(progress_callback, {"stage": "chunking", "progress": 25, "progress_type": "estimated",
                                           "completed_pages": normalized.total_pages, "total_pages": normalized.total_pages})
            return self._index(normalized, started, progress_callback, cancel_event)
        except Exception as exc:
            self.index_writer.delete_document(document_id)
            logger.error("Independent ingestion failed document_id=%s exception_type=%s", document_id, type(exc).__name__)
            return IngestResult(success=False, status="failed", document_id=document_id,
                                paper_id=str(meta.get("paper_id") or paper_id or "unknown_paper"),
                                error=str(exc), execution_time_seconds=round(time.perf_counter() - started, 3),
                                metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False})

    def ingest_text(self, content: str, paper_id: str | None = None,
                    metadata: dict[str, Any] | None = None,
                    progress_callback: Callable[[dict], None] | None = None,
                    cancel_event: Event | None = None) -> IngestResult:
        started = time.perf_counter()
        meta = dict(metadata or {})
        if paper_id:
            meta["paper_id"] = paper_id
        try:
            self._check_cancel(cancel_event, "before extraction")
            normalized = TextDocumentLoader().load_text(content=content, metadata=meta)
            self._check_cancel(cancel_event, "after extraction")
            self._emit(progress_callback, {"stage": "chunking", "progress": 25, "progress_type": "estimated",
                                           "completed_pages": normalized.total_pages, "total_pages": normalized.total_pages})
            return self._index(normalized, started, progress_callback, cancel_event)
        except Exception as exc:
            document_id = str(meta.get("document_id") or "unknown_doc")
            if document_id != "unknown_doc":
                self.index_writer.delete_document(document_id)
            return IngestResult(success=False, status="failed", document_id=document_id,
                                paper_id=str(meta.get("paper_id") or paper_id or "unknown_paper"),
                                error=str(exc), execution_time_seconds=round(time.perf_counter() - started, 3),
                                metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False})

    def _index(self, normalized, started, progress_callback, cancel_event) -> IngestResult:
        self._check_cancel(cancel_event, "before chunking")
        chunks = self.chunker.chunk_document(normalized)
        if not chunks:
            raise RuntimeError("No text chunks could be extracted from the document.")
        self._emit(progress_callback, {"stage": "indexing", "progress": 70, "progress_type": "actual",
                                       "completed_chunks": 0, "total_chunks": len(chunks)})
        self._check_cancel(cancel_event, "before SQLite index write")
        count = self.index_writer.replace_document_chunks(normalized.document_id, chunks)
        try:
            self._check_cancel(cancel_event, "after SQLite index write")
        except Exception:
            self.index_writer.delete_document(normalized.document_id)
            raise
        elapsed = time.perf_counter() - started
        self._emit(progress_callback, {"stage": "ready", "progress": 100, "progress_type": "actual",
                                       "completed_chunks": count, "total_chunks": count})
        return IngestResult(success=True, status="indexed", document_id=normalized.document_id,
                            paper_id=normalized.paper_id, chunk_count=count, total_pages=normalized.total_pages,
                            execution_time_seconds=round(elapsed, 3),
                            metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False,
                                      "truncation_occurred": False, "chunk_count_verified": count == len(chunks)})

    def delete_paper(self, paper_id: str) -> int:
        return self.index_writer.delete_paper(paper_id)

    @staticmethod
    def _check_cancel(cancel_event: Event | None, stage: str) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise IngestionCancelled(f"Ingestion cancelled {stage}.")

    @staticmethod
    def _emit(callback: Callable[[dict], None] | None, event: dict) -> None:
        if callback:
            callback(event)

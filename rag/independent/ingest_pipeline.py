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
        had_existing_index = False
        try:
            had_existing_index = self.index_writer.count_document(document_id).get("lexical_count", 0) > 0
        except Exception:
            pass
        try:
            self._check_cancel(cancel_event, "before extraction")
            self._emit(progress_callback, {"stage": "extracting_text", "progress": 5, "progress_type": "estimated"})
            loader = DocumentLoaderFactory.get_loader(file_path)
            if isinstance(loader, PDFDocumentLoader):
                normalized = loader.load(file_path, metadata=meta, progress_callback=progress_callback, cancel_event=cancel_event)
            else:
                normalized = loader.load(file_path, metadata=meta)
            self._check_cancel(cancel_event, "after extraction")
            self._emit(progress_callback, {"stage": "chunking", "progress": 55, "progress_type": "actual",
                                           "completed_pages": normalized.total_pages, "total_pages": normalized.total_pages})
            return self._index(normalized, started, progress_callback, cancel_event, file_path=file_path)
        except Exception as exc:
            if not had_existing_index:
                self.index_writer.delete_document(document_id)
            is_cancelled = isinstance(exc, IngestionCancelled) or (cancel_event is not None and cancel_event.is_set())
            if is_cancelled:
                logger.info("Independent ingestion cancelled document_id=%s stage=%s", document_id, exc)
                return IngestResult(
                    success=False,
                    status="cancelled",
                    document_id=document_id,
                    paper_id=str(meta.get("paper_id") or paper_id or "unknown_paper"),
                    error="Ingestion cancelled by user.",
                    execution_time_seconds=round(time.perf_counter() - started, 3),
                    metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False, "existing_index_preserved": had_existing_index},
                )
            logger.error("Independent ingestion failed document_id=%s exception_type=%s", document_id, type(exc).__name__)
            return IngestResult(success=False, status="failed", document_id=document_id,
                                paper_id=str(meta.get("paper_id") or paper_id or "unknown_paper"),
                                error=str(exc), execution_time_seconds=round(time.perf_counter() - started, 3),
                                metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False, "existing_index_preserved": had_existing_index})

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
            self._emit(progress_callback, {"stage": "chunking", "progress": 55, "progress_type": "actual",
                                           "completed_pages": normalized.total_pages, "total_pages": normalized.total_pages})
            return self._index(normalized, started, progress_callback, cancel_event, file_path=None)
        except Exception as exc:
            document_id = str(meta.get("document_id") or "unknown_doc")
            if document_id != "unknown_doc":
                self.index_writer.delete_document(document_id)
            return IngestResult(success=False, status="failed", document_id=document_id,
                                paper_id=str(meta.get("paper_id") or paper_id or "unknown_paper"),
                                error=str(exc), execution_time_seconds=round(time.perf_counter() - started, 3),
                                metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False})

    def _index(self, normalized, started, progress_callback, cancel_event, file_path: str | None = None) -> IngestResult:
        self._check_cancel(cancel_event, "before chunking")
        chunks = self.chunker.chunk_document(normalized)
        if not chunks:
            raise RuntimeError("No text chunks could be extracted from the document.")
        self._emit(progress_callback, {"stage": "indexing", "progress": 80, "progress_type": "actual",
                                       "completed_chunks": 0, "total_chunks": len(chunks)})
        self._check_cancel(cancel_event, "before SQLite index write")
        count = self.index_writer.replace_document_chunks(normalized.document_id, chunks)
        try:
            from rag.intelligence.concept_graph_extractor import ConceptGraphExtractor
            db_candidates = [
                Path(self.index_writer.db_path).parent.parent / "library.sqlite3",
                Path(self.index_writer.db_path).parent / "library.sqlite3",
                Path(os.environ.get("LOCALAPPDATA", "")) / "ResearchLens" / "Library" / "library.sqlite3",
                Path("library.sqlite3"),
            ]
            kg_db = next((p for p in db_candidates if p.exists()), None)
            if kg_db:
                owner_id = str(getattr(normalized, "metadata", {}).get("owner_id", ""))
                extractor = ConceptGraphExtractor(db_path=kg_db)
                extractor.ingest_document_kg(
                    owner_id=owner_id,
                    paper_id=normalized.paper_id,
                    document_id=normalized.document_id,
                    chunks_or_sections=chunks,
                    db_path=kg_db,
                )
        except Exception as kg_err:
            logger.debug("Concept graph auto-ingestion notice: %s", kg_err)
        try:
            self._check_cancel(cancel_event, "after SQLite index write")
        except Exception:
            self.index_writer.delete_document(normalized.document_id)
            raise
        elapsed = time.perf_counter() - started
        self._emit(progress_callback, {"stage": "ready", "progress": 100, "progress_type": "actual",
                                       "completed_chunks": count, "total_chunks": count})

        pages = getattr(normalized, "pages", [])
        ocr_pages = [p for p in pages if getattr(p, "is_ocr", False)]
        has_ocr = len(ocr_pages) > 0
        has_low_conf = any((getattr(p, "ocr_confidence", 1.0) or 1.0) < 0.40 for p in ocr_pages)
        has_empty_pages = any(not (getattr(p, "text", "") or "").strip() for p in pages) and len(pages) > 1

        final_status = "indexed"

        # Clean up intermediate OCR checkpoint upon successful ingestion
        if file_path:
            try:
                checkpoint_file = Path(file_path).parent / f".ocr-{normalized.document_id}.json"
                checkpoint_file.unlink(missing_ok=True)
            except Exception:
                pass

        return IngestResult(success=True, status=final_status, document_id=normalized.document_id,
                            paper_id=normalized.paper_id, chunk_count=count, total_pages=normalized.total_pages,
                            execution_time_seconds=round(elapsed, 3),
                            metadata={"index_mode": "sqlite_fts5_only", "pretrained_embeddings_used": False,
                                      "has_ocr_content": has_ocr, "ocr_pages_count": len(ocr_pages),
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

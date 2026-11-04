"""
RAG Integration Client for FastAPI Backend.
Owned boundary contract between Abhay's Backend and Gorav's RAG Engine.
FastAPI route handlers should import and call this client without importing
internal RAG details directly.
"""

import logging
import threading
from typing import Callable
from typing import List, Optional, Dict, Any

from rag.pipelines.ingest_pipeline import IngestionPipeline, IngestResult
from rag.pipelines.query_pipeline import QueryPipeline
from rag.retrieval.query import QueryFilters
from rag.citations.citation_formatter import RAGResult
from rag.vectorstore.vector_repository import VectorRepository

logger = logging.getLogger(__name__)


class RAGClient:
    """
    High-level integration wrapper for the FastAPI backend service.
    Exposes clean synchronous and data-dictionary interfaces matching the API contract.
    """

    def __init__(
        self,
        ingest_pipeline: Optional[IngestionPipeline] = None,
        query_pipeline: Optional[QueryPipeline] = None,
        vector_repo: Optional[VectorRepository] = None,
    ):
        self._ingest_pipeline = ingest_pipeline or IngestionPipeline()
        self._query_pipeline = query_pipeline or QueryPipeline()
        self._vector_repo = vector_repo or VectorRepository()
        self._ingest_locks: dict[str, threading.Lock] = {}
        self._ingest_locks_guard = threading.Lock()
        self._active_ingests: dict[str, str] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    def ingest_document(
        self,
        file_path: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """
        Ingests a document file into the RAG vector store.

        Returns:
            dict: {
                "success": bool,
                "status": "indexed" | "failed",
                "document_id": str,
                "paper_id": str,
                "chunk_count": int,
                "total_pages": int,
                "error": str | None
            }
        """
        document_id = str((metadata or {}).get("document_id") or file_path)
        with self._ingest_locks_guard:
            lock = self._ingest_locks.setdefault(document_id, threading.Lock())
            if not lock.acquire(blocking=False):
                return {
                    "success": False,
                    "status": "failed",
                    "document_id": document_id,
                    "paper_id": paper_id or "unknown_paper",
                    "chunk_count": 0,
                    "total_pages": 0,
                    "error": "An earlier ingestion attempt for this source is still running. Wait briefly, then retry.",
                    "active_attempt": True,
                }
            self._active_ingests[document_id] = paper_id or ""
            if cancel_event is None:
                cancel_event = threading.Event()
            self._cancel_events[document_id] = cancel_event
        try:
            result: IngestResult = self._ingest_pipeline.ingest_file(
                file_path=file_path,
                paper_id=paper_id,
                metadata=metadata,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )
            if cancel_event is not None and cancel_event.is_set() and result.success:
                # Close the last race between the pipeline's final safe-boundary
                # check and a gateway timeout. The per-document lock remains held
                # until this cleanup completes, so an immediate retry cannot race it.
                try:
                    self._vector_repo.delete_document_chunks(document_id)
                    result = result.model_copy(update={
                        "success": False, "status": "failed", "chunk_count": 0,
                        "error": "Ingestion cancelled after the request timed out.",
                    })
                except Exception as cleanup_error:
                    result = result.model_copy(update={
                        "success": False, "status": "failed", "chunk_count": 0,
                        "error": "Ingestion cancelled after timeout; index cleanup failed: "
                                f"{type(cleanup_error).__name__}: {cleanup_error}",
                    })
            return result.model_dump()
        finally:
            with self._ingest_locks_guard:
                lock.release()
                self._active_ingests.pop(document_id, None)
                if self._ingest_locks.get(document_id) is lock:
                    self._ingest_locks.pop(document_id, None)

    def ingest_text_content(
        self,
        content: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ingests raw text or markdown research paper content.
        """
        result: IngestResult = self._ingest_pipeline.ingest_text(
            content=content,
            paper_id=paper_id,
            metadata=metadata,
        )
        return result.model_dump()

    def cancel_ingest(self, document_id: str) -> bool:
        """Signal cancellation for an active ingestion job."""
        with self._ingest_locks_guard:
            event = self._cancel_events.get(document_id)
            if event is not None:
                event.set()
                logger.info("Cancellation signalled for active ingestion document_id=%s", document_id)
                return True
            return False

    def ask_question(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        sections: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        user_id: Optional[str] = None,
        answer_mode: str = "DOCUMENTS_GENERAL",
    ) -> Dict[str, Any]:
        """
        Answers a question grounded in target papers.

        Matches API contract:
        {
            "answer": "...",
            "sources": [
                {
                    "source_id": "S1",
                    "paper_id": "paper_123",
                    "page": 4,
                    "page_start": 4,
                    "page_end": 4,
                    "section": "Methodology",
                    "text": "...",
                    "score": 0.85,
                    "title": "Paper Title"
                }
            ],
            "paper_ids": ["paper_123"]
        }
        """
        filters = QueryFilters(sections=sections) if sections else None
        result: RAGResult = self._query_pipeline.answer_question(
            question=question,
            paper_ids=paper_ids,
            filters=filters,
            top_k=top_k,
            conversation_context=conversation_context,
            progress_callback=progress_callback,
            user_id=user_id,
            answer_mode=answer_mode,
        )
        return result.to_api_dict()

    def summarize_paper(
        self,
        paper_id: str,
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """
        Produces a structured research paper summary.
        """
        result: RAGResult = self._query_pipeline.summarize_paper(
            paper_id=paper_id,
            top_k=top_k,
        )
        return result.to_api_dict()

    def compare_papers(
        self,
        paper_ids: List[str],
        focus_area: Optional[str] = None,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Generates comparative analysis across multiple research papers.
        """
        result: RAGResult = self._query_pipeline.compare_papers(
            paper_ids=paper_ids,
            focus_area=focus_area,
            top_k=top_k,
        )
        return result.to_api_dict()

    def delete_paper(self, paper_id: str) -> int:
        """
        Removes all indexed vectors for a paper.
        """
        with self._ingest_locks_guard:
            if paper_id in self._active_ingests.values():
                raise RuntimeError("Cannot delete a paper while one of its sources is being indexed.")
        return self._ingest_pipeline.delete_paper(paper_id)

    def delete_document_chunks(self, document_id: str) -> int:
        """Remove a document's records from the active vector and lexical indexes."""
        with self._ingest_locks_guard:
            if document_id in self._active_ingests:
                raise RuntimeError("Cannot delete source chunks while its ingestion is still active.")
        return self._vector_repo.delete_document_chunks(document_id)

    def get_document_index_counts(self, document_id: str) -> Dict[str, Any]:
        """Return verifiable active-collection counts for both backing indexes."""
        return self._vector_repo.document_index_counts(document_id)

    def health_check(self) -> Dict[str, Any]:
        """
        Returns status of vector storage and pipeline readiness.
        """
        try:
            count = self._vector_repo.count_chunks()
            return {
                "status": "healthy",
                "total_indexed_chunks": count,
                "vectorstore": "chromadb",
            }
        except Exception:
            return {
                "status": "unhealthy",
                "error": "RAG storage is unavailable.",
            }


# Default singleton instance for quick import by backend routes
rag_client = RAGClient()

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
from rag.config.settings import settings

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
        # Keep model-backed ingestion lazy so an independent-mode API process
        # can answer from SQLite FTS5 without constructing FastEmbedder.
        self._ingest_pipeline = ingest_pipeline
        self._query_pipeline = query_pipeline or QueryPipeline()
        self._vector_repo = vector_repo or VectorRepository()
        self._ingest_locks: dict[str, threading.Lock] = {}
        self._ingest_locks_guard = threading.Lock()
        self._active_ingests: dict[str, str] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    @property
    def _ingest(self) -> Any:
        if self._ingest_pipeline is None:
            if settings.rag_engine_mode == "independent":
                from rag.independent.ingest_pipeline import IndependentIngestionPipeline
                self._ingest_pipeline = IndependentIngestionPipeline()
            else:
                self._ingest_pipeline = IngestionPipeline()
        return self._ingest_pipeline

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
            result: IngestResult = self._ingest.ingest_file(
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
        result: IngestResult = self._ingest.ingest_text(
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
        user_id: str,  # SEC-001: Made REQUIRED
        paper_ids: Optional[List[str]] = None,
        sections: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "EVIDENCE_FIRST",
        paper_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Answers a question grounded in target papers.
        
        Args:
            question: Research question to answer
            user_id: REQUIRED - User ID for multi-tenant isolation (SEC-001)
            paper_ids: Optional paper IDs to search within user's scope
            sections: Optional sections to filter
            top_k: Number of sources to retrieve
            conversation_context: Optional conversation history
            progress_callback: Optional callback for progress updates
            answer_mode: Answer generation mode
            
        Returns:
            Dict with answer, sources, and paper_ids
            
        Raises:
            ValueError: If user_id is not provided

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
        if not user_id:
            raise ValueError("user_id is required for secure query execution (SEC-001 compliance)")
            
        filters = QueryFilters(sections=sections) if sections else None
        result: RAGResult = self._query_pipeline.answer_question(
            question=question,
            user_id=user_id,  # SEC-001: Pass as required positional arg
            paper_ids=paper_ids,
            filters=filters,
            top_k=top_k,
            conversation_context=conversation_context,
            progress_callback=progress_callback,
            answer_mode=answer_mode,
            paper_metadata=paper_metadata,
        )
        return result.to_api_dict()

    def summarize_paper(
        self,
        paper_id: str,
        user_id: str,  # SEC-001: Add required user_id
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """
        Produces a structured research paper summary.
        
        Args:
            paper_id: Paper ID to summarize
            user_id: REQUIRED - User ID for multi-tenant isolation (SEC-001)
            top_k: Number of sources to retrieve
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is required (SEC-001 compliance)")
            
        result: RAGResult = self._query_pipeline.summarize_paper(
            paper_id=paper_id,
            user_id=user_id,  # SEC-001: Pass user_id
            top_k=top_k,
        )
        return result.to_api_dict()

    def compare_papers(
        self,
        paper_ids: Optional[List[str]],
        user_id: str,  # SEC-001: Add required user_id
        focus_area: Optional[str] = None,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None,
        output_format: str = "table",
        document_labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates comparative analysis across multiple research papers.
        
        Args:
            paper_ids: Paper IDs to compare
            user_id: REQUIRED - User ID for multi-tenant isolation (SEC-001)
            focus_area: Optional focus for comparison
            top_k: Number of sources to retrieve
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is required (SEC-001 compliance)")
            
        result: RAGResult = self._query_pipeline.compare_papers(
            paper_ids=paper_ids,
            document_ids=document_ids,
            user_id=user_id,  # SEC-001: Pass user_id
            focus_area=focus_area,
            top_k=top_k,
            output_format=output_format,
            document_labels=document_labels,
        )
        return result.to_api_dict()

    def delete_paper(self, paper_id: str) -> int:
        """
        Removes all indexed vectors for a paper.
        """
        with self._ingest_locks_guard:
            if paper_id in self._active_ingests.values():
                raise RuntimeError("Cannot delete a paper while one of its sources is being indexed.")
        count = self._ingest.delete_paper(paper_id)
        if settings.rag_engine_mode == "independent":
            count = max(count, self._vector_repo.delete_paper_chunks(paper_id))
        return count

    def delete_document_chunks(self, document_id: str) -> int:
        """Remove a document's records from the active vector and lexical indexes."""
        with self._ingest_locks_guard:
            if document_id in self._active_ingests:
                raise RuntimeError("Cannot delete source chunks while its ingestion is still active.")
        return self._vector_repo.delete_document_chunks(document_id)

    def get_document_index_counts(self, document_id: str) -> Dict[str, Any]:
        """Return verifiable active-collection counts for both backing indexes."""
        if settings.rag_engine_mode == "independent":
            from rag.independent.index_writer import IndependentIndexWriter
            counts = IndependentIndexWriter().count_document(document_id)
            return {
                **counts,
                "collection_name": IndependentIndexWriter().collection_name,
                "storage_mode": "sqlite_fts5_only",
                "chroma_count": 0,
                "fts_count": counts["lexical_count"],
                "unique_fts_count": counts["lexical_unique_count"],
                "ids_match": counts["lexical_count"] == counts["lexical_unique_count"],
            }
        return self._vector_repo.document_index_counts(document_id)

    def health_check(self) -> Dict[str, Any]:
        """
        Returns status of vector storage and pipeline readiness.
        """
        try:
            if settings.rag_engine_mode == "independent":
                from rag.independent.index_writer import IndependentIndexWriter
                count = IndependentIndexWriter().count_all()
                return {"status": "healthy", "total_indexed_chunks": count,
                        "vectorstore": "sqlite_fts5", "pretrained_embeddings_used": False}
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

"""Async adapter over the synchronous in-process RAG client (Gorav's boundary,
`rag_client.py`).

Backend services talk to RAG only through this gateway: it runs the
synchronous pipeline off the event loop, applies the configured timeout and
maps failures onto the API error contract. It never inspects RAG internals.
"""

import asyncio
import logging
import threading
from typing import Callable
from typing import Any, Optional

from backend.app.core.config import get_settings
from backend.app.core.exceptions import RAGIngestionTimeoutError, RAGUnavailableError

logger = logging.getLogger("backend.rag")


def _gemini_configuration_error(exc: Exception) -> Optional[str]:
    message = str(exc)
    if ("GEMINI_API_KEY" in message or "Gemini" in message
            or "Unsupported LLM provider" in message
            or "No generation provider" in message):
        return message
    return None


class RAGGateway:
    def __init__(self, client: Any = None, timeout_seconds: Optional[float] = None):
        self._client = client
        self._timeout_override = timeout_seconds

    @property
    def _timeout(self) -> float:
        if self._timeout_override is not None:
            return self._timeout_override
        return get_settings().rag_timeout_seconds

    def _get_client(self) -> Any:
        if self._client is None:
            # Imported lazily: this pulls in the RAG dependency chain
            # (ChromaDB, embedders, ...), which the backend should only pay
            # for when RAG is actually used.
            from backend.app.integrations.rag_client import rag_client

            self._client = rag_client
        return self._client

    async def _call(
        self, method_name: str, /, *args: Any, timeout_seconds: Optional[float] = None,
        cooperative_cancel: bool = False, **kwargs: Any,
    ) -> Any:
        try:
            client = self._get_client()
        except Exception as exc:
            logger.error("RAG client unavailable exception_type=%s", type(exc).__name__)
            if (message := _gemini_configuration_error(exc)):
                raise RAGUnavailableError(message) from exc
            raise RAGUnavailableError() from exc
        method = getattr(client, method_name)
        timeout = timeout_seconds or self._timeout
        cancel_event = threading.Event() if cooperative_cancel else None
        if cancel_event is not None:
            kwargs["cancel_event"] = cancel_event
        try:
            if cancel_event is None:
                return await asyncio.wait_for(asyncio.to_thread(method, *args, **kwargs), timeout=timeout)
            worker = asyncio.create_task(asyncio.to_thread(method, *args, **kwargs))
            try:
                done, _ = await asyncio.wait({worker}, timeout=timeout)
            except asyncio.CancelledError:
                cancel_event.set()
                worker.add_done_callback(self._observe_worker_result)
                raise
            if worker in done:
                return worker.result()
            # wait_for() around to_thread() cancels only the awaitable. Keep the
            # worker and RAGClient's per-document lock alive while it cooperatively
            # stops and cleans up at a safe pipeline boundary.
            cancel_event.set()
            worker.add_done_callback(self._observe_worker_result)
            raise asyncio.TimeoutError
        except asyncio.TimeoutError as exc:
            logger.error(
                "RAG call timed out method=%s timeout_seconds=%s cooperative_cancel=%s",
                method_name, timeout, cooperative_cancel,
            )
            message = "The RAG service timed out."
            if cooperative_cancel:
                message += " Cancellation was requested; a same-document retry remains locked until cleanup finishes."
            if cooperative_cancel:
                raise RAGIngestionTimeoutError(message) from exc
            raise RAGUnavailableError(message) from exc
        except RAGUnavailableError:
            raise
        except Exception as exc:
            logger.error("RAG query failed method=%s exception_type=%s", method_name, type(exc).__name__)
            if (message := _gemini_configuration_error(exc)):
                raise RAGUnavailableError(message) from exc
            raise RAGUnavailableError() from exc

    @staticmethod
    def _observe_worker_result(worker: asyncio.Task) -> None:
        """Retrieve background worker exceptions after the HTTP call timed out."""
        if not worker.cancelled():
            try:
                worker.exception()
            except Exception:
                logger.exception("Timed-out RAG worker raised after request completion")

    async def ingest_document(
        self,
        file_path: str,
        paper_id: str,
        metadata: Optional[dict[str, Any]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[Any] = None,  # Milestone 1: Accept cancellation event
    ) -> dict[str, Any]:
        return await self._call(
            "ingest_document", file_path=file_path, paper_id=paper_id, metadata=metadata,
            **({"progress_callback": progress_callback} if progress_callback else {}),
            **({"cancel_event": cancel_event} if cancel_event else {}),
            cooperative_cancel=True,
            timeout_seconds=get_settings().rag_ingest_timeout_seconds,
        )

    async def cancel_ingest(self, document_id: str) -> bool:
        return await self._call("cancel_ingest", document_id)

    async def ask_question(
        self,
        question: str,
        user_id: str,  # SEC-001: Made REQUIRED
        paper_ids: Optional[list[str]] = None,
        document_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "EVIDENCE_FIRST",
        paper_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute a query grounded in indexed papers.
        
        Args:
            question: Research question to answer
            user_id: REQUIRED - User ID for multi-tenant isolation (SEC-001)
            paper_ids: Optional paper IDs to search within user's scope
            document_ids: Optional document IDs to search within user's scope
            top_k: Number of sources to retrieve
            conversation_context: Optional conversation history
            progress_callback: Optional callback for progress updates
            answer_mode: Answer generation mode
            
        Returns:
            Dict with answer, sources, and paper_ids
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is required for secure query execution (SEC-001 compliance)")
            
        return await self._call(
            "ask_question",
            question=question,
            user_id=user_id,  # SEC-001: Always pass user_id (no longer conditional)
            paper_ids=paper_ids,
            top_k=top_k,
            answer_mode=answer_mode,
            paper_metadata=paper_metadata,
            **({"document_ids": document_ids} if document_ids else {}),
            **({"conversation_context": conversation_context} if conversation_context else {}),
            **({"progress_callback": progress_callback} if progress_callback else {}),
        )

    async def summarize_paper(self, paper_id: str, user_id: str, top_k: int = 8) -> dict[str, Any]:
        """
        Summarize a research paper.
        
        Args:
            paper_id: Paper ID to summarize
            user_id: REQUIRED - User ID for multi-tenant isolation (SEC-001)
            top_k: Number of sources to retrieve
            
        Raises:
            ValueError: If user_id is not provided
        """
        if not user_id:
            raise ValueError("user_id is required (SEC-001 compliance)")
            
        return await self._call("summarize_paper", paper_id=paper_id, user_id=user_id, top_k=top_k)

    async def compare_papers(
        self,
        paper_ids: list[str] | None,
        user_id: str,  # SEC-001: Add required user_id
        focus_area: Optional[str] = None,
        top_k: int = 10,
        document_ids: list[str] | None = None,
        output_format: str = "table",
        document_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Compare multiple research papers.
        
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
            
        return await self._call(
            "compare_papers", paper_ids=paper_ids, document_ids=document_ids,
            output_format=output_format, document_labels=document_labels,
            user_id=user_id, focus_area=focus_area, top_k=top_k
        )

    async def delete_paper(self, paper_id: str) -> int:
        return await self._call("delete_paper", paper_id)

    async def delete_document_chunks(self, document_id: str) -> int:
        return await self._call("delete_document_chunks", document_id)

    async def get_document_index_counts(self, document_id: str) -> dict[str, Any]:
        return await self._call("get_document_index_counts", document_id)

    async def get_document_index_status(self, document_id: str) -> dict[str, Any]:
        return await self._call("get_document_index_status", document_id)

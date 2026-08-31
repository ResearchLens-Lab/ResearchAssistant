"""Async adapter over the synchronous in-process RAG client (Gorav's boundary,
`rag_client.py`).

Backend services talk to RAG only through this gateway: it runs the
synchronous pipeline off the event loop, applies the configured timeout and
maps failures onto the API error contract. It never inspects RAG internals.
"""

import asyncio
import logging
from typing import Any, Optional

from backend.app.core.config import get_settings
from backend.app.core.exceptions import RAGUnavailableError

logger = logging.getLogger("backend.rag")


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

    async def _call(self, method_name: str, /, *args: Any, **kwargs: Any) -> Any:
        try:
            client = self._get_client()
        except Exception as exc:
            logger.error("RAG client unavailable: %s", exc)
            raise RAGUnavailableError() from exc
        method = getattr(client, method_name)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(method, *args, **kwargs), timeout=self._timeout
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "RAG query failed: '%s' timed out after %ss", method_name, self._timeout
            )
            raise RAGUnavailableError("The RAG service timed out.") from exc
        except RAGUnavailableError:
            raise
        except Exception as exc:
            logger.error("RAG query failed: '%s' raised %s", method_name, exc)
            raise RAGUnavailableError() from exc

    async def ingest_document(
        self,
        file_path: str,
        paper_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return await self._call(
            "ingest_document", file_path=file_path, paper_id=paper_id, metadata=metadata
        )

    async def ask_question(
        self,
        question: str,
        paper_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> dict[str, Any]:
        return await self._call(
            "ask_question", question=question, paper_ids=paper_ids, top_k=top_k
        )

    async def summarize_paper(self, paper_id: str, top_k: int = 8) -> dict[str, Any]:
        return await self._call("summarize_paper", paper_id=paper_id, top_k=top_k)

    async def compare_papers(
        self,
        paper_ids: list[str],
        focus_area: Optional[str] = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        return await self._call(
            "compare_papers", paper_ids=paper_ids, focus_area=focus_area, top_k=top_k
        )

    async def delete_paper(self, paper_id: str) -> int:
        return await self._call("delete_paper", paper_id)

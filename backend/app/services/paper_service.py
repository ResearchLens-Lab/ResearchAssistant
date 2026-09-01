# Deferred annotations: the `list` method below must not shadow builtin
# `list` in signature annotations.
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import PaperNotFoundError, RAGUnavailableError
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.schemas.paper import PaperCompareRequest, PaperCreate, PaperUpdate
from backend.app.utils.pagination import PageParams, page_payload

logger = logging.getLogger("backend.papers")


class PaperService:
    def __init__(self, db: AsyncSession, rag: Optional[RAGGateway] = None):
        self.db = db
        self.papers = PaperRepository(db)
        self.rag = rag

    async def create(self, user: User, payload: PaperCreate) -> Paper:
        paper = await self.papers.create(owner_id=user.id, data=payload.model_dump())
        await self.db.commit()
        logger.info("paper created paper_id=%s user_id=%s", paper.id, user.id)
        return paper

    async def get_owned(self, user: User, paper_id: str) -> Paper:
        """Ownership is enforced on every paper lookup; papers belonging to
        other users are indistinguishable from missing ones (no UUID probing)."""
        paper = await self.papers.get_by_id(paper_id)
        if paper is None or paper.owner_id != user.id:
            raise PaperNotFoundError()
        return paper

    async def list(self, user: User, params: PageParams) -> dict[str, Any]:
        items, total = await self.papers.list_by_owner(
            user.id, params.offset, params.page_size
        )
        return page_payload(items, total, params)

    async def search(
        self,
        user: User,
        q: Optional[str],
        author: Optional[str],
        year: Optional[int],
        params: PageParams,
    ) -> dict[str, Any]:
        items, total = await self.papers.search(
            user.id, q, author, year, params.offset, params.page_size
        )
        return page_payload(items, total, params)

    async def update(self, user: User, paper_id: str, payload: PaperUpdate) -> Paper:
        paper = await self.get_owned(user, paper_id)
        paper = await self.papers.update(paper, payload.model_dump(exclude_unset=True))
        await self.db.commit()
        return paper

    async def delete(self, user: User, paper_id: str) -> None:
        paper = await self.get_owned(user, paper_id)
        documents = await DocumentRepository(self.db).list_by_paper(paper.id)
        storage_paths = [doc.storage_path for doc in documents if doc.storage_path]
        await self.papers.delete(paper)
        await self.db.commit()

        # Best-effort cleanup outside the transaction: stored files and
        # indexed vectors. Failures are logged, never surfaced.
        for path in storage_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                logger.warning("could not remove stored file path=%s", path)
        if self.rag is not None:
            try:
                await self.rag.delete_paper(paper_id)
            except RAGUnavailableError:
                logger.warning("RAG vector cleanup failed paper_id=%s", paper_id)

    async def validate_owned_papers(
        self, user: User, paper_ids: list[str]
    ) -> list[Paper]:
        return [
            await self.get_owned(user, paper_id)
            for paper_id in dict.fromkeys(paper_ids)
        ]

    async def summarize(self, user: User, paper_id: str) -> dict[str, Any]:
        await self.get_owned(user, paper_id)
        result = await self.rag.summarize_paper(paper_id)
        return {
            "paper_id": paper_id,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
        }

    async def compare(self, user: User, payload: PaperCompareRequest) -> dict[str, Any]:
        papers = await self.validate_owned_papers(user, payload.paper_ids)
        paper_ids = [paper.id for paper in papers]
        result = await self.rag.compare_papers(paper_ids, focus_area=payload.focus_area)
        return {
            "paper_ids": paper_ids,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
        }

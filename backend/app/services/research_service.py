"""Thin pass-through to the knowledge-graph boundary (Harendra's domain).
The backend validates access and forwards; graph internals never live here."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.integrations.knowledge_graph_client import KnowledgeGraphClient
from backend.app.models.user import User
from backend.app.services.paper_service import PaperService


class ResearchService:
    def __init__(self, db: AsyncSession, graph: KnowledgeGraphClient):
        self.db = db
        self.graph = graph

    async def get_paper_graph(self, user: User, paper_id: str) -> dict[str, Any]:
        await PaperService(self.db).get_owned(user, paper_id)
        return await self.graph.get_paper_graph(paper_id)

    async def get_related_papers(self, user: User, paper_id: str) -> list[dict[str, Any]]:
        await PaperService(self.db).get_owned(user, paper_id)
        return await self.graph.get_related_papers(paper_id)

    async def get_research_trends(self, user: User) -> dict[str, Any]:
        return await self.graph.get_research_trends()

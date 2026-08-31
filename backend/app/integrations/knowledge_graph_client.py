"""Knowledge-graph integration boundary (implementation owned by Harendra).

The backend defines only the interface — no Neo4j internals belong here.
Until the knowledge-graph service is wired in, every operation reports the
boundary as unavailable through the shared error contract (503)."""

from typing import Any

from backend.app.core.exceptions import KnowledgeGraphUnavailableError


class KnowledgeGraphClient:
    async def get_paper_graph(self, paper_id: str) -> dict[str, Any]:
        raise KnowledgeGraphUnavailableError()

    async def get_related_papers(self, paper_id: str) -> list[dict[str, Any]]:
        raise KnowledgeGraphUnavailableError()

    async def get_citation_network(self, paper_id: str) -> dict[str, Any]:
        raise KnowledgeGraphUnavailableError()

    async def get_research_trends(self) -> dict[str, Any]:
        raise KnowledgeGraphUnavailableError()


knowledge_graph_client = KnowledgeGraphClient()

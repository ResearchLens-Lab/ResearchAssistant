"""Research-intelligence endpoints — the integration boundary for the
knowledge graph (Harendra). They validate access and forward to the graph
client; until that service is integrated they answer 503
KNOWLEDGE_GRAPH_UNAVAILABLE."""

from fastapi import APIRouter

from backend.app.core.dependencies import CurrentUser, DBSession, KnowledgeGraphDep
from backend.app.schemas.research import (
    PaperGraphResponse,
    RelatedPapersResponse,
    ResearchTrendsResponse,
)
from backend.app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


@router.get(
    "/papers/{paper_id}/graph",
    response_model=PaperGraphResponse,
    summary="Citation/entity graph for a paper (knowledge-graph boundary)",
)
async def get_paper_graph(
    paper_id: str, current_user: CurrentUser, db: DBSession, graph: KnowledgeGraphDep
):
    return await ResearchService(db, graph).get_paper_graph(current_user, paper_id)


@router.get(
    "/papers/{paper_id}/related",
    response_model=RelatedPapersResponse,
    summary="Related papers (knowledge-graph boundary)",
)
async def get_related_papers(
    paper_id: str, current_user: CurrentUser, db: DBSession, graph: KnowledgeGraphDep
):
    related = await ResearchService(db, graph).get_related_papers(current_user, paper_id)
    return {"paper_id": paper_id, "related": related}


@router.get(
    "/trends",
    response_model=ResearchTrendsResponse,
    summary="Research trends (knowledge-graph boundary)",
)
async def get_research_trends(
    current_user: CurrentUser, db: DBSession, graph: KnowledgeGraphDep
):
    return await ResearchService(db, graph).get_research_trends(current_user)

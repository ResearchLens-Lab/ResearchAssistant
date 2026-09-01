from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.schemas.common import Page
from backend.app.schemas.paper import PaperResponse
from backend.app.services.paper_service import PaperService
from backend.app.utils.pagination import PageParams

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=Page[PaperResponse],
    summary="Metadata search over own papers",
    description=(
        "Database/metadata search (title, abstract, author, year). "
        "Semantic/vector retrieval belongs to the RAG boundary, not here."
    ),
)
async def search_papers(
    current_user: CurrentUser,
    db: DBSession,
    q: Optional[str] = Query(None, description="Free-text match on title/abstract"),
    author: Optional[str] = Query(None, description="Author name substring"),
    year: Optional[int] = Query(None, ge=1000, le=2100, description="Publication year"),
    params: PageParams = Depends(),
):
    return await PaperService(db).search(current_user, q, author, year, params)

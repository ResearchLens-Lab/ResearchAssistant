from fastapi import APIRouter, Depends, status

from backend.app.core.dependencies import CurrentUser, DBSession, RAGGatewayDep
from backend.app.schemas.common import Page
from backend.app.schemas.document import DocumentResponse
from backend.app.schemas.paper import (
    PaperCompareRequest,
    PaperCompareResponse,
    PaperCreate,
    PaperResponse,
    PaperSummaryResponse,
    PaperUpdate,
)
from backend.app.services.document_service import DocumentService
from backend.app.services.paper_service import PaperService
from backend.app.services.source_verification import SourceVerificationService
from backend.app.utils.pagination import PageParams

router = APIRouter(prefix="/papers", tags=["papers"])


@router.post(
    "",
    response_model=PaperResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a paper",
)
async def create_paper(payload: PaperCreate, current_user: CurrentUser, db: DBSession):
    return await PaperService(db).create(current_user, payload)


@router.get("", response_model=Page[PaperResponse], summary="List own papers")
async def list_papers(
    current_user: CurrentUser, db: DBSession, params: PageParams = Depends()
):
    return await PaperService(db).list(current_user, params)


@router.post(
    "/compare",
    response_model=PaperCompareResponse,
    summary="Compare papers via the RAG boundary",
)
async def compare_papers(
    payload: PaperCompareRequest,
    current_user: CurrentUser,
    db: DBSession,
    rag: RAGGatewayDep,
):
    return await PaperService(db, rag).compare(current_user, payload)


@router.get(
    "/compare/history",
    summary="List past comparative analyses for the current user",
)
async def list_comparison_history(
    current_user: CurrentUser,
    db: DBSession,
):
    return await PaperService(db).list_comparison_history(current_user)


@router.get(
    "/compare/history/{comparison_id}",
    summary="Get a past comparison by ID",
)
async def get_comparison_history(
    comparison_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    return await PaperService(db).get_comparison_history(current_user, comparison_id)



@router.get("/{paper_id}", response_model=PaperResponse, summary="Get a paper")
async def get_paper(paper_id: str, current_user: CurrentUser, db: DBSession):
    return await PaperService(db).get_owned(current_user, paper_id)


@router.post("/{paper_id}/verify-source", summary="Explicitly verify stored bibliographic metadata by DOI")
async def verify_paper_source(paper_id: str, current_user: CurrentUser, db: DBSession):
    paper = await PaperService(db).get_owned(current_user, paper_id)
    return await SourceVerificationService().verify(paper)


@router.patch("/{paper_id}", response_model=PaperResponse, summary="Update a paper")
async def update_paper(
    paper_id: str, payload: PaperUpdate, current_user: CurrentUser, db: DBSession
):
    return await PaperService(db).update(current_user, paper_id, payload)


@router.delete(
    "/{paper_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a paper (documents and indexed vectors included)",
)
async def delete_paper(
    paper_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    await PaperService(db, rag).delete(current_user, paper_id)


@router.post(
    "/{paper_id}/summary",
    response_model=PaperSummaryResponse,
    summary="Grounded summary via the RAG boundary",
)
async def summarize_paper(
    paper_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    return await PaperService(db, rag).summarize(current_user, paper_id)


@router.get(
    "/{paper_id}/documents",
    response_model=list[DocumentResponse],
    summary="List documents uploaded for a paper",
)
async def list_paper_documents(
    paper_id: str, current_user: CurrentUser, db: DBSession
):
    return await DocumentService(db).list_for_paper(current_user, paper_id)


@router.post(
    "/{paper_id}/open-folder",
    summary="Open this project's local directory in Explorer",
)
async def open_project_folder(
    paper_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    return await PaperService(db, rag).open_folder(current_user, paper_id)


@router.post(
    "/{paper_id}/sync-folder",
    summary="Sync new files from this project's local directory (single-user desktop mode only)",
)
async def sync_project_folder(
    paper_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    return await PaperService(db, rag).sync_folder(current_user, paper_id)


@router.post(
    "/{paper_id}/export-summary",
    summary="Export grounded summary and citations audit trail to project folder",
)
async def export_paper_summary(
    paper_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    return await PaperService(db, rag).export_summary(current_user, paper_id)

from fastapi import APIRouter, File, Form, UploadFile, status

from backend.app.core.dependencies import CurrentUser, DBSession, RAGGatewayDep
from backend.app.schemas.document import DocumentResponse
from backend.app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a research-paper PDF and index it via the RAG boundary",
    description=(
        "Accepts multipart/form-data with a `file` (PDF) and the `paper_id` it "
        "belongs to. The document record tracks processing status: "
        "uploaded → processing → indexed/failed."
    ),
)
async def upload_document(
    current_user: CurrentUser,
    db: DBSession,
    rag: RAGGatewayDep,
    file: UploadFile = File(..., description="Research paper PDF"),
    paper_id: str = Form(..., description="Paper this document belongs to"),
):
    return await DocumentService(db, rag).upload(current_user, paper_id, file)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata and processing status",
)
async def get_document(document_id: str, current_user: CurrentUser, db: DBSession):
    return await DocumentService(db).get_owned(current_user, document_id)

import mimetypes
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.core.dependencies import CurrentUser, DBSession, RAGGatewayDep
from backend.app.schemas.document import DocumentResponse, PaperDocumentsRequest
from backend.app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a supported source document and index it via the RAG boundary",
    description=(
        "Accepts multipart/form-data with a `file` and the `paper_id` it "
        "belongs to. The document record tracks processing status: "
        "uploaded → processing → indexed/failed."
    ),
)
async def upload_document(
    current_user: CurrentUser,
    db: DBSession,
    rag: RAGGatewayDep,
    file: UploadFile = File(..., description="Supported research source document, up to 100 MB"),
    paper_id: str = Form(..., description="Paper this document belongs to"),
):
    return await DocumentService(db, rag).upload(current_user, paper_id, file)


@router.post("/upload/batch", status_code=status.HTTP_201_CREATED, summary="Upload multiple supported documents or ZIP archives into one project (500 MB total batch limit)")
async def upload_documents_batch(
    current_user: CurrentUser,
    db: DBSession,
    rag: RAGGatewayDep,
    files: list[UploadFile] = File(...),
    paper_id: str = Form(...),
):
    return await DocumentService(db, rag).upload_batch(current_user, paper_id, files)


@router.post("/by-papers", response_model=dict[str, list[DocumentResponse]], summary="List documents for multiple owned projects")
async def list_documents_by_papers(
    payload: PaperDocumentsRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    return await DocumentService(db).list_for_papers(current_user, payload.paper_ids)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata and processing status",
)
async def get_document(document_id: str, current_user: CurrentUser, db: DBSession):
    return await DocumentService(db).get_owned(current_user, document_id)


@router.post("/{document_id}/cancel", response_model=DocumentResponse, summary="Cancel an active document ingestion")
async def cancel_document(document_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep):
    return await DocumentService(db, rag).cancel(current_user, document_id)


@router.post("/{document_id}/retry", response_model=DocumentResponse, summary="Retry a failed source or re-index an existing source using its stored original file")
async def retry_document(document_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep):
    return await DocumentService(db, rag).retry(current_user, document_id)


@router.post("/{document_id}/reindex", response_model=DocumentResponse, summary="Re-index an existing document with the latest section-aware research engine")
async def reindex_document(document_id: str, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep):
    return await DocumentService(db, rag).reindex(current_user, document_id)


@router.get("/{document_id}/file", summary="Download an owned source document")
async def get_document_file(document_id: str, current_user: CurrentUser, db: DBSession):
    document = await DocumentService(db).get_owned(current_user, document_id)
    path = Path(document.storage_path).resolve()
    if not path.is_file():
        from backend.app.core.exceptions import DocumentNotFoundError
        raise DocumentNotFoundError()
    media_type = mimetypes.guess_type(document.filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=Path(document.filename).name)

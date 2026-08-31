import logging
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    DocumentNotFoundError,
    PaperNotFoundError,
    RAGUnavailableError,
)
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.services.paper_service import PaperService
from backend.app.utils.validators import validate_pdf_upload

logger = logging.getLogger("backend.documents")


class DocumentService:
    def __init__(self, db: AsyncSession, rag: Optional[RAGGateway] = None):
        self.db = db
        self.documents = DocumentRepository(db)
        self.paper_service = PaperService(db)
        self.rag = rag

    async def upload(self, user: User, paper_id: str, upload: UploadFile) -> Document:
        settings = get_settings()
        paper = await self.paper_service.get_owned(user, paper_id)

        content = await upload.read()
        validate_pdf_upload(
            upload.filename, upload.content_type, content, settings.max_upload_size_bytes
        )

        document = await self.documents.create(
            paper_id=paper.id,
            filename=upload.filename or "document.pdf",
            storage_path="",
            content_type=upload.content_type or "application/pdf",
            file_size=len(content),
        )
        # Files are stored under a generated id — user filenames never become
        # filesystem paths (no traversal).
        upload_dir = settings.upload_path
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path = upload_dir / f"{document.id}.pdf"
        storage_path.write_bytes(content)
        document.storage_path = str(storage_path)
        document.processing_status = DocumentStatus.PROCESSING.value
        await self.db.flush()
        await self.db.commit()
        logger.info("document uploaded document_id=%s paper_id=%s", document.id, paper.id)

        await self._process(document, paper)
        return document

    async def _process(self, document: Document, paper: Paper) -> None:
        """Synchronous RAG ingestion, acceptable for the prototype; the status
        model (uploaded → processing → indexed/failed) already supports moving
        this to a background worker later."""
        logger.info("RAG ingestion started document_id=%s", document.id)
        metadata = {
            "document_id": document.id,  # shared ID passed through to RAG/ChromaDB
            "title": paper.title,
            "authors": ", ".join(paper.authors or []),
            "year": paper.publication_year,
        }
        try:
            result = await self.rag.ingest_document(
                file_path=document.storage_path,
                paper_id=document.paper_id,
                metadata=metadata,
            )
        except RAGUnavailableError as exc:
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_error = exc.message
            await self.db.commit()
            logger.warning(
                "RAG ingestion failed document_id=%s error=%s", document.id, exc.message
            )
            return

        if result.get("success") and result.get("status") == "indexed":
            document.processing_status = DocumentStatus.INDEXED.value
            document.chunk_count = result.get("chunk_count")
            document.processing_error = None
        else:
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_error = result.get("error") or "Document ingestion failed."
        await self.db.commit()
        logger.info(
            "RAG ingestion completed document_id=%s status=%s",
            document.id,
            document.processing_status,
        )

    async def get_owned(self, user: User, document_id: str) -> Document:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()
        try:
            await self.paper_service.get_owned(user, document.paper_id)
        except PaperNotFoundError as exc:
            raise DocumentNotFoundError() from exc
        return document

    async def list_for_paper(self, user: User, paper_id: str) -> list[Document]:
        await self.paper_service.get_owned(user, paper_id)
        return await self.documents.list_by_paper(paper_id)

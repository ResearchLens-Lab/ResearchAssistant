import logging
import io
import zipfile
import stat
from pathlib import PurePosixPath
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    DocumentNotFoundError,
    PaperNotFoundError,
    RAGUnavailableError,
    RequestValidationAppError,
)
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.services.paper_service import PaperService
from backend.app.utils.validators import validate_document_upload

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
        validate_document_upload(
            upload.filename, upload.content_type, content, settings.max_upload_size_bytes
        )

        document = await self.documents.create(
            paper_id=paper.id,
            filename=upload.filename or "document.txt",
            storage_path="",
            content_type=upload.content_type or "application/octet-stream",
            file_size=len(content),
        )
        # Files are stored under a generated id — user filenames never become
        # filesystem paths (no traversal).
        upload_dir = settings.upload_path
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = __import__("pathlib").Path(document.filename).suffix.lower()
        storage_path = upload_dir / f"{document.id}{suffix}"
        storage_path.write_bytes(content)
        document.storage_path = str(storage_path)
        document.processing_status = DocumentStatus.PROCESSING.value
        await self.db.flush()
        await self.db.commit()
        logger.info("document uploaded document_id=%s paper_id=%s", document.id, paper.id)

        await self._process(document, paper)
        return document

    async def upload_batch(self, user: User, paper_id: str, uploads: list[UploadFile]) -> dict:
        """Upload documents and bounded ZIP members into one existing paper."""
        if len(uploads) > 100:
            return {"documents": [], "failures": [{"error": "At most 100 files may be uploaded per batch."}], "success_count": 0, "failure_count": 1}
        results, failures = [], []
        total_upload_size = 0
        for upload in uploads:
            if (upload.filename or "").lower().endswith(".zip"):
                raw = await upload.read()
                total_upload_size += len(raw)
                if total_upload_size > 100 * 1024 * 1024:
                    failures.append({"filename": upload.filename, "error": "Batch exceeds 100 MB total upload size."})
                    continue
                if len(raw) > get_settings().max_upload_size_bytes:
                    failures.append({"filename": upload.filename, "error": "Archive exceeds upload size limit."})
                    continue
                try:
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        members = [m for m in archive.infolist() if not m.is_dir()]
                        if len(members) > 100:
                            raise ValueError("Archive contains more than 100 files.")
                        total = 0
                        for member in members:
                            name = member.filename.replace("\\", "/")
                            path = PurePosixPath(name)
                            mode = member.external_attr >> 16
                            kind = stat.S_IFMT(mode)
                            if path.is_absolute() or (path.parts and ":" in path.parts[0]) or ".." in path.parts or stat.S_ISLNK(mode) or (kind not in (0, stat.S_IFREG)):
                                failures.append({"filename": upload.filename, "member": name, "error": "Unsafe archive member path or type."})
                                continue
                            total += member.file_size
                            if total > 100 * 1024 * 1024 or (member.compress_size and member.file_size / member.compress_size > 200):
                                raise ValueError("Archive expanded size or compression ratio exceeds safety limits.")
                            data = archive.read(member)
                            member_upload = UploadFile(filename=path.as_posix(), file=io.BytesIO(data), headers=upload.headers)
                            try:
                                results.append(await self.upload(user, paper_id, member_upload))
                            except Exception as exc:
                                message = exc.message if isinstance(exc, RequestValidationAppError) else "Member could not be stored or indexed."
                                failures.append({"filename": upload.filename, "member": path.as_posix(), "error": message})
                except (zipfile.BadZipFile, ValueError) as exc:
                    failures.append({"filename": upload.filename, "error": f"Invalid or unsafe ZIP archive: {exc}"})
                continue
            try:
                raw = await upload.read()
                total_upload_size += len(raw)
                if total_upload_size > 100 * 1024 * 1024:
                    failures.append({"filename": upload.filename, "error": "Batch exceeds 100 MB total upload size."})
                    continue
                await upload.seek(0)
                results.append(await self.upload(user, paper_id, upload))
            except Exception as exc:
                message = exc.message if isinstance(exc, RequestValidationAppError) else "File could not be stored or indexed."
                failures.append({"filename": upload.filename, "error": message})
        return {"documents": results, "failures": failures, "success_count": len(results), "failure_count": len(failures)}

    async def _process(self, document: Document, paper: Paper) -> None:
        """Synchronous RAG ingestion, acceptable for the prototype; the status
        model (uploaded → processing → indexed/failed) already supports moving
        this to a background worker later."""
        logger.info("RAG ingestion started document_id=%s", document.id)
        metadata = {
            "document_id": document.id,  # shared ID passed through to RAG/ChromaDB
            "filename": document.filename,
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
            # RAG parser/provider errors may contain internal paths or provider
            # response details; keep persisted API-visible errors actionable and safe.
            document.processing_error = "No text chunks could be extracted or indexed. Confirm the format is supported and the file contains extractable text."
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

import logging
import asyncio
import hashlib
import json
import shutil
import zipfile
import stat
import tempfile
import zlib
import time
import threading
from pathlib import Path, PurePosixPath
from typing import Optional
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    DocumentNotFoundError,
    PaperNotFoundError,
    RAGIngestionTimeoutError,
    RAGUnavailableError,
    RequestValidationAppError,
)
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.document import Document, DocumentStatus, DocumentWorkerLease, CleanupStatus, OperationType
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.services.paper_service import PaperService
from backend.app.services.document_service_helpers import (
    compute_file_hash_streaming,
    check_duplicate_and_classify,
    acquire_worker_lease,
    release_worker_lease,
    update_worker_heartbeat,
)
from backend.app.schemas.document import (
    DocumentUploadResult,
    DocumentBatchUploadResponse,
    DocumentUploadOutcome,
)
from backend.app.utils.validators import (
    SUPPORTED_EXTENSIONS,
    resolve_safe_path_in_dir,
    validate_document_file,
)
from rag.config.settings import settings as rag_settings

logger = logging.getLogger("backend.documents")

_background_tasks: set[asyncio.Task] = set()


def launch_background_ingest(document_id: str, paper_id: str, owner_id: str) -> None:
    task = asyncio.create_task(_run_background_ingest(document_id, paper_id, owner_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_background_ingest(document_id: str, paper_id: str, owner_id: str) -> None:
    try:
        from backend.app.database.session import get_session_factory
        from backend.app.integrations.rag_gateway import RAGGateway

        async with get_session_factory()() as db:
            rag = RAGGateway()
            service = DocumentService(db, rag)
            doc = await service.documents.get_by_id(document_id)
            if not doc:
                logger.warning("Background ingestion aborted: document %s not found", document_id)
                return
            if doc.processing_status == DocumentStatus.CANCELLED.value:
                logger.info("Background ingestion aborted: document %s was cancelled", document_id)
                return
            paper = await service.paper_service.papers.get_by_id(paper_id)
            if not paper:
                logger.warning("Background ingestion aborted: paper %s not found", paper_id)
                return

            # If resuming an uncheckpointed job from a prior session, reset progress to page 1
            checkpoint_file = Path(doc.storage_path).parent / f".ocr-{doc.id}.json"
            if not checkpoint_file.is_file() and (doc.processing_completed_units or 0) > 0:
                doc.processing_completed_units = 0
                doc.processing_progress = 5
                doc.processing_stage = "inspecting"
                await db.commit()

            await service._process(doc, paper)
    except Exception as exc:
        logger.error("Background ingestion crashed for doc %s: %s", document_id, exc, exc_info=True)


def is_generated_summary_export(entry: Path) -> bool:
    """Identifies generated summary files to prevent re-ingestion into library."""
    name = entry.name.lower()
    if name.startswith("grounded summary") or name.startswith("grounded_summary") or name.startswith(".summary"):
        return True
    if entry.suffix.lower() in {".md", ".txt"}:
        try:
            with open(entry, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(300)
                if "<!-- researchlens:generated-summary" in head or "researchlens-grounded-summary" in head:
                    return True
        except Exception:
            pass
    return False


def _get_project_exclusions(folder: Path) -> set[str]:
    """Returns set of explicitly removed filenames and hashes for a project folder."""
    ex_file = folder / ".researchlens-exclusions.json"
    if ex_file.is_file():
        try:
            data = json.loads(ex_file.read_text(encoding="utf-8"))
            return set(data.get("excluded_filenames", []) + data.get("excluded_hashes", []))
        except Exception:
            pass
    return set()


def _add_project_exclusion(folder: Path, filename: str, file_hash: Optional[str] = None) -> None:
    """Persists an exclusion to prevent auto-scanner re-import of an explicitly removed source."""
    if not folder.is_dir():
        return
    ex_file = folder / ".researchlens-exclusions.json"
    data = {"excluded_filenames": [], "excluded_hashes": []}
    if ex_file.is_file():
        try:
            data = json.loads(ex_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    fn_list = set(data.get("excluded_filenames", []))
    if filename:
        fn_list.add(filename)
    h_list = set(data.get("excluded_hashes", []))
    if file_hash:
        h_list.add(file_hash)
    data["excluded_filenames"] = sorted(list(fn_list))
    data["excluded_hashes"] = sorted(list(h_list))
    try:
        ex_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _remove_project_exclusion(folder: Path, filename: str, file_hash: Optional[str] = None) -> None:
    """Clears an exclusion when a user explicitly uploads/re-adds a source."""
    ex_file = folder / ".researchlens-exclusions.json"
    if not ex_file.is_file():
        return
    try:
        data = json.loads(ex_file.read_text(encoding="utf-8"))
        data["excluded_filenames"] = [f for f in data.get("excluded_filenames", []) if f != filename]
        if file_hash:
            data["excluded_hashes"] = [h for h in data.get("excluded_hashes", []) if h != file_hash]
        ex_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


class DocumentService:
    def __init__(self, db: AsyncSession, rag: Optional[RAGGateway] = None):
        self.db = db
        self.documents = DocumentRepository(db)
        self.paper_service = PaperService(db)
        self.rag = rag

    async def upload(self, user: User, paper_id: str, upload: UploadFile) -> Document:
        settings = get_settings()
        upload_started = time.perf_counter()
        paper = await self.paper_service.get_owned(user, paper_id)
        # A prior file in this batch may have rolled back this session; reload
        # the owner row before using its identifier in subsequent inserts.
        await self.db.refresh(paper)

        upload_dir = settings.upload_path
        upload_dir.mkdir(parents=True, exist_ok=True)
        staged = None
        storage_path = None
        db_touched = False
        try:
            hasher = hashlib.sha256()
            with tempfile.NamedTemporaryFile(prefix=".upload-", dir=upload_dir, delete=False) as target:
                staged = Path(target.name)
                size = 0
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    hasher.update(chunk)
                    if size > settings.max_upload_size_bytes:
                        raise RequestValidationAppError(f"File exceeds the maximum allowed size of {settings.max_upload_size_mb} MB.")
                    await asyncio.to_thread(target.write, chunk)
            validate_document_file(upload.filename, upload.content_type, staged, size, settings.max_upload_size_bytes)
            file_sha256 = hasher.hexdigest()

            # Milestone 1: State-aware duplicate detection
            existing, outcome, message = await check_duplicate_and_classify(
                self.db, paper.id, file_sha256, size
            )
            
            if existing:
                logger.info(
                    "Duplicate detected document_id=%s outcome=%s paper_id=%s",
                    existing.id, outcome, paper.id
                )
                if outcome == DocumentUploadOutcome.RETRY_AVAILABLE:
                    # Previous attempt was failed or cancelled; re-trigger processing
                    if staged is not None:
                        if not existing.storage_path or not Path(existing.storage_path).is_file():
                            storage_path = upload_dir / f"{existing.id}{Path(upload.filename or 'doc.pdf').suffix.lower()}"
                            staged.replace(storage_path)
                            staged = None
                            existing.storage_path = str(storage_path)
                        else:
                            staged.unlink(missing_ok=True)
                            staged = None
                    existing.processing_status = DocumentStatus.PROCESSING.value
                    existing.processing_stage = "extracting_text"
                    existing.processing_progress = 0
                    existing.processing_progress_type = "estimated"
                    existing.processing_completed_units = 0
                    existing.processing_total_units = None
                    existing.processing_unit = None
                    existing.processing_error = None
                    existing.cleanup_status = None
                    existing.operation_type = OperationType.RETRY.value
                    existing.processing_started_at = datetime.utcnow()
                    existing.processing_heartbeat_at = existing.processing_started_at
                    existing.updated_at = existing.processing_started_at
                    await self.db.flush()
                    await self.db.commit()
                    if self.rag.__class__.__name__ == "FakeRAGGateway":
                        await self._process(existing, paper)
                    else:
                        launch_background_ingest(existing.id, paper.id, paper.owner_id)
                    setattr(existing, "_upload_outcome", DocumentUploadOutcome.STORED_NEW)
                    setattr(existing, "_upload_message", "Previous attempt re-triggered and is now processing.")
                    return existing

                if staged is not None:
                    staged.unlink(missing_ok=True)
                setattr(existing, "_upload_outcome", outcome)
                setattr(existing, "_upload_message", message)
                return existing

            filename = resolve_safe_path_in_dir(upload_dir, upload.filename).name
            db_touched = True
            document = await self.documents.create(
                paper_id=paper.id,
                filename=filename,
                storage_path="",
                content_type=upload.content_type or "application/octet-stream",
                file_size=size,
            )
            # Files are stored under a generated id — user filenames never become
            # filesystem paths (no traversal).
            storage_path = upload_dir / f"{document.id}{Path(filename).suffix.lower()}"
            staged.replace(storage_path)
            staged = None
            document.storage_path = str(storage_path)
            document.file_hash_sha256 = file_sha256

            try:
                proj_folder = self.paper_service.get_project_folder(paper)
                dest = resolve_safe_path_in_dir(proj_folder, filename)
                shutil.copy2(storage_path, dest)
            except Exception as copy_err:
                logger.debug("Failed saving project document copy: %s", copy_err)

            document.operation_type = OperationType.INITIAL_UPLOAD.value
            setattr(document, "_upload_outcome", DocumentUploadOutcome.STORED_NEW)
            setattr(document, "_upload_message", None)
            document.processing_status = DocumentStatus.PROCESSING.value
            document.processing_stage = "extracting_text"
            document.processing_progress = 0
            document.processing_progress_type = "estimated"
            document.processing_completed_units = 0
            document.processing_total_units = None
            document.processing_unit = None
            document.processing_started_at = datetime.utcnow()
            document.processing_heartbeat_at = document.processing_started_at
            await self.db.flush()
            await self.db.commit()
            logger.info(
                "Document stored document_id=%s bytes=%d hash=%s duration_seconds=%.3f",
                document.id, size, file_sha256[:8], time.perf_counter() - upload_started,
            )
        except Exception:
            if staged is not None:
                staged.unlink(missing_ok=True)
            if storage_path is not None:
                storage_path.unlink(missing_ok=True)
            if db_touched:
                await self.db.rollback()
            raise
        logger.info("document uploaded document_id=%s paper_id=%s", document.id, paper.id)

        if self.rag.__class__.__name__ == "FakeRAGGateway":
            await self._process(document, paper)
        else:
            launch_background_ingest(document.id, paper.id, paper.owner_id)
        return document

    async def upload_batch(self, user: User, paper_id: str, uploads: list[UploadFile]) -> DocumentBatchUploadResponse:
        """Upload documents and bounded ZIP members into one existing paper."""
        await self.paper_service.get_owned(user, paper_id)
        settings = get_settings()
        if len(uploads) > settings.max_upload_batch_files:
            raise RequestValidationAppError(f"At most {settings.max_upload_batch_files} files may be uploaded per batch.")
        declared_total = sum(upload.size or 0 for upload in uploads)
        if declared_total > settings.max_upload_batch_size_bytes:
            raise RequestValidationAppError(f"Batch exceeds the {settings.max_upload_batch_size_mb} MB total upload limit.")
        
        results: list[DocumentUploadResult] = []
        success_count = 0
        failure_count = 0
        
        for upload in uploads:
            if (upload.filename or "").lower().endswith(".zip"):
                if (upload.size or 0) > settings.max_upload_size_bytes:
                    results.append(DocumentUploadResult(
                        filename=upload.filename,
                        document=None,
                        outcome=DocumentUploadOutcome.FAILED,
                        success=False,
                        error="Archive exceeds upload size limit.",
                        message=f"File {upload.filename} is too large"
                    ))
                    failure_count += 1
                    continue
                try:
                    upload.file.seek(0)
                    with zipfile.ZipFile(upload.file) as archive:
                        entries = archive.infolist()
                        if len(entries) > settings.max_zip_entries:
                            raise ValueError(f"Archive contains more than {settings.max_zip_entries} files.")
                        total = 0
                        for member in entries:
                            name = member.filename.replace("\\", "/")
                            path = PurePosixPath(name)
                            mode = member.external_attr >> 16
                            kind = stat.S_IFMT(mode)
                            if path.is_absolute() or (path.parts and ":" in path.parts[0]) or ".." in path.parts or stat.S_ISLNK(mode) or (kind not in (0, stat.S_IFREG, stat.S_IFDIR)):
                                results.append(DocumentUploadResult(
                                    filename=name,
                                    document=None,
                                    outcome=DocumentUploadOutcome.FAILED,
                                    success=False,
                                    error="Unsafe archive member path or type.",
                                    message=f"Archive member {name} is unsafe"
                                ))
                                failure_count += 1
                                continue
                            if member.is_dir():
                                continue
                            total += member.file_size
                            if member.file_size > settings.max_zip_entry_size_bytes:
                                raise ValueError("An archive entry exceeds the per-file size limit.")
                            if total > settings.max_zip_expanded_size_bytes or (member.compress_size and member.file_size / member.compress_size > settings.max_zip_compression_ratio):
                                raise ValueError("Archive expanded size or compression ratio exceeds safety limits.")
                            try:
                                with archive.open(member) as member_stream:
                                    member_upload = UploadFile(filename=path.as_posix(), file=member_stream, headers=upload.headers)
                                    doc = await self.upload(user, paper_id, member_upload)
                                    results.append(DocumentUploadResult(
                                        filename=path.as_posix(),
                                        document=doc,
                                        outcome=DocumentUploadOutcome.STORED_NEW,
                                        success=True,
                                        message=f"Extracted from {upload.filename}"
                                    ))
                                    success_count += 1
                            except Exception as exc:
                                message = exc.message if isinstance(exc, RequestValidationAppError) else "Member could not be stored or indexed."
                                results.append(DocumentUploadResult(
                                    filename=path.as_posix(),
                                    document=None,
                                    outcome=DocumentUploadOutcome.FAILED,
                                    success=False,
                                    error=message,
                                    message=f"Failed to extract {path.as_posix()} from {upload.filename}"
                                ))
                                failure_count += 1
                except (zipfile.BadZipFile, ValueError, RuntimeError, NotImplementedError, OSError, zlib.error) as exc:
                    results.append(DocumentUploadResult(
                        filename=upload.filename,
                        document=None,
                        outcome=DocumentUploadOutcome.FAILED,
                        success=False,
                        error=f"Invalid or unsafe ZIP archive: {exc}",
                        message=f"Archive {upload.filename} could not be processed"
                    ))
                    failure_count += 1
                continue
            
            try:
                doc = await self.upload(user, paper_id, upload)
                outcome = getattr(doc, "_upload_outcome", DocumentUploadOutcome.STORED_NEW)
                message = getattr(doc, "_upload_message", None)
                if outcome == DocumentUploadOutcome.CLEANUP_FAILED:
                    results.append(DocumentUploadResult(
                        filename=upload.filename,
                        document=doc,
                        outcome=outcome,
                        success=False,
                        error=message,
                        message=message
                    ))
                    failure_count += 1
                else:
                    results.append(DocumentUploadResult(
                        filename=upload.filename,
                        document=doc,
                        outcome=outcome,
                        success=True,
                        message=message
                    ))
                    success_count += 1
            except Exception as exc:
                logger.warning("Batch file upload failed exception_type=%s", type(exc).__name__)
                message = exc.message if isinstance(exc, RequestValidationAppError) else "File could not be stored or indexed."
                results.append(DocumentUploadResult(
                    filename=upload.filename,
                    document=None,
                    outcome=DocumentUploadOutcome.FAILED,
                    success=False,
                    error=message,
                    message=f"Failed to upload {upload.filename}"
                ))
                failure_count += 1
        
        return DocumentBatchUploadResponse(
            results=results,
            success_count=success_count,
            failure_count=failure_count
        )

    async def _process(self, document: Document, paper: Paper) -> None:
        """Synchronous RAG ingestion with cooperative cancellation and worker lease."""
        logger.info("RAG ingestion started document_id=%s operation_type=%s", document.id, document.operation_type)
        
        # Milestone 1: Capture operation type before any state mutation
        operation_type = document.operation_type or OperationType.INITIAL_UPLOAD.value
        is_reindex = (operation_type == OperationType.REINDEX.value)
        
        # Milestone 1: Acquire worker lease
        lease = None
        try:
            lease = await acquire_worker_lease(self.db, document.id)
        except Exception as lease_err:
            logger.error("Failed to acquire worker lease document_id=%s: %s", document.id, lease_err)
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_error = "Failed to acquire worker lease. Another process may be active."
            document.processing_stage = "failed"
            await self.db.commit()
            return
        
        # Milestone 1: Thread-safe cancellation event
        cancel_event = threading.Event()
        
        metadata = {
            "document_id": document.id,  # shared ID passed through to RAG/ChromaDB
            "owner_id": paper.owner_id,  # SEC-001: Paper owner for multi-tenant isolation
            "filename": document.filename,
            "title": paper.title,
            "authors": ", ".join(paper.authors or []),
            "year": paper.publication_year,
            "file_hash": getattr(document, "file_hash_sha256", None),
        }
        loop = asyncio.get_running_loop()

        last_persisted = {"stage": "extracting_text", "progress": 0, "at": time.monotonic()}
        progress_commit_stats = {"count": 0, "seconds": 0.0}

        async def persist_progress(event: dict) -> None:
            stage = str(event.get("stage", ""))
            if not stage or document.processing_status != DocumentStatus.PROCESSING.value:
                return
            progress = max(document.processing_progress or 0, min(100 if stage == "ready" else 99, max(0, int(event.get("progress", 0)))))
            now = time.monotonic()
            stage_changed = stage != last_persisted["stage"]
            progress_changed = progress != last_persisted["progress"]
            # Avoid a SELECT+COMMIT for every batch callback. Persist phase changes
            # and meaningful progress changes at most once per 750 ms.
            if not (event.get("force") or stage_changed or (progress_changed and now - last_persisted["at"] >= 0.75) or stage == "ready"):
                return
            update_data = {
                "processing_stage": stage,
                "processing_progress": progress,
                "processing_progress_type": str(event.get("progress_type") or "estimated"),
                "processing_heartbeat_at": datetime.utcnow(),
            }
            if "completed_pages" in event:
                tot = int(event.get("total_pages") or 0) or None
                comp = int(event.get("completed_pages") or 0)
                if tot is not None:
                    comp = min(comp, tot)
                update_data["processing_completed_units"] = comp
                update_data["processing_total_units"] = tot
                update_data["processing_unit"] = "pages"
            elif "completed_chunks" in event:
                tot = int(event.get("total_chunks") or 0) or None
                comp = int(event.get("completed_chunks") or 0)
                if tot is not None:
                    comp = min(comp, tot)
                update_data["processing_completed_units"] = comp
                update_data["processing_total_units"] = tot
                update_data["processing_unit"] = "chunks"

            for k, v in update_data.items():
                setattr(document, k, v)

            # Isolated DB session to prevent concurrent AsyncSession race (N11)
            # Also update worker lease heartbeat
            from backend.app.database.session import get_session_factory
            commit_started = time.perf_counter()
            try:
                async with get_session_factory()() as isolated_db:
                    await isolated_db.execute(
                        update(Document)
                        .where(Document.id == document.id)
                        .values(**update_data)
                    )
                    # Update lease heartbeat
                    if lease:
                        await isolated_db.execute(
                            update(DocumentWorkerLease)
                            .where(DocumentWorkerLease.id == lease.id)
                            .values(heartbeat_at=datetime.utcnow())
                        )
                    await isolated_db.commit()
                progress_commit_stats["count"] += 1
                progress_commit_stats["seconds"] += time.perf_counter() - commit_started
            except Exception as commit_err:
                logger.debug("Isolated progress commit notice: %s", commit_err)

            last_persisted.update(stage=stage, progress=progress, at=time.monotonic())

        def progress_callback(event: dict) -> None:
            if event.get("stage"):
                try:
                    asyncio.run_coroutine_threadsafe(persist_progress(event), loop)
                except Exception as exc:
                    logger.debug('Progress callback dispatch note: %s', exc)

        await self.db.refresh(document)
        if document.processing_status == DocumentStatus.CANCELLED.value:
            logger.info("Ingestion already cancelled before RAG call document_id=%s", document.id)
            if lease:
                await release_worker_lease(self.db, lease.id)
            return

        rag_started = time.perf_counter()
        try:
            result = await self.rag.ingest_document(
                file_path=document.storage_path,
                paper_id=document.paper_id,
                metadata=metadata,
                progress_callback=progress_callback,
                cancel_event=cancel_event,  # Milestone 1: Pass cancellation event
            )
            logger.info(
                "RAG ingestion returned document_id=%s roundtrip_seconds=%.3f pipeline_seconds=%s chunks=%s",
                document.id, time.perf_counter() - rag_started,
                result.get("execution_time_seconds"), result.get("chunk_count"),
            )
        except RAGUnavailableError as exc:
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_error = exc.message
            document.processing_stage = "failed"
            document.processing_progress = min(document.processing_progress or 0, 99)
            document.processing_progress_type = "actual"
            document.chunk_count = 0
            document.processing_heartbeat_at = datetime.utcnow()
            document.cleanup_status = CleanupStatus.PENDING.value
            # Milestone 1: Use captured operation_type, not mutated processing_stage
            if not isinstance(exc, RAGIngestionTimeoutError) and not is_reindex:
                document.processing_error = await self._cleanup_failed_index(document, exc.message)
                if "cleanup failed" in document.processing_error.lower():
                    document.cleanup_status = CleanupStatus.FAILED.value
                else:
                    document.cleanup_status = CleanupStatus.COMPLETED.value
            status_commit_started = time.perf_counter()
            await self.db.commit()
            status_commit_seconds = time.perf_counter() - status_commit_started
            logger.warning(
                "RAG ingestion failed document_id=%s error=%s progress_commits=%d progress_commit_seconds=%.4f final_status_commit_seconds=%.4f",
                document.id, exc.message, progress_commit_stats["count"],
                progress_commit_stats["seconds"], status_commit_seconds,
            )
            # Lease will be released in finally block after cleanup
            return
        finally:
            # Milestone 1: Always release lease in finally block
            if lease:
                await release_worker_lease(self.db, lease.id)

        await self.db.refresh(document)
        reported_status = str(result.get("status", ""))
        is_cancelled = (
            document.processing_status in [DocumentStatus.CANCELLED.value, DocumentStatus.CANCEL_REQUESTED.value]
            or reported_status == "cancelled"
            or "cancelled" in str(result.get("error", "")).lower()
        )

        if is_cancelled:
            logger.info("Cooperative ingestion cancellation completed document_id=%s is_reindex=%s", document.id, is_reindex)
            if is_reindex or result.get("metadata", {}).get("existing_index_preserved"):
                document.processing_status = DocumentStatus.INDEXED.value
                document.processing_stage = "ready"
                document.processing_error = None
                document.cleanup_status = None
            else:
                document.processing_status = DocumentStatus.CANCELLED.value
                document.processing_stage = "cancelled"
                document.processing_progress = 0
                document.processing_error = "Ingestion cancelled."
                document.cleanup_status = CleanupStatus.COMPLETED.value
                document.chunk_count = 0
            await self.db.commit()
            return
        success = result.get("success") and reported_status in {"indexed", "partial", "needs_review"}
        error = str(result.get("error") or "Indexing did not complete.")
        cleanup_safe = True
        if success:
            expected_count = int(result.get("chunk_count") or 0)
            try:
                counts = await self.rag.get_document_index_counts(document.id)
                if rag_settings.rag_engine_mode == "independent":
                    consistent = (
                        expected_count > 0
                        and counts.get("storage_mode") == "sqlite_fts5_only"
                        and counts.get("fts_count") == expected_count
                        and counts.get("unique_fts_count") == expected_count
                    )
                else:
                    consistent = (
                        expected_count > 0
                        and counts.get("ids_match") is True
                        and counts.get("chroma_count") == expected_count
                        and counts.get("fts_count") == expected_count
                    )
                if not consistent:
                    success = False
                    error = (
                        "Index consistency check failed "
                        f"(reported={expected_count}, Chroma={counts.get('chroma_count')}, "
                        f"FTS5={counts.get('fts_count')}, ids_match={counts.get('ids_match')})."
                    )
            except RAGUnavailableError as exc:
                success = False
                cleanup_safe = False
                error = f"Index consistency could not be verified: {exc.message}"
        if success:
            document.processing_status = DocumentStatus.INDEXED.value
            document.processing_stage = "ready"
            document.processing_progress = 100
            document.processing_progress_type = "actual"
            document.processing_heartbeat_at = datetime.utcnow()
            document.chunk_count = result.get("chunk_count")
            document.processing_error = None
            document.cleanup_status = None
        else:
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_stage = "failed"
            document.processing_progress = min(document.processing_progress or 0, 99)
            document.processing_progress_type = "actual"
            document.processing_heartbeat_at = datetime.utcnow()
            document.chunk_count = 0
            document.cleanup_status = CleanupStatus.PENDING.value
            # Milestone 1: Use captured operation_type
            if cleanup_safe and not result.get("active_attempt") and not is_reindex:
                error = await self._cleanup_failed_index(document, error)
                if "cleanup failed" in error.lower():
                    document.cleanup_status = CleanupStatus.FAILED.value
                else:
                    document.cleanup_status = CleanupStatus.COMPLETED.value
            # IngestResult errors contain parser/provider diagnostics, but never
            # expose internal storage paths in the API response.
            document.processing_error = error.replace(document.storage_path, document.filename)
        status_commit_started = time.perf_counter()
        await self.db.commit()
        status_commit_seconds = time.perf_counter() - status_commit_started
        logger.info(
            "RAG ingestion completed document_id=%s status=%s progress_commits=%d progress_commit_seconds=%.4f final_status_commit_seconds=%.4f",
            document.id,
            document.processing_status,
            progress_commit_stats["count"],
            progress_commit_stats["seconds"],
            status_commit_seconds,
        )

    async def get_owned(self, user: User, document_id: str) -> Document:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()
        try:
            await self.paper_service.get_owned(user, document.paper_id)
        except PaperNotFoundError as exc:
            raise DocumentNotFoundError() from exc
        await self._mark_stalled_documents([document])
        await self._attach_index_health([document])
        return document

    async def cancel(self, user: User, document_id: str) -> Document:
        document = await self.get_owned(user, document_id)
        if document.processing_status in [DocumentStatus.CANCELLED.value, DocumentStatus.CANCELLING_CLEANUP.value]:
            return document
        if document.processing_status not in (DocumentStatus.PROCESSING.value, DocumentStatus.UPLOADED.value,
                                             DocumentStatus.QUEUED.value, DocumentStatus.EXTRACTING.value,
                                             DocumentStatus.OCR_PROCESSING.value, DocumentStatus.STRUCTURING.value,
                                             DocumentStatus.CHUNKING.value, DocumentStatus.INDEXING.value):
            raise RequestValidationAppError("Only active or queued documents can be cancelled.")

        # Milestone 1: Set CANCEL_REQUESTED first - worker will check this
        document.processing_status = DocumentStatus.CANCEL_REQUESTED.value
        document.processing_stage = "cancel_requested"
        document.processing_error = "Cancellation requested by user."
        document.processing_heartbeat_at = datetime.utcnow()
        await self.db.commit()
        logger.info("Cancel requested document_id=%s", document.id)

        # Signal RAG pipeline to stop cooperatively
        if self.rag:
            try:
                await self.rag.cancel_ingest(document.id)
            except Exception as e:
                logger.warning("Could not signal RAG cancel document_id=%s: %s", document.id, e)

        # Worker will transition to CANCELLING_CLEANUP and then CANCELLED
        # Do NOT attempt cleanup here while worker may still be active
        # The worker owns cleanup responsibility when it reaches safe boundary
        
        return document

    async def retry(self, user: User, document_id: str) -> Document:
        document = await self.get_owned(user, document_id)
        if document.processing_status == DocumentStatus.PROCESSING.value:
            raise RequestValidationAppError("This source is already being processed.")
        if document.processing_status == DocumentStatus.INDEXED.value:
            return await self.reindex(user, document_id)
        if document.processing_status not in (DocumentStatus.FAILED.value, DocumentStatus.CANCELLED.value):
            raise RequestValidationAppError("Only failed, cancelled or indexed sources can be retried.")
        if not Path(document.storage_path).is_file():
            raise RequestValidationAppError("The stored source file is missing and cannot be retried.")
        
        # Milestone 1: Check for active worker lease or pending cleanup
        from backend.app.services.document_service_helpers import has_active_worker_lease
        if await has_active_worker_lease(self.db, document.id):
            raise RequestValidationAppError("Worker cleanup is still in progress. Please wait a moment before retrying.")
        
        if document.cleanup_status == CleanupStatus.FAILED.value:
            raise RequestValidationAppError("Previous cleanup failed. Please contact support or delete and re-upload this source.")
        
        paper = await self.paper_service.get_owned(user, document.paper_id)
        started_at = datetime.utcnow()
        claim = await self.db.execute(
            update(Document)
            .where(Document.id == document.id, Document.processing_status.in_([DocumentStatus.FAILED.value, DocumentStatus.CANCELLED.value]))
            .values(
                processing_status=DocumentStatus.PROCESSING.value,
                processing_stage="inspecting", processing_progress=5,
                processing_progress_type="estimated", processing_completed_units=0,
                processing_total_units=None, processing_unit=None,
                processing_started_at=started_at, processing_heartbeat_at=started_at,
                processing_error=None, chunk_count=0,
                operation_type=OperationType.RETRY.value,
                cleanup_status=None,
            )
        )
        if claim.rowcount != 1:
            await self.db.rollback()
            await self.db.refresh(document)
            if document.processing_status == DocumentStatus.PROCESSING.value:
                raise RequestValidationAppError("This source is already being processed.")
            raise RequestValidationAppError("This source changed state; refresh it before retrying.")
        document.processing_status = DocumentStatus.PROCESSING.value
        document.processing_stage = "inspecting"
        document.processing_progress = 5
        document.processing_progress_type = "estimated"
        document.processing_completed_units = 0
        document.processing_total_units = None
        document.processing_unit = None
        document.processing_started_at = started_at
        document.processing_heartbeat_at = started_at
        document.processing_error = None
        document.chunk_count = 0
        document.operation_type = OperationType.RETRY.value
        document.cleanup_status = None
        await self.db.commit()
        if self.rag.__class__.__name__ == "FakeRAGGateway":
            await self._process(document, paper)
        else:
            launch_background_ingest(document.id, paper.id, paper.owner_id)
        return document

    async def reindex(self, user: User, document_id: str) -> Document:
        """Safely re-index an existing document with the updated section-aware research engine.
        
        Guarantees:
        1. Preserves original stored file.
        2. Preserves existing FTS5 index until replacement succeeds.
        3. Validates section boundaries, page ranges, and SEC-001 owner metadata.
        4. Atomically replaces old index in FTS5 only after validation.
        5. If re-indexing fails, leaves old index intact and rolls back safely.
        """
        document = await self.get_owned(user, document_id)
        if document.processing_status == DocumentStatus.PROCESSING.value:
            raise RequestValidationAppError("This source is already being processed.")
        if not Path(document.storage_path).is_file():
            raise RequestValidationAppError("The stored source file is missing and cannot be re-indexed.")
        paper = await self.paper_service.get_owned(user, document.paper_id)

        previous_chunk_count = document.chunk_count
        previous_status = document.processing_status
        previous_stage = document.processing_stage

        started_at = datetime.utcnow()
        document.processing_status = DocumentStatus.PROCESSING.value
        document.processing_stage = "reindexing"
        document.processing_progress = 10
        document.processing_progress_type = "estimated"
        document.processing_started_at = started_at
        document.processing_heartbeat_at = started_at
        document.processing_error = None
        document.operation_type = OperationType.REINDEX.value  # Milestone 1: Set before processing
        await self.db.commit()

        try:
            await self._process(document, paper)
            await self.db.refresh(document)
            if document.processing_status == DocumentStatus.INDEXED.value:
                setattr(document, "reindex_required", False)
                setattr(document, "index_version", 2)
                logger.info("Document re-indexed successfully document_id=%s chunks=%s", document.id, document.chunk_count)
            else:
                error_msg = document.processing_error or "Re-indexing could not be verified."
                raise RuntimeError(error_msg)
        except Exception as exc:
            logger.warning("Re-indexing failed for document_id=%s: %s; reverting status", document.id, exc)
            document.processing_status = previous_status
            document.processing_stage = previous_stage
            document.chunk_count = previous_chunk_count
            document.processing_error = f"Re-indexing failed: {exc}. Previous index was preserved."
            setattr(document, "reindex_required", True)
            setattr(document, "index_version", 1)
            await self.db.commit()
            raise RequestValidationAppError(f"Re-indexing failed: {exc}. Your existing index was preserved.") from exc

        return document

    async def scan_and_ingest_local_folder(self, user: User, paper: Paper, folder: Path) -> int:
        """Scan an isolated project folder for new files (single-user desktop mode only)."""
        settings = get_settings()
        if not settings.is_local_folder_sync_allowed:
            return 0
        if not folder.is_dir():
            return 0
        added_count = 0
        exclusions = _get_project_exclusions(folder)
        from sqlalchemy import or_
        for entry in folder.iterdir():
            if not entry.is_file() or entry.name.startswith("."):
                continue
            if is_generated_summary_export(entry):
                continue
            safe_name = resolve_safe_path_in_dir(folder, entry.name).name
            if safe_name in exclusions:
                continue
            if entry.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                file_size = entry.stat().st_size
                if file_size <= 0 or file_size > settings.max_upload_size_bytes:
                    logger.debug("Skipping local file %s: invalid size %d", safe_name, file_size)
                    continue
                validate_document_file(
                    safe_name, None, entry, file_size, settings.max_upload_size_bytes
                )
                file_hash = compute_file_hash_streaming(entry)
                if file_hash in exclusions:
                    continue
                existing = await self.db.scalar(
                    select(Document).where(
                        Document.paper_id == paper.id,
                        or_(
                            Document.file_hash_sha256 == file_hash,
                            Document.filename == safe_name,
                        )
                    )
                )
                if existing:
                    if not existing.file_hash_sha256:
                        existing.file_hash_sha256 = file_hash
                        await self.db.commit()
                    continue

                upload_dir = settings.upload_path
                upload_dir.mkdir(parents=True, exist_ok=True)
                new_doc = await self.documents.create(
                    paper_id=paper.id,
                    filename=safe_name,
                    storage_path="",
                    content_type="application/pdf" if entry.suffix.lower() == ".pdf" else "application/octet-stream",
                    file_size=file_size,
                )
                storage_path = upload_dir / f"{new_doc.id}{entry.suffix.lower()}"
                shutil.copy2(entry, storage_path)
                new_doc.storage_path = str(storage_path)
                new_doc.file_hash_sha256 = file_hash
                new_doc.operation_type = OperationType.INITIAL_UPLOAD.value
                new_doc.processing_status = DocumentStatus.PROCESSING.value
                new_doc.processing_stage = "extracting_text"
                new_doc.processing_progress = 0
                new_doc.processing_started_at = datetime.utcnow()
                new_doc.processing_heartbeat_at = new_doc.processing_started_at
                await self.db.commit()

                launch_background_ingest(new_doc.id, paper.id, paper.owner_id)
                added_count += 1
                logger.info("Auto-ingested dropped file: %s for project %s", safe_name, paper.title)
            except Exception as scan_err:
                logger.debug("Error scanning local file %s: %s", entry.name, scan_err)
        return added_count

    async def list_for_paper(self, user: User, paper_id: str) -> list[Document]:
        await self.paper_service.get_owned(user, paper_id)
        documents = await self.documents.list_by_paper(paper_id)
        await self._mark_stalled_documents(documents)
        await self._attach_index_health(documents)
        return documents

    async def list_for_papers(self, user: User, paper_ids: list[str]) -> dict[str, list[Document]]:
        ids = list(dict.fromkeys(paper_ids))
        owned_rows = await self.db.execute(
            select(Paper.id).where(Paper.owner_id == user.id, Paper.id.in_(ids))
        )
        owned_ids = set(owned_rows.scalars().all())
        if owned_ids != set(ids):
            raise PaperNotFoundError()
        grouped: dict[str, list[Document]] = defaultdict(list)
        documents = await self.documents.list_by_papers(ids)
        await self._mark_stalled_documents(documents)
        await self._attach_index_health(documents)
        for document in documents:
            grouped[document.paper_id].append(document)
        return {paper_id: grouped[paper_id] for paper_id in ids}

    async def _attach_index_health(self, documents: list[Document]) -> None:
        """Inspect indexed documents to identify older incompatible extractions (stale indexes)."""
        for doc in documents:
            if doc.processing_status != DocumentStatus.INDEXED.value:
                setattr(doc, "reindex_required", False)
                setattr(doc, "index_version", 2)
                continue
            is_stale = False
            if (doc.chunk_count or 0) <= 1 and (doc.file_size or 0) > 8192:
                is_stale = True
            elif self.rag:
                try:
                    status = await self.rag.get_document_index_status(doc.id)
                    if status.get("is_stale"):
                        is_stale = True
                except Exception:
                    pass
            setattr(doc, "reindex_required", is_stale)
            setattr(doc, "index_version", 1 if is_stale else 2)

    async def _mark_stalled_documents(self, documents: list[Document]) -> None:
        """Turn orphaned PROCESSING rows into a visible, retryable failure."""
        timeout = get_settings().rag_ingest_timeout_seconds
        stale_after = timedelta(seconds=max(900, timeout + 60))
        cutoff = datetime.utcnow() - stale_after
        stale = [
            document for document in documents
            if document.processing_status == DocumentStatus.PROCESSING.value
            and (document.processing_heartbeat_at or document.updated_at) < cutoff
        ]
        for document in stale:
            document.processing_status = DocumentStatus.FAILED.value
            document.processing_stage = "failed"
            document.processing_progress_type = "actual"
            document.processing_error = "Processing stopped before indexing completed. Retry this source."
            document.processing_progress = 0
            document.processing_completed_units = 0
            document.processing_total_units = None
            document.processing_unit = None
            document.chunk_count = 0
            document.processing_heartbeat_at = datetime.utcnow()
        if stale:
            await self.db.commit()

    async def _cleanup_failed_index(self, document: Document, primary_error: str) -> str:
        """Clean a finished failed attempt, retaining its root error if cleanup fails."""
        try:
            await self.rag.delete_document_chunks(document.id)
            counts = await self.rag.get_document_index_counts(document.id)
            if counts.get("chroma_count") or counts.get("fts_count") or not counts.get("ids_match"):
                return f"{primary_error}; index cleanup incomplete: Chroma={counts.get('chroma_count')}, FTS5={counts.get('fts_count')}, ids_match={counts.get('ids_match')}"
        except Exception as cleanup_error:
            detail = cleanup_error.message if isinstance(cleanup_error, RAGUnavailableError) else str(cleanup_error)
            return f"{primary_error}; index cleanup failed: {type(cleanup_error).__name__}: {detail}"
        return primary_error

    async def delete(self, user: User, document_id: str) -> None:
        """Deletes an owned document, releasing leases and clearing indexed chunks."""
        document = await self.get_owned(user, document_id)

        # Release worker leases if any
        try:
            from backend.app.services.document_service_helpers import release_worker_leases_for_document
            await release_worker_leases_for_document(self.db, document.id)
        except Exception as lease_err:
            logger.debug("Worker lease release note on delete: %s", lease_err)

        # If document is actively processing, signal cancellation
        if document.processing_status in [
            DocumentStatus.PROCESSING.value,
            DocumentStatus.CANCEL_REQUESTED.value,
            DocumentStatus.UPLOADED.value,
            DocumentStatus.QUEUED.value,
        ]:
            if self.rag:
                try:
                    await self.rag.cancel_ingest(document.id)
                except Exception:
                    pass

        # Best-effort delete chunks from RAG index
        try:
            if self.rag:
                await self.rag.delete_document_chunks(document.id)
        except Exception as rag_err:
            logger.debug("RAG delete chunks note on delete: %s", rag_err)

        # Check if another document in the same project still references this file
        from sqlalchemy import or_
        other_in_paper = await self.db.scalar(
            select(Document).where(
                Document.paper_id == document.paper_id,
                Document.id != document.id,
                or_(
                    Document.filename == document.filename,
                    Document.file_hash_sha256 == document.file_hash_sha256,
                ),
            )
        )
        if not other_in_paper:
            try:
                paper = await self.paper_service.papers.get_by_id(document.paper_id)
                if paper:
                    folder = self.paper_service.get_project_folder(paper)
                    _add_project_exclusion(folder, document.filename, document.file_hash_sha256)
            except Exception as ex_err:
                logger.debug("Could not record project exclusion: %s", ex_err)

        # Mark project summary stale upon source removal
        try:
            paper = await self.paper_service.papers.get_by_id(document.paper_id)
            if paper and paper.summary_json:
                s_copy = dict(paper.summary_json)
                s_copy["is_stale"] = True
                paper.summary_json = s_copy
        except Exception:
            pass

        # Delete backend file copy if not shared by another document record
        try:
            if document.storage_path:
                other = await self.db.execute(
                    select(Document).where(Document.storage_path == document.storage_path, Document.id != document.id)
                )
                if not other.scalars().first():
                    fpath = Path(document.storage_path)
                    if fpath.is_file():
                        fpath.unlink(missing_ok=True)
                    (fpath.parent / f".ocr-{document.id}.json").unlink(missing_ok=True)
        except Exception as file_err:
            logger.debug("File deletion note on delete: %s", file_err)

        await self.db.delete(document)
        await self.db.commit()

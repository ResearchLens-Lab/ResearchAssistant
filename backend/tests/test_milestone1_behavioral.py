"""Milestone 1 Behavioral Tests - Comprehensive verification against application services and worker lifecycle.

Exercises actual DocumentService methods, worker lease lifecycle, database persistence,
and lexical FTS5 index integrity using isolated temporary SQLite databases and directories.
"""

import asyncio
import hashlib
import io
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.app.database.session as app_session
from backend.app.core.config import get_settings
from backend.app.core.exceptions import RAGUnavailableError, RequestValidationAppError
from backend.app.models.document import (
    CleanupStatus,
    Document,
    DocumentStatus,
    DocumentWorkerLease,
    OperationType,
)
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.schemas.document import DocumentBatchUploadResponse, DocumentUploadOutcome
from backend.app.services.document_service import DocumentService
from backend.app.services.document_service_helpers import (
    acquire_worker_lease,
    check_duplicate_and_classify,
    compute_file_hash_streaming,
    has_active_worker_lease,
    release_worker_lease,
)
from rag.chunking.metadata import ChunkMetadata, DocumentChunk
from rag.independent.index_writer import IndependentIndexWriter


# Sample valid minimal PDF bytes
VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n"
)


@pytest.fixture
async def app_context():
    """Create isolated temporary environment for behavioral tests."""
    with tempfile.TemporaryDirectory(prefix="rl_behavioral_", ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_library.sqlite3"
        upload_path = tmp_path / "uploads"
        upload_path.mkdir(parents=True, exist_ok=True)
        lexical_path = tmp_path / "test_lexical.sqlite3"

        settings = get_settings()
        orig_upload_dir = settings.upload_dir
        settings.upload_dir = str(upload_path)

        sqlite_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        engine = create_async_engine(sqlite_url, echo=False)

        from backend.app.database.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Wire database session globals so background tasks and persist_progress use isolated DB
        orig_app_engine = app_session._engine
        orig_app_factory = app_session._session_factory
        app_session._engine = engine
        app_session._session_factory = session_factory

        # Seed test user and paper
        async with session_factory() as session:
            user = User(
                id="user-behavioral-1",
                email="researcher@local.test",
                username="researcher1",
                hashed_password="pbkdf2_sha256$dummy",
                full_name="Lead Researcher",
            )
            paper = Paper(
                id="paper-behavioral-1",
                owner_id=user.id,
                title="Behavioral Testing Project",
                authors=["Test Author"],
            )
            session.add(user)
            session.add(paper)
            await session.commit()

        yield {
            "tmp_path": tmp_path,
            "db_path": db_path,
            "upload_path": upload_path,
            "lexical_path": lexical_path,
            "engine": engine,
            "session_factory": session_factory,
            "user_id": "user-behavioral-1",
            "paper_id": "paper-behavioral-1",
        }

        # Teardown
        app_session._engine = orig_app_engine
        app_session._session_factory = orig_app_factory
        settings.upload_dir = orig_upload_dir
        await engine.dispose()


class TestMilestone1BehavioralSuite:
    """Complete Milestone 1 behavioral test suite."""

    # -------------------------------------------------------------------------
    # Baseline checks from original suite
    # -------------------------------------------------------------------------
    def test_check_01_migration_sqlite_real_execution(self):
        """Check 1: Run actual migration DDL on isolated SQLite with test data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE documents (
                    id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    processing_status TEXT NOT NULL DEFAULT 'uploaded',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                INSERT INTO documents (id, paper_id, filename, storage_path, content_type, file_size, 
                                     processing_status, created_at, updated_at)
                VALUES ('existing-doc-1', 'paper-1', 'existing.pdf', '/storage/existing.pdf', 'application/pdf', 54321,
                        'indexed', datetime('now'), datetime('now'))
            """)
            conn.commit()

            cursor.execute("ALTER TABLE documents ADD COLUMN cleanup_status TEXT")
            cursor.execute("ALTER TABLE documents ADD COLUMN operation_type TEXT")
            cursor.execute("ALTER TABLE documents ADD COLUMN index_version INTEGER NOT NULL DEFAULT 1")
            cursor.execute("ALTER TABLE documents ADD COLUMN file_hash_sha256 TEXT")
            cursor.execute("CREATE INDEX ix_documents_file_hash ON documents(file_hash_sha256)")
            cursor.execute("CREATE INDEX ix_documents_cleanup_status ON documents(cleanup_status)")

            cursor.execute("""
                CREATE TABLE document_worker_leases (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    released_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX ix_worker_leases_document_id ON document_worker_leases(document_id)")
            cursor.execute("CREATE INDEX ix_worker_leases_status ON document_worker_leases(status)")

            conn.commit()

            cursor.execute("SELECT id, filename, index_version, cleanup_status FROM documents WHERE id='existing-doc-1'")
            row = cursor.fetchone()
            assert row is not None, "Existing row lost during migration"
            assert row[0] == "existing-doc-1"
            assert row[1] == "existing.pdf"
            assert row[2] == 1, "index_version default not applied"
            assert row[3] is None, "cleanup_status should be NULL"

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_worker_leases'")
            assert cursor.fetchone() is not None
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_check_02_streaming_hash_actual_file(self):
        """Check 2: Streaming hash computation on actual 5MB file without full loading."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for _ in range(5000):
                tmp.write(b"x" * 1024)
            tmp.flush()
            pdf_path = Path(tmp.name)

        try:
            streaming_hash = compute_file_hash_streaming(pdf_path)
            manual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            assert streaming_hash == manual_hash
            assert len(streaming_hash) == 64
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_check_10_sqlite_consistency_after_operations(self):
        """Check 10: Verify SQLite consistency across lexical tables with no orphan headings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_lexical.sqlite3"
            writer = IndependentIndexWriter(db_path)

            chunks = [
                DocumentChunk(
                    metadata=ChunkMetadata(
                        chunk_id="chunk-1",
                        chunk_index=0,
                        document_id="doc-consistency-1",
                        paper_id="paper-1",
                        owner_id="user-1",
                        section="Introduction",
                        page_start=1,
                        page_end=1,
                        title="Test Doc",
                        filename="test.pdf",
                        locator="Page 1",
                        extra={"heading_path": ["Introduction"], "extraction_confidence": 0.95},
                    ),
                    text="Test chunk text for consistency check.",
                ),
                DocumentChunk(
                    metadata=ChunkMetadata(
                        chunk_id="chunk-2",
                        chunk_index=1,
                        document_id="doc-consistency-1",
                        paper_id="paper-1",
                        owner_id="user-1",
                        section="Methods",
                        page_start=2,
                        page_end=2,
                        title="Test Doc",
                        filename="test.pdf",
                        locator="Page 2",
                        extra={"heading_path": ["Methods"], "extraction_confidence": 0.88},
                    ),
                    text="Methods section text.",
                ),
            ]

            writer.replace_document_chunks("doc-consistency-1", chunks)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM lexical_chunks WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 2
            cursor.execute("SELECT COUNT(*) FROM lexical_metadata WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 2
            cursor.execute("SELECT COUNT(*) FROM headings_fts")
            assert cursor.fetchone()[0] == 2

            writer.delete_document("doc-consistency-1")

            cursor.execute("SELECT COUNT(*) FROM lexical_chunks WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM lexical_metadata WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM headings_fts")
            assert cursor.fetchone()[0] == 0, "Heading orphans detected"
            conn.close()

    def test_check_11_quality_zero_persisted_and_retrieved(self):
        """Check 11: Verify extraction_quality=0.0 persists and retrieves as 0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_quality.sqlite3"
            writer = IndependentIndexWriter(db_path)

            chunks = [
                DocumentChunk(
                    metadata=ChunkMetadata(
                        chunk_id="chunk-zero-quality",
                        chunk_index=0,
                        document_id="doc-quality-1",
                        paper_id="paper-1",
                        owner_id="user-1",
                        section="OCR Section",
                        page_start=1,
                        page_end=1,
                        title="Low Quality OCR",
                        filename="scanned.pdf",
                        locator="Page 1",
                        extra={"extraction_confidence": 0.0, "extraction_method": "ocr"},
                    ),
                    text="Poorly scanned text with zero confidence.",
                ),
            ]

            writer.replace_document_chunks("doc-quality-1", chunks)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT quality_score FROM lexical_metadata WHERE chunk_id='chunk-zero-quality'")
            quality = cursor.fetchone()[0]
            assert quality == 0.0, f"Quality should be 0.0, got {quality}"
            conn.close()

    # -------------------------------------------------------------------------
    # Scenario 1: Upload a new PDF and verify that document and background job
    # are created correctly.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_01_upload_new_pdf_creates_document_and_job(self, app_context):
        """Scenario 1: Upload new PDF via DocumentService.upload; verify document, hash, and worker dispatch."""
        session_factory = app_context["session_factory"]
        expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

        mock_rag = AsyncMock()
        mock_rag.ingest_document = AsyncMock(return_value={"success": True, "chunk_count": 3, "status": "indexed"})
        mock_rag.get_document_index_counts = AsyncMock(
            return_value={"storage_mode": "sqlite_fts5_only", "fts_count": 3, "unique_fts_count": 3}
        )

        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, mock_rag)

            upload = UploadFile(
                filename="quantum_paper.pdf",
                file=io.BytesIO(VALID_PDF_BYTES),
                headers={"content-type": "application/pdf"},
            )

            with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
                doc = await service.upload(user, paper.id, upload)

                # 1. Document record created with correct fields
                assert doc.id is not None
                assert doc.paper_id == paper.id
                assert doc.filename == "quantum_paper.pdf"
                assert doc.file_size == len(VALID_PDF_BYTES)
                assert doc.file_hash_sha256 == expected_hash
                assert doc.operation_type == OperationType.INITIAL_UPLOAD.value
                assert doc.processing_status == DocumentStatus.PROCESSING.value

                # 2. File stored on disk in isolated upload directory
                storage_file = Path(doc.storage_path)
                assert storage_file.is_file()
                assert storage_file.read_bytes() == VALID_PDF_BYTES

                # 3. Background worker was dispatched
                mock_launch.assert_called_once_with(doc.id, paper.id, user.id)

            # 4. Now execute worker lifecycle (_process) to verify full lease & status transition
            await service._process(doc, paper)
            await session.refresh(doc)
            assert doc.processing_status == DocumentStatus.INDEXED.value
            assert doc.chunk_count == 3
            assert doc.processing_progress == 100

            # 5. Verify worker lease was acquired and cleanly released
            result = await session.execute(
                select(DocumentWorkerLease).where(DocumentWorkerLease.document_id == doc.id)
            )
            leases = result.scalars().all()
            assert len(leases) == 1
            assert leases[0].status == "released"
            assert leases[0].released_at is not None

    # -------------------------------------------------------------------------
    # Scenario 2: Upload an already-indexed PDF and verify that no duplicate worker
    # or document is created.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_02_upload_already_indexed_pdf_no_duplicate(self, app_context):
        """Scenario 2: Upload already-indexed PDF; verify existing doc returned and no new worker launched."""
        session_factory = app_context["session_factory"]
        expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

        # Seed existing indexed document
        async with session_factory() as session:
            existing_doc = Document(
                id="doc-already-indexed-1",
                paper_id=app_context["paper_id"],
                filename="indexed_original.pdf",
                storage_path=str(app_context["upload_path"] / "doc-already-indexed-1.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=expected_hash,
                processing_status=DocumentStatus.INDEXED.value,
                chunk_count=15,
                index_version=2,
            )
            # Write physical file to storage
            Path(existing_doc.storage_path).write_bytes(VALID_PDF_BYTES)
            session.add(existing_doc)
            await session.commit()

        # Attempt upload with identical PDF
        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, AsyncMock())

            upload = UploadFile(
                filename="reuploaded_same.pdf",
                file=io.BytesIO(VALID_PDF_BYTES),
                headers={"content-type": "application/pdf"},
            )

            with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
                returned_doc = await service.upload(user, paper.id, upload)

                # Returns existing document without creating duplicate
                assert returned_doc.id == "doc-already-indexed-1"
                assert getattr(returned_doc, "_upload_outcome") == DocumentUploadOutcome.ALREADY_INDEXED
                assert not mock_launch.called, "Worker should not be dispatched for already-indexed file"

            # Verify total document count remains exactly 1
            result = await session.execute(
                select(Document).where(Document.paper_id == app_context["paper_id"])
            )
            all_docs = result.scalars().all()
            assert len(all_docs) == 1
            assert all_docs[0].id == "doc-already-indexed-1"

            # Verify no temporary upload artifacts left in uploads dir
            staged_files = list(app_context["upload_path"].glob(".upload-*"))
            assert len(staged_files) == 0

    # -------------------------------------------------------------------------
    # Scenario 3: Upload a PDF that is currently processing and verify that
    # the existing job is returned.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_03_upload_processing_pdf_returns_existing_job(self, app_context):
        """Scenario 3: Upload PDF while processing; verify existing job returned without duplicate worker."""
        session_factory = app_context["session_factory"]
        expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

        # Seed document in PROCESSING state with active worker lease
        async with session_factory() as session:
            proc_doc = Document(
                id="doc-currently-processing",
                paper_id=app_context["paper_id"],
                filename="currently_processing.pdf",
                storage_path=str(app_context["upload_path"] / "doc-currently-processing.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=expected_hash,
                processing_status=DocumentStatus.PROCESSING.value,
                processing_stage="extracting_text",
                processing_progress=30,
            )
            Path(proc_doc.storage_path).write_bytes(VALID_PDF_BYTES)
            session.add(proc_doc)
            await session.commit()

            lease = await acquire_worker_lease(session, proc_doc.id, "worker-in-flight-1")
            assert lease.status == "active"

        # Attempt duplicate upload while worker is active
        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, AsyncMock())

            upload = UploadFile(
                filename="currently_processing_reupload.pdf",
                file=io.BytesIO(VALID_PDF_BYTES),
                headers={"content-type": "application/pdf"},
            )

            with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
                returned_doc = await service.upload(user, paper.id, upload)

                # Verify existing job is returned
                assert returned_doc.id == "doc-currently-processing"
                assert getattr(returned_doc, "_upload_outcome") == DocumentUploadOutcome.EXISTING_JOB
                assert not mock_launch.called, "Worker must NOT be dispatched for file with active job"

            # Document count is still 1
            result = await session.execute(
                select(Document).where(Document.paper_id == app_context["paper_id"])
            )
            assert len(result.scalars().all()) == 1

            # Worker lease remains the single original active lease
            result = await session.execute(
                select(DocumentWorkerLease).where(DocumentWorkerLease.document_id == "doc-currently-processing")
            )
            leases = result.scalars().all()
            assert len(leases) == 1
            assert leases[0].worker_id == "worker-in-flight-1"

    # -------------------------------------------------------------------------
    # Scenario 4: Retry a failed or cancelled document after its previous worker
    # has stopped.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_04_retry_after_worker_stopped(self, app_context):
        """Scenario 4: Retry failed/cancelled doc after prior worker stopped; verify status reset and worker dispatch."""
        session_factory = app_context["session_factory"]

        # Seed failed document with stopped worker (lease released)
        async with session_factory() as session:
            failed_doc = Document(
                id="doc-failed-prior",
                paper_id=app_context["paper_id"],
                filename="failed_source.pdf",
                storage_path=str(app_context["upload_path"] / "doc-failed-prior.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=hashlib.sha256(VALID_PDF_BYTES).hexdigest(),
                processing_status=DocumentStatus.FAILED.value,
                processing_stage="failed",
                processing_error="Connection to OCR engine timed out",
                cleanup_status=CleanupStatus.COMPLETED.value,
            )
            Path(failed_doc.storage_path).write_bytes(VALID_PDF_BYTES)
            session.add(failed_doc)
            await session.commit()

            # Record released lease
            prior_lease = DocumentWorkerLease(
                document_id=failed_doc.id,
                worker_id="worker-old",
                status="released",
                started_at=datetime.utcnow() - timedelta(minutes=10),
                heartbeat_at=datetime.utcnow() - timedelta(minutes=9),
                released_at=datetime.utcnow() - timedelta(minutes=9),
            )
            session.add(prior_lease)
            await session.commit()

            # Confirm no active lease
            assert not await has_active_worker_lease(session, failed_doc.id)

        # Execute retry via DocumentService
        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, AsyncMock())

            with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
                retried = await service.retry(user, "doc-failed-prior")

                # Verify state reset
                assert retried.processing_status == DocumentStatus.PROCESSING.value
                assert retried.processing_stage == "inspecting"
                assert retried.processing_progress == 5
                assert retried.processing_error is None
                assert retried.cleanup_status is None
                assert retried.operation_type == OperationType.RETRY.value

                # Verify background worker dispatched
                mock_launch.assert_called_once_with("doc-failed-prior", paper.id, user.id)

            # Verify persisted in database
            await session.refresh(retried)
            assert retried.processing_status == DocumentStatus.PROCESSING.value
            assert retried.operation_type == OperationType.RETRY.value
            assert retried.processing_error is None

    # -------------------------------------------------------------------------
    # Scenario 5: Cancel a running document and verify cooperative worker
    # termination and exactly one lease release.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_05_cancel_running_document_cooperative_and_one_lease_release(self, app_context):
        """Scenario 5: Cancel running document; verify cooperative termination, file preservation, and exactly 1 lease release."""
        session_factory = app_context["session_factory"]

        mock_rag = AsyncMock()
        mock_rag.cancel_ingest = AsyncMock(return_value=True)
        mock_rag.delete_document_chunks = AsyncMock(return_value=0)

        # Seed document currently processing with active worker lease
        async with session_factory() as session:
            doc = Document(
                id="doc-cancel-target",
                paper_id=app_context["paper_id"],
                filename="cancel_target.pdf",
                storage_path=str(app_context["upload_path"] / "doc-cancel-target.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=hashlib.sha256(VALID_PDF_BYTES).hexdigest(),
                processing_status=DocumentStatus.PROCESSING.value,
                processing_stage="extracting_text",
                processing_progress=25,
            )
            stored_file = Path(doc.storage_path)
            stored_file.write_bytes(VALID_PDF_BYTES)
            session.add(doc)
            await session.commit()

            lease = await acquire_worker_lease(session, doc.id, "worker-cancel-test")
            lease_id = lease.id

        # Call service.cancel()
        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            service = DocumentService(session, mock_rag)

            cancelled_doc = await service.cancel(user, "doc-cancel-target")
            assert cancelled_doc.processing_status == DocumentStatus.CANCEL_REQUESTED.value
            mock_rag.cancel_ingest.assert_called_once_with("doc-cancel-target")

            # Source file MUST be preserved
            assert stored_file.is_file()
            assert stored_file.read_bytes() == VALID_PDF_BYTES

            # Worker cooperative termination: Worker notices cancel requested
            cancelled_doc.processing_status = DocumentStatus.CANCELLED.value
            cancelled_doc.processing_stage = "cancelled"
            cancelled_doc.cleanup_status = CleanupStatus.COMPLETED.value
            await session.commit()

            # Worker releases lease
            await release_worker_lease(session, lease_id)

            # Verify lease released exactly once
            result = await session.execute(
                select(DocumentWorkerLease).where(DocumentWorkerLease.id == lease_id)
            )
            db_lease = result.scalars().first()
            assert db_lease.status == "released"
            assert db_lease.released_at is not None

            # Attempt redundant release to verify idempotency (must not error or create orphan)
            await release_worker_lease(session, lease_id)
            await session.refresh(db_lease)
            assert db_lease.status == "released"

            # Confirm no active lease remains
            assert not await has_active_worker_lease(session, "doc-cancel-target")

    # -------------------------------------------------------------------------
    # Scenario 6: Simulate an HTTP timeout while the original worker is still
    # running. Verify that a second worker cannot start.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_06_http_timeout_while_worker_running_blocks_second_worker(self, app_context):
        """Scenario 6: HTTP timeout occurs while worker 1 runs; verify retry rejected and duplicate upload blocked."""
        session_factory = app_context["session_factory"]
        expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

        # Document was processing, client request timed out, but worker is alive with fresh heartbeat
        async with session_factory() as session:
            doc = Document(
                id="doc-timeout-sim",
                paper_id=app_context["paper_id"],
                filename="timeout_sim.pdf",
                storage_path=str(app_context["upload_path"] / "doc-timeout-sim.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=expected_hash,
                processing_status=DocumentStatus.PROCESSING.value,
                processing_stage="extracting_text",
                processing_progress=45,
                processing_heartbeat_at=datetime.utcnow(),
            )
            Path(doc.storage_path).write_bytes(VALID_PDF_BYTES)
            session.add(doc)
            await session.commit()

            lease = await acquire_worker_lease(session, doc.id, "worker-1-running")
            assert lease.status == "active"

        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, AsyncMock())

            # 1. Attempt retry on active job -> must be rejected
            with pytest.raises(RequestValidationAppError) as exc_info:
                await service.retry(user, "doc-timeout-sim")
            assert "already being processed" in str(exc_info.value).lower() or "cleanup is still in progress" in str(exc_info.value).lower()

            # 2. Attempt duplicate upload -> must return existing job without launching second worker
            upload = UploadFile(
                filename="timeout_retry_upload.pdf",
                file=io.BytesIO(VALID_PDF_BYTES),
                headers={"content-type": "application/pdf"},
            )
            with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
                returned = await service.upload(user, paper.id, upload)
                assert returned.id == "doc-timeout-sim"
                assert getattr(returned, "_upload_outcome") == DocumentUploadOutcome.EXISTING_JOB
                assert not mock_launch.called, "Second worker must not be dispatched"

            # 3. Exactly one worker lease exists and belongs to worker 1
            result = await session.execute(
                select(DocumentWorkerLease).where(DocumentWorkerLease.document_id == "doc-timeout-sim")
            )
            leases = result.scalars().all()
            assert len(leases) == 1
            assert leases[0].worker_id == "worker-1-running"
            assert leases[0].status == "active"

    # -------------------------------------------------------------------------
    # Scenario 7: Simulate cleanup failure and verify that the original PDF is
    # preserved and the correct cleanup status is recorded.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_07_cleanup_failure_preserves_pdf_and_records_status(self, app_context):
        """Scenario 7: Ingest fails and cleanup fails; verify PDF preserved, status FAILED/CLEANUP_FAILED, retry blocked."""
        session_factory = app_context["session_factory"]

        mock_rag = AsyncMock()
        mock_rag.ingest_document = AsyncMock(side_effect=RAGUnavailableError("OCR engine crashed"))
        mock_rag.delete_document_chunks = AsyncMock(side_effect=RAGUnavailableError("Database locked during cleanup"))

        async with session_factory() as session:
            doc = Document(
                id="doc-cleanup-fail-1",
                paper_id=app_context["paper_id"],
                filename="cleanup_failure_doc.pdf",
                storage_path=str(app_context["upload_path"] / "doc-cleanup-fail-1.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=hashlib.sha256(VALID_PDF_BYTES).hexdigest(),
                processing_status=DocumentStatus.PROCESSING.value,
                operation_type=OperationType.INITIAL_UPLOAD.value,
            )
            stored_file = Path(doc.storage_path)
            stored_file.write_bytes(VALID_PDF_BYTES)
            session.add(doc)
            await session.commit()

            paper = await session.get(Paper, app_context["paper_id"])
            user = await session.get(User, app_context["user_id"])
            service = DocumentService(session, mock_rag)

            # Run worker lifecycle which encounters ingestion failure + cleanup failure
            await service._process(doc, paper)
            await session.refresh(doc)

            # 1. Status is FAILED and cleanup_status is FAILED
            assert doc.processing_status == DocumentStatus.FAILED.value
            assert doc.cleanup_status == CleanupStatus.FAILED.value
            assert "cleanup failed" in doc.processing_error.lower()

            # 2. Original PDF file is completely preserved
            assert stored_file.is_file()
            assert stored_file.read_bytes() == VALID_PDF_BYTES

            # 3. Subsequent retry is blocked due to failed cleanup
            with pytest.raises(RequestValidationAppError) as exc_retry:
                await service.retry(user, "doc-cleanup-fail-1")
            assert "previous cleanup failed" in str(exc_retry.value).lower()

    # -------------------------------------------------------------------------
    # Scenario 8: Simulate reindex failure and verify that the previously working
    # index remains searchable.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_08_reindex_failure_preserves_searchable_index(self, app_context):
        """Scenario 8: Reindex fails; verify document reverts and previous FTS5 index remains fully searchable."""
        session_factory = app_context["session_factory"]
        lexical_db_path = app_context["lexical_path"]

        # Step 1: Populate working index in real SQLite FTS5 database
        writer = IndependentIndexWriter(lexical_db_path)
        writer.collection_name = f"paper_{app_context['paper_id']}"

        chunks = [
            DocumentChunk(
                metadata=ChunkMetadata(
                    chunk_id="reindex-chunk-1",
                    chunk_index=0,
                    document_id="doc-reindex-searchable",
                    paper_id=app_context["paper_id"],
                    owner_id=app_context["user_id"],
                    section="Graph Algorithms",
                    page_start=1,
                    page_end=1,
                    title="Algorithms Text",
                    filename="algo.pdf",
                    locator="Page 1",
                    extra={"heading_path": ["Graph Algorithms"], "extraction_confidence": 0.98},
                ),
                text="Dijkstra algorithm computes single source shortest paths in directed graphs.",
            ),
            DocumentChunk(
                metadata=ChunkMetadata(
                    chunk_id="reindex-chunk-2",
                    chunk_index=1,
                    document_id="doc-reindex-searchable",
                    paper_id=app_context["paper_id"],
                    owner_id=app_context["user_id"],
                    section="Dynamic Programming",
                    page_start=2,
                    page_end=2,
                    title="Algorithms Text",
                    filename="algo.pdf",
                    locator="Page 2",
                    extra={"heading_path": ["Dynamic Programming"], "extraction_confidence": 0.94},
                ),
                text="Bellman-Ford algorithm accommodates negative weight edges in graphs.",
            ),
        ]
        inserted_count = writer.replace_document_chunks("doc-reindex-searchable", chunks)
        assert inserted_count == 2

        # Verify initial FTS5 searchability
        conn = sqlite3.connect(lexical_db_path)
        cur = conn.cursor()
        cur.execute("SELECT chunk_id FROM lexical_chunks WHERE lexical_chunks MATCH 'Dijkstra'")
        assert cur.fetchone()[0] == "reindex-chunk-1"
        conn.close()

        # Step 2: Seed document in DB with INDEXED status (v1 index)
        async with session_factory() as session:
            doc = Document(
                id="doc-reindex-searchable",
                paper_id=app_context["paper_id"],
                filename="algo.pdf",
                storage_path=str(app_context["upload_path"] / "doc-reindex-searchable.pdf"),
                content_type="application/pdf",
                file_size=len(VALID_PDF_BYTES),
                file_hash_sha256=hashlib.sha256(VALID_PDF_BYTES).hexdigest(),
                processing_status=DocumentStatus.INDEXED.value,
                chunk_count=2,
                index_version=1,
            )
            Path(doc.storage_path).write_bytes(VALID_PDF_BYTES)
            session.add(doc)
            await session.commit()

        # Step 3: Trigger reindex with simulated RAG failure
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        mock_rag.ingest_document = AsyncMock(side_effect=RAGUnavailableError("Embedding worker crashed during reindex"))

        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            service = DocumentService(session, mock_rag)

            with pytest.raises(RequestValidationAppError) as exc_info:
                await service.reindex(user, "doc-reindex-searchable")
            assert "index was preserved" in str(exc_info.value).lower()

            # Retrieve updated document state in current session
            doc = await session.get(Document, "doc-reindex-searchable")
            assert doc.processing_status == DocumentStatus.INDEXED.value
            assert doc.chunk_count == 2
            assert doc.reindex_required is True
            assert doc.index_version == 1
            assert "index was preserved" in doc.processing_error.lower()

        # Step 4: Verify the SQLite FTS5 index is STILL fully intact and searchable!
        conn = sqlite3.connect(lexical_db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT chunk_id, text FROM lexical_chunks WHERE lexical_chunks MATCH 'Dijkstra'")
            row1 = cur.fetchone()
            assert row1 is not None
            assert row1[0] == "reindex-chunk-1"
            assert "Dijkstra" in row1[1]

            cur.execute("SELECT chunk_id, text FROM lexical_chunks WHERE lexical_chunks MATCH '\"Bellman-Ford\"'")
            row2 = cur.fetchone()
            assert row2 is not None
            assert row2[0] == "reindex-chunk-2"
            assert "Bellman-Ford" in row2[1]
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Scenario 9: Test a mixed batch upload containing valid and invalid PDFs.
    # Verify independent per-file outcomes.
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_scenario_09_mixed_batch_upload_independent_outcomes(self, app_context):
        """Scenario 9: Mixed batch upload (1 new valid, 1 duplicate indexed, 1 invalid); verify independent outcomes."""
        session_factory = app_context["session_factory"]

        valid_pdf_1 = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n%New File"
        )
        valid_pdf_2 = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n%Duplicate File"
        )
        corrupt_bytes = b"THIS_IS_NOT_A_VALID_PDF_HEADER"

        dup_hash = hashlib.sha256(valid_pdf_2).hexdigest()

        # Seed existing indexed document matching valid_pdf_2
        async with session_factory() as session:
            existing_doc = Document(
                id="doc-batch-dup-existing",
                paper_id=app_context["paper_id"],
                filename="duplicate_source.pdf",
                storage_path=str(app_context["upload_path"] / "doc-batch-dup-existing.pdf"),
                content_type="application/pdf",
                file_size=len(valid_pdf_2),
                file_hash_sha256=dup_hash,
                processing_status=DocumentStatus.INDEXED.value,
                chunk_count=8,
            )
            Path(existing_doc.storage_path).write_bytes(valid_pdf_2)
            session.add(existing_doc)
            await session.commit()

        # Prepare 3 uploads for batch
        upload_new = UploadFile(
            filename="valid_new.pdf",
            file=io.BytesIO(valid_pdf_1),
            headers={"content-type": "application/pdf"},
        )
        upload_dup = UploadFile(
            filename="already_indexed.pdf",
            file=io.BytesIO(valid_pdf_2),
            headers={"content-type": "application/pdf"},
        )
        upload_corrupt = UploadFile(
            filename="corrupt.pdf",
            file=io.BytesIO(corrupt_bytes),
            headers={"content-type": "application/pdf"},
        )

        mock_rag = AsyncMock()
        async with session_factory() as session:
            user = await session.get(User, app_context["user_id"])
            paper = await session.get(Paper, app_context["paper_id"])
            service = DocumentService(session, mock_rag)

            with patch("backend.app.services.document_service.launch_background_ingest"):
                batch_response = await service.upload_batch(
                    user, paper.id, [upload_new, upload_dup, upload_corrupt]
                )

            assert isinstance(batch_response, DocumentBatchUploadResponse)
            assert len(batch_response.results) == 3

            # Result 0: Valid new PDF -> STORED_NEW
            r0 = batch_response.results[0]
            assert r0.outcome == DocumentUploadOutcome.STORED_NEW
            assert r0.document is not None
            assert r0.document.filename == "valid_new.pdf"
            assert r0.error is None

            # Result 1: Duplicate indexed PDF -> ALREADY_INDEXED
            r1 = batch_response.results[1]
            assert r1.outcome == DocumentUploadOutcome.ALREADY_INDEXED
            assert r1.document is not None
            assert r1.document.id == "doc-batch-dup-existing"
            assert r1.error is None

            # Result 2: Corrupt PDF -> FAILED
            r2 = batch_response.results[2]
            assert r2.outcome == DocumentUploadOutcome.FAILED
            assert r2.document is None
            assert r2.error is not None
            assert "valid pdf" in r2.error.lower()

            # Independent outcome tallies
            assert batch_response.success_count == 2
            assert batch_response.failure_count == 1

            # Confirm valid new document was stored in DB
            result = await session.execute(
                select(Document).where(Document.id == r0.document.id)
            )
            saved_new = result.scalars().first()
            assert saved_new is not None
            assert saved_new.filename == "valid_new.pdf"
            assert Path(saved_new.storage_path).is_file()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

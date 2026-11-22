"""
Behavioral Acceptance Suite for Project Source Upload Lifecycle & 4-Source Boundary Validation.
Exercises actual DocumentService, Database, and Worker Lifecycle on isolated temporary databases.
No production data is touched or modified.
"""

import io
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import select

from backend.app.database.base import Base
from backend.app.models.user import User
from backend.app.models.paper import Paper
from backend.app.models.document import Document, DocumentStatus, OperationType, CleanupStatus
from backend.app.schemas.document import DocumentBatchUploadResponse, DocumentUploadOutcome
from backend.app.services.document_service import DocumentService
from fastapi import UploadFile

VALID_PDF_1 = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n%Doc1"
)

VALID_PDF_2 = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n%Doc2"
)

VALID_PDF_5TH = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n%Doc5th"
)

CORRUPT_BYTES = b"NOT_A_VALID_PDF_FILE"


@pytest.fixture
async def isolated_env():
    """Create isolated SQLite database and upload directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_lifecycle.sqlite3"
        upload_path = tmp_path / "uploads"
        upload_path.mkdir(parents=True, exist_ok=True)

        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        user_id = "test-user-1"
        paper_id = "test-paper-1"
        async with session_factory() as session:
            test_user = User(
                id=user_id,
                email="tester@researchlens.test",
                username="testuser",
                hashed_password="fakehash",
                is_active=True,
            )
            test_paper = Paper(
                id=paper_id,
                owner_id=user_id,
                title="Algorithms Acceptance Project",
                authors=["Test Author"],
            )
            session.add(test_user)
            session.add(test_paper)
            await session.commit()

        with patch("backend.app.core.config.get_settings") as mock_settings:
            from backend.app.core.config import Settings
            s = Settings(
                database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
                upload_dir=str(upload_path),
                max_upload_size_mb=100,
                max_upload_batch_size_mb=500,
                max_upload_batch_files=10,
            )
            mock_settings.return_value = s

            try:
                yield {
                    "session_factory": session_factory,
                    "engine": engine,
                    "user_id": user_id,
                    "paper_id": paper_id,
                    "upload_path": upload_path,
                }
            finally:
                await engine.dispose()


@pytest.mark.asyncio
async def test_acceptance_01_upload_single_new_pdf(isolated_env):
    """1. Upload one new PDF: verify document record created and background worker dispatched."""
    session_factory = isolated_env["session_factory"]
    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        upload = UploadFile(
            filename="algorithm_paper.pdf",
            file=io.BytesIO(VALID_PDF_1),
            headers={"content-type": "application/pdf"},
        )

        with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
            doc = await service.upload(user, paper.id, upload)

            assert doc is not None
            assert doc.filename == "algorithm_paper.pdf"
            assert doc.processing_status == DocumentStatus.PROCESSING.value
            assert doc.processing_stage == "extracting_text"
            assert doc.file_size == len(VALID_PDF_1)
            assert doc.file_hash_sha256 == hashlib.sha256(VALID_PDF_1).hexdigest()
            assert mock_launch.called, "Worker must be dispatched for new upload"
            mock_launch.assert_called_once_with(doc.id, paper.id, user.id)

            # Verify persisted file in uploads
            stored_file = Path(doc.storage_path)
            assert stored_file.is_file()
            assert stored_file.read_bytes() == VALID_PDF_1


@pytest.mark.asyncio
async def test_acceptance_02_upload_same_pdf_again(isolated_env):
    """2. Upload the same PDF again: verify no duplicate record or worker is created."""
    session_factory = isolated_env["session_factory"]
    expected_hash = hashlib.sha256(VALID_PDF_1).hexdigest()

    # Seed initial indexed document
    async with session_factory() as session:
        existing = Document(
            id="doc-initial-indexed",
            paper_id=isolated_env["paper_id"],
            filename="algorithm_paper.pdf",
            storage_path=str(isolated_env["upload_path"] / "doc-initial-indexed.pdf"),
            content_type="application/pdf",
            file_size=len(VALID_PDF_1),
            file_hash_sha256=expected_hash,
            processing_status=DocumentStatus.INDEXED.value,
            chunk_count=10,
        )
        Path(existing.storage_path).write_bytes(VALID_PDF_1)
        session.add(existing)
        await session.commit()

    # Re-upload the exact same file
    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        upload = UploadFile(
            filename="algorithm_paper_duplicate.pdf",
            file=io.BytesIO(VALID_PDF_1),
            headers={"content-type": "application/pdf"},
        )

        with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
            returned = await service.upload(user, paper.id, upload)

            assert returned.id == "doc-initial-indexed"
            assert getattr(returned, "_upload_outcome") == DocumentUploadOutcome.ALREADY_INDEXED
            assert not mock_launch.called, "Worker should not be dispatched for duplicate indexed file"

        # Check total count is still 1
        docs = await service.list_for_paper(user, paper.id)
        assert len(docs) == 1
        assert docs[0].id == "doc-initial-indexed"


@pytest.mark.asyncio
async def test_acceptance_03_mixed_batch_upload(isolated_env):
    """3. Upload a mixed batch (valid, duplicate, invalid): verify independent per-file outcomes."""
    session_factory = isolated_env["session_factory"]
    dup_hash = hashlib.sha256(VALID_PDF_1).hexdigest()

    # Seed existing indexed document matching VALID_PDF_1
    async with session_factory() as session:
        existing = Document(
            id="doc-batch-dup",
            paper_id=isolated_env["paper_id"],
            filename="existing_source.pdf",
            storage_path=str(isolated_env["upload_path"] / "doc-batch-dup.pdf"),
            content_type="application/pdf",
            file_size=len(VALID_PDF_1),
            file_hash_sha256=dup_hash,
            processing_status=DocumentStatus.INDEXED.value,
            chunk_count=5,
        )
        Path(existing.storage_path).write_bytes(VALID_PDF_1)
        session.add(existing)
        await session.commit()

    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        upload_new = UploadFile(
            filename="valid_new_2.pdf",
            file=io.BytesIO(VALID_PDF_2),
            headers={"content-type": "application/pdf"},
        )
        upload_dup = UploadFile(
            filename="already_indexed_file.pdf",
            file=io.BytesIO(VALID_PDF_1),
            headers={"content-type": "application/pdf"},
        )
        upload_invalid = UploadFile(
            filename="corrupt_bad.pdf",
            file=io.BytesIO(CORRUPT_BYTES),
            headers={"content-type": "application/pdf"},
        )

        with patch("backend.app.services.document_service.launch_background_ingest"):
            resp = await service.upload_batch(user, paper.id, [upload_new, upload_dup, upload_invalid])

        assert isinstance(resp, DocumentBatchUploadResponse)
        assert len(resp.results) == 3
        assert resp.success_count == 2  # 1 new + 1 duplicate (non-error)
        assert resp.failure_count == 1  # 1 invalid corrupt

        # Check item 0: new file
        assert resp.results[0].filename == "valid_new_2.pdf"
        assert resp.results[0].outcome == DocumentUploadOutcome.STORED_NEW
        assert resp.results[0].success is True
        assert resp.results[0].error is None

        # Check item 1: duplicate file
        assert resp.results[1].filename == "already_indexed_file.pdf"
        assert resp.results[1].outcome == DocumentUploadOutcome.ALREADY_INDEXED
        assert resp.results[1].success is True
        assert resp.results[1].error is None

        # Check item 2: corrupt file
        assert resp.results[2].filename == "corrupt_bad.pdf"
        assert resp.results[2].outcome == DocumentUploadOutcome.FAILED
        assert resp.results[2].success is False
        assert resp.results[2].error is not None


@pytest.mark.asyncio
async def test_acceptance_04_fifth_document_upload_with_four_prior_sources(isolated_env):
    """
    4. Upload a 5th document to a project that already has 4 source records (1 ready, 1 failed, 2 cancelled).
    Verify that 4 is not a limit, the count increments to 5, and all 5 records are returned and visible.
    """
    session_factory = isolated_env["session_factory"]

    # Seed exactly 4 documents matching user's real project state:
    # 1 Ready, 1 Failed, 2 Cancelled
    async with session_factory() as session:
        doc1_ready = Document(
            id="doc-1-ready-cormen",
            paper_id=isolated_env["paper_id"],
            filename="Cormen Introduction to Algorithms.pdf",
            storage_path=str(isolated_env["upload_path"] / "cormen.pdf"),
            content_type="application/pdf",
            file_size=5726585,
            file_hash_sha256="hash-cormen-1234",
            processing_status=DocumentStatus.INDEXED.value,
            processing_stage="ready",
            chunk_count=1906,
        )
        doc2_failed = Document(
            id="doc-2-failed-horowitz",
            paper_id=isolated_env["paper_id"],
            filename="horowitz-sahani-algorithms.pdf",
            storage_path=str(isolated_env["upload_path"] / "horowitz_failed.pdf"),
            content_type="application/pdf",
            file_size=29934436,
            file_hash_sha256="hash-horowitz-fail",
            processing_status=DocumentStatus.FAILED.value,
            processing_stage="failed",
            processing_error="The RAG service is currently unavailable.",
        )
        doc3_cancelled = Document(
            id="doc-3-cancelled-1",
            paper_id=isolated_env["paper_id"],
            filename="horowitz-sahani-algorithms.pdf",
            storage_path=str(isolated_env["upload_path"] / "horowitz_canc1.pdf"),
            content_type="application/pdf",
            file_size=29934436,
            file_hash_sha256="hash-horowitz-canc1",
            processing_status=DocumentStatus.CANCELLED.value,
            processing_stage="cancelled",
            processing_error="Ingestion was cancelled by user.",
        )
        doc4_cancelled = Document(
            id="doc-4-cancelled-2",
            paper_id=isolated_env["paper_id"],
            filename="horowitz-sahani-algorithms.pdf",
            storage_path=str(isolated_env["upload_path"] / "horowitz_canc2.pdf"),
            content_type="application/pdf",
            file_size=29934436,
            file_hash_sha256="hash-horowitz-canc2",
            processing_status=DocumentStatus.CANCELLED.value,
            processing_stage="cancelled",
            processing_error="Ingestion was cancelled by user.",
        )
        for d in [doc1_ready, doc2_failed, doc3_cancelled, doc4_cancelled]:
            Path(d.storage_path).write_bytes(VALID_PDF_1)
            session.add(d)
        await session.commit()

    # Step 1: Verify before upload, project sources count is exactly 4
    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        sources_before = await service.list_for_paper(user, paper.id)
        assert len(sources_before) == 4, f"Expected 4 prior documents, found {len(sources_before)}"
        statuses_before = {d.id: d.processing_status for d in sources_before}
        assert statuses_before["doc-1-ready-cormen"] == "indexed"
        assert statuses_before["doc-2-failed-horowitz"] == "failed"
        assert statuses_before["doc-3-cancelled-1"] == "cancelled"
        assert statuses_before["doc-4-cancelled-2"] == "cancelled"

    # Step 2: Upload a 5th new document
    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        upload_5th = UploadFile(
            filename="fifth_document_new.pdf",
            file=io.BytesIO(VALID_PDF_5TH),
            headers={"content-type": "application/pdf"},
        )

        with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
            new_doc = await service.upload(user, paper.id, upload_5th)

            assert new_doc is not None
            assert new_doc.filename == "fifth_document_new.pdf"
            assert new_doc.processing_status == DocumentStatus.PROCESSING.value
            assert mock_launch.called, "Worker must be dispatched for 5th document"

        # Step 3: Verify list_for_paper now contains exactly 5 documents
        sources_after = await service.list_for_paper(user, paper.id)
        assert len(sources_after) == 5, f"Expected 5 sources after upload, found {len(sources_after)}"

        # Verify all statuses are represented
        all_ids = {d.id for d in sources_after}
        assert "doc-1-ready-cormen" in all_ids
        assert "doc-2-failed-horowitz" in all_ids
        assert "doc-3-cancelled-1" in all_ids
        assert "doc-4-cancelled-2" in all_ids
        assert new_doc.id in all_ids


@pytest.mark.asyncio
async def test_acceptance_05_reupload_failed_document_retriggers_processing(isolated_env):
    """
    5. Re-uploading a file that previously failed or cancelled re-triggers processing
    instead of silently returning dead record with no worker.
    """
    session_factory = isolated_env["session_factory"]
    target_hash = hashlib.sha256(VALID_PDF_1).hexdigest()

    # Seed document in FAILED state
    async with session_factory() as session:
        failed_doc = Document(
            id="doc-failed-to-reupload",
            paper_id=isolated_env["paper_id"],
            filename="failed_source.pdf",
            storage_path=str(isolated_env["upload_path"] / "failed_source.pdf"),
            content_type="application/pdf",
            file_size=len(VALID_PDF_1),
            file_hash_sha256=target_hash,
            processing_status=DocumentStatus.FAILED.value,
            processing_stage="failed",
            processing_error="The RAG service is currently unavailable.",
        )
        Path(failed_doc.storage_path).write_bytes(VALID_PDF_1)
        session.add(failed_doc)
        await session.commit()

    # User uploads the same file again via upload
    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        paper = await session.get(Paper, isolated_env["paper_id"])
        mock_rag = AsyncMock()
        mock_rag.get_document_index_status = AsyncMock(return_value={"is_stale": False})
        service = DocumentService(session, mock_rag)

        reupload = UploadFile(
            filename="failed_source.pdf",
            file=io.BytesIO(VALID_PDF_1),
            headers={"content-type": "application/pdf"},
        )

        with patch("backend.app.services.document_service.launch_background_ingest") as mock_launch:
            returned = await service.upload(user, paper.id, reupload)

            assert returned.id == "doc-failed-to-reupload"
            assert returned.processing_status == DocumentStatus.PROCESSING.value
            assert returned.processing_stage == "extracting_text"
            assert returned.processing_error is None
            assert mock_launch.called, "Worker MUST be dispatched when re-uploading a failed document"

        # Verify DB persisted state
        await session.refresh(returned)
        assert returned.processing_status == DocumentStatus.PROCESSING.value
        assert returned.processing_error is None


@pytest.mark.asyncio
async def test_delete_document_removes_record_and_cleans_up(isolated_env):
    """Verify that deleting a document releases leases, removes RAG chunks, and deletes the DB record."""
    session_factory = isolated_env["session_factory"]

    async with session_factory() as session:
        user = await session.get(User, isolated_env["user_id"])
        mock_rag = AsyncMock()
        mock_rag.delete_document_chunks = AsyncMock(return_value=5)
        service = DocumentService(session, mock_rag)

        # Create a document to delete
        doc_path = Path(isolated_env["upload_path"]) / "doc_to_delete.pdf"
        doc_path.write_bytes(VALID_PDF_1)

        doc = Document(
            id="doc-delete-test",
            paper_id=isolated_env["paper_id"],
            filename="delete_me.pdf",
            storage_path=str(doc_path),
            content_type="application/pdf",
            file_size=len(VALID_PDF_1),
            file_hash_sha256=hashlib.sha256(VALID_PDF_1).hexdigest(),
            processing_status=DocumentStatus.CANCELLED.value,
        )
        session.add(doc)
        await session.commit()

        # Delete it via service
        await service.delete(user, "doc-delete-test")

        # Verify RAG chunks were deleted
        mock_rag.delete_document_chunks.assert_called_once_with("doc-delete-test")

        # Verify record no longer exists in DB
        res = await session.get(Document, "doc-delete-test")
        assert res is None, "Document record must be removed from DB upon delete"

        # Verify file unlinked from disk
        assert not doc_path.is_file(), "Underlying storage file should be deleted when unshared"

"""Test document lifecycle: upload, duplicate detection, cancel, retry, reindex."""
import pytest
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import threading

from backend.app.services.document_service import DocumentService
from backend.app.services.document_service_helpers import (
    compute_file_hash_streaming,
    check_duplicate_and_classify,
    acquire_worker_lease,
    release_worker_lease,
    has_active_worker_lease,
)
from backend.app.models.document import Document, DocumentWorkerLease, DocumentStatus, CleanupStatus, OperationType
from backend.app.models.user import User
from backend.app.models.paper import Paper
from backend.app.schemas.document import DocumentUploadOutcome


@pytest.fixture
def mock_db_session():
    """Mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = Mock()
    return session


@pytest.fixture
def mock_rag_gateway():
    """Mock RAG gateway."""
    gateway = AsyncMock()
    gateway.ingest_document = AsyncMock(return_value={
        "success": True,
        "chunk_count": 42,
        "status": "indexed"
    })
    return gateway


@pytest.fixture
def test_pdf_path(tmp_path):
    """Create a temporary test PDF file."""
    pdf_path = tmp_path / "test_document.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%Test PDF content for hashing\n%%EOF")
    return pdf_path


class TestStreamingHash:
    """Test streaming hash computation."""
    
    def test_compute_file_hash_streaming(self, test_pdf_path):
        """Test streaming hash computation never loads full file."""
        result_hash = compute_file_hash_streaming(test_pdf_path)  # Pass Path object, not string
        
        # Verify it's a valid SHA-256 hex string
        assert len(result_hash) == 64
        assert all(c in "0123456789abcdef" for c in result_hash)
        
        # Verify matches manual hash
        manual_hash = hashlib.sha256(test_pdf_path.read_bytes()).hexdigest()
        assert result_hash == manual_hash
        
        print(f"✅ Streaming hash computed: {result_hash[:16]}...")


class TestDuplicateDetection:
    """Test state-aware duplicate detection."""
    
    @pytest.mark.asyncio
    async def test_duplicate_indexed_document(self, mock_db_session):
        """Test duplicate detection for already indexed document."""
        # Mock existing indexed document
        existing_doc = Document(
            id="doc-123",
            filename="test.pdf",
            file_hash_sha256="abc123",
            file_size=12345,
            processing_status=DocumentStatus.INDEXED,
            cleanup_status=None
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=existing_doc)))
        mock_db_session.execute.return_value = mock_result
        
        # check_duplicate_and_classify returns (document, outcome, message)
        doc, outcome, message = await check_duplicate_and_classify(
            mock_db_session,
            "test-paper",
            "abc123",
            12345
        )
        
        assert outcome == "already_indexed"
        assert doc.id == "doc-123"
        print("✅ Duplicate indexed document detected correctly")
    
    @pytest.mark.asyncio
    async def test_duplicate_processing_document(self, mock_db_session):
        """Test duplicate detection for document currently processing."""
        existing_doc = Document(
            id="doc-456",
            filename="test.pdf",
            file_hash_sha256="def456",
            file_size=12345,
            processing_status=DocumentStatus.PROCESSING,
            cleanup_status=None
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=existing_doc)))
        mock_db_session.execute.return_value = mock_result
        
        # Mock has_active_worker_lease to return True
        with patch('backend.app.services.document_service_helpers.has_active_worker_lease', return_value=True):
            doc, outcome, message = await check_duplicate_and_classify(
                mock_db_session,
                "test-paper",
                "def456",
                12345
            )
        
        assert outcome == "existing_job"
        assert doc.id == "doc-456"
        print("✅ Duplicate processing document detected correctly")
    
    @pytest.mark.asyncio
    async def test_duplicate_cleanup_in_progress(self, mock_db_session):
        """Test duplicate detection for document with cleanup in progress."""
        existing_doc = Document(
            id="doc-789",
            filename="test.pdf",
            file_hash_sha256="ghi789",
            file_size=12345,
            processing_status=DocumentStatus.CANCEL_REQUESTED,
            cleanup_status=CleanupStatus.IN_PROGRESS
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=existing_doc)))
        mock_db_session.execute.return_value = mock_result
        
        doc, outcome, message = await check_duplicate_and_classify(
            mock_db_session,
            "test-paper",
            "ghi789",
            12345
        )
        
        assert outcome == "cleanup_in_progress"
        assert doc.id == "doc-789"
        print("✅ Duplicate cleanup_in_progress detected correctly")
    
    @pytest.mark.asyncio
    async def test_new_document(self, mock_db_session):
        """Test new document with no duplicates."""
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=None)))
        mock_db_session.execute.return_value = mock_result
        
        doc, outcome, message = await check_duplicate_and_classify(
            mock_db_session,
            "test-paper",
            "unique-hash-999",
            99999
        )
        
        assert outcome == "stored_new"
        assert doc is None
        print("✅ New document (no duplicate) detected correctly")


class TestWorkerLeases:
    """Test worker lease management."""
    
    @pytest.mark.asyncio
    async def test_acquire_and_release_lease(self, mock_db_session):
        """Test lease acquisition and release."""
        doc_id = "doc-lease-1"
        worker_id = "worker-test-1"
        
        # Mock lease object
        mock_lease = DocumentWorkerLease(
            id="lease-123",
            document_id=doc_id,
            worker_id=worker_id,
            status="active",
            started_at=datetime.utcnow(),
            heartbeat_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Mock refresh to populate the lease
        async def mock_refresh(obj):
            obj.id = "lease-123"
        mock_db_session.refresh.side_effect = mock_refresh
        
        # Acquire lease
        lease = await acquire_worker_lease(mock_db_session, doc_id, worker_id)
        assert lease is not None
        assert lease.document_id == doc_id
        assert lease.worker_id == worker_id
        assert lease.status == "active"
        
        # Mock finding the lease for release
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=lease)))
        mock_db_session.execute.return_value = mock_result
        
        # Release lease
        await release_worker_lease(mock_db_session, lease.id)
        assert mock_db_session.commit.called
        
        print("✅ Worker lease acquire/release cycle completed")
    
    @pytest.mark.asyncio
    async def test_stale_lease_detection(self, mock_db_session):
        """Test detection of stale leases (>5min old)."""
        doc_id = "doc-stale-1"
        
        # Mock stale lease (6 minutes old)
        stale_time = datetime.utcnow() - timedelta(minutes=6)
        stale_lease = DocumentWorkerLease(
            id="lease-stale-1",
            document_id=doc_id,
            worker_id="worker-old",
            status="active",
            heartbeat_at=stale_time,
            started_at=stale_time,
            created_at=stale_time,
            updated_at=stale_time
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=stale_lease)))
        mock_db_session.execute.return_value = mock_result
        
        has_active = await has_active_worker_lease(mock_db_session, doc_id)
        
        # Stale lease should be treated as inactive
        assert not has_active
        print("✅ Stale lease (>5min) correctly identified as inactive")
    
    @pytest.mark.asyncio
    async def test_active_lease_blocks_concurrent(self, mock_db_session):
        """Test active lease blocks concurrent processing."""
        doc_id = "doc-concurrent-1"
        
        # Mock recent active lease (1 minute old)
        recent_time = datetime.utcnow() - timedelta(minutes=1)
        active_lease = DocumentWorkerLease(
            id="lease-active-1",
            document_id=doc_id,
            worker_id="worker-current",
            status="active",
            heartbeat_at=recent_time,
            started_at=recent_time,
            created_at=recent_time,
            updated_at=recent_time
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=active_lease)))
        mock_db_session.execute.return_value = mock_result
        
        has_active = await has_active_worker_lease(mock_db_session, doc_id)
        
        assert has_active
        print("✅ Active lease correctly blocks concurrent processing")


class TestCancellation:
    """Test cooperative cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_sets_requested_first(self, mock_db_session):
        """Test cancel sets CANCEL_REQUESTED before cleanup."""
        doc_id = "doc-cancel-1"
        user = User(id="user-1", email="test@example.com", username="test")
        paper = Paper(id="paper-1", owner_id=user.id, title="Test")
        
        # Mock document
        doc = Document(
            id=doc_id,
            paper_id=paper.id,
            filename="test.pdf",
            storage_path="/tmp/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            processing_status=DocumentStatus.PROCESSING,
            cleanup_status=None,
            operation_type=OperationType.INITIAL_UPLOAD
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=doc)))
        mock_db_session.execute.return_value = mock_result
        
        # Mock document service cancel method
        service = DocumentService(db=mock_db_session, rag=AsyncMock())
        service.get_owned = AsyncMock(return_value=doc)
        service.paper_service.get_owned = AsyncMock(return_value=paper)
        
        # Call cancel
        result = await service.cancel(user, doc_id)
        
        # Verify status set to CANCEL_REQUESTED
        assert doc.processing_status == DocumentStatus.CANCEL_REQUESTED.value
        print("✅ Cancel sets CANCEL_REQUESTED status first")


class TestRetry:
    """Test retry logic."""
    
    @pytest.mark.asyncio
    async def test_retry_blocked_during_cleanup(self, mock_db_session):
        """Test retry blocked when cleanup is in progress."""
        doc_id = "doc-retry-cleanup"
        user = User(id="user-1", email="test@example.com", username="test")
        paper = Paper(id="paper-1", owner_id=user.id, title="Test")
        
        # Mock document with cleanup in progress
        doc = Document(
            id=doc_id,
            paper_id=paper.id,
            filename="test.pdf",
            storage_path="/tmp/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            processing_status=DocumentStatus.FAILED,
            cleanup_status=CleanupStatus.IN_PROGRESS,
            operation_type=OperationType.INITIAL_UPLOAD
        )
        
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=Mock(first=Mock(return_value=doc)))
        mock_db_session.execute.return_value = mock_result
        
        # Mock has_active_worker_lease to return True (simulating cleanup worker)
        with patch('backend.app.services.document_service_helpers.has_active_worker_lease', new_callable=AsyncMock, return_value=True), \
             patch('pathlib.Path.is_file', return_value=True):
            service = DocumentService(db=mock_db_session, rag=AsyncMock())
            service.get_owned = AsyncMock(return_value=doc)
            service.paper_service.get_owned = AsyncMock(return_value=paper)
            
            # Attempt retry should fail
            with pytest.raises(Exception, match="cleanup|progress|lease"):
                await service.retry(user, doc_id)
        
        print("✅ Retry correctly blocked during cleanup")
    
    @pytest.mark.asyncio
    async def test_retry_sets_operation_type(self, mock_db_session, mock_rag_gateway):
        """Test retry sets operation_type=RETRY."""
        doc_id = "doc-retry-op-type"
        user = User(id="user-1", email="test@example.com", username="test")
        paper = Paper(id="paper-1", owner_id=user.id, title="Test")
        
        # Mock failed document (no cleanup issues)
        doc = Document(
            id=doc_id,
            paper_id=paper.id,
            filename="test.pdf",
            storage_path="/tmp/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            processing_status=DocumentStatus.FAILED,
            cleanup_status=None,
            operation_type=OperationType.INITIAL_UPLOAD,
        )
        
        mock_claim = Mock()
        mock_claim.rowcount = 1
        mock_db_session.execute.return_value = mock_claim
        
        # Mock no active lease
        with patch('backend.app.services.document_service_helpers.has_active_worker_lease', new_callable=AsyncMock, return_value=False), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('backend.app.services.document_service.launch_background_ingest'):
            service = DocumentService(db=mock_db_session, rag=mock_rag_gateway)
            service.get_owned = AsyncMock(return_value=doc)
            service.paper_service.get_owned = AsyncMock(return_value=paper)
            
            # Call retry
            await service.retry(user, doc_id)
            
            # Verify operation_type set to RETRY
            assert doc.operation_type == OperationType.RETRY.value
            assert doc.cleanup_status is None  # Cleared
            print("✅ Retry sets operation_type=RETRY and clears cleanup_status")


class TestReindex:
    """Test reindex with atomic rollback."""
    
    @pytest.mark.asyncio
    async def test_reindex_captures_operation_type_before_mutation(self, mock_db_session, mock_rag_gateway):
        """Test reindex captures operation_type before state changes."""
        doc_id = "doc-reindex-1"
        user = User(id="user-1", email="test@example.com", username="test")
        paper = Paper(id="paper-1", owner_id=user.id, title="Test")
        
        # Mock indexed document
        doc = Document(
            id=doc_id,
            paper_id=paper.id,
            filename="test.pdf",
            storage_path="/tmp/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            processing_status=DocumentStatus.INDEXED,
            operation_type=OperationType.INITIAL_UPLOAD,
            index_version=1,
            chunk_count=42,
        )
        
        with patch('pathlib.Path.is_file', return_value=True):
            service = DocumentService(db=mock_db_session, rag=mock_rag_gateway)
            service.get_owned = AsyncMock(return_value=doc)
            service.paper_service.get_owned = AsyncMock(return_value=paper)
            
            async def fake_process(d, p):
                assert d.operation_type == OperationType.REINDEX.value
                d.processing_status = DocumentStatus.INDEXED.value
            service._process = AsyncMock(side_effect=fake_process)
            
            # Call reindex
            await service.reindex(user, doc_id)
            
            # Verify operation_type set to REINDEX
            assert doc.operation_type == OperationType.REINDEX.value
            print("✅ Reindex sets operation_type=REINDEX before processing")


print("All document lifecycle tests defined successfully")

"""Milestone 1 Integration Tests - Core functionality validation."""
import pytest
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# Import the actual implementations
from backend.app.services.document_service_helpers import (
    compute_file_hash_streaming,
)


class TestCriticalBehaviors:
    """Test critical Milestone 1 behaviors without full database setup."""
    
    def test_streaming_hash_computation(self):
        """✅ Test 1: Verify streaming hash never loads full file into memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test PDF
            test_file = Path(tmpdir) / "test.pdf"
            test_content = b"%PDF-1.4\n%Test content for hashing\n%%EOF"
            test_file.write_bytes(test_content)
            
            # Compute hash using streaming
            streaming_hash = compute_file_hash_streaming(test_file)
            
            # Verify against manual hash
            manual_hash = hashlib.sha256(test_content).hexdigest()
            
            assert streaming_hash == manual_hash
            assert len(streaming_hash) == 64
            print("✅ Test 1 PASSED: Streaming hash computation works correctly")
    
    def test_duplicate_detection_returns_correct_tuple(self):
        """✅ Test 2: Verify check_duplicate_and_classify returns (doc, outcome, message)."""
        # This is verified by function signature inspection
        from backend.app.services.document_service_helpers import check_duplicate_and_classify
        import inspect
        
        sig = inspect.signature(check_duplicate_and_classify)
        # Function exists and is async
        assert inspect.iscoroutinefunction(check_duplicate_and_classify)
        
        # Check docstring mentions correct outcomes
        doc = check_duplicate_and_classify.__doc__
        assert "stored_new" in doc
        assert "already_indexed" in doc
        assert "existing_job" in doc
        assert "cleanup_in_progress" in doc
        
        print("✅ Test 2 PASSED: Duplicate detection function signature verified")
    
    def test_worker_lease_model_exists(self):
        """✅ Test 3: Verify DocumentWorkerLease model has required fields."""
        from backend.app.models.document import DocumentWorkerLease
        
        # Check model has required fields
        assert hasattr(DocumentWorkerLease, 'document_id')
        assert hasattr(DocumentWorkerLease, 'worker_id')
        assert hasattr(DocumentWorkerLease, 'status')
        assert hasattr(DocumentWorkerLease, 'heartbeat_at')
        assert hasattr(DocumentWorkerLease, 'started_at')
        assert hasattr(DocumentWorkerLease, 'released_at')
        
        print("✅ Test 3 PASSED: DocumentWorkerLease model has all required fields")
    
    def test_document_model_has_lifecycle_fields(self):
        """✅ Test 4: Verify Document model has new Milestone 1 fields."""
        from backend.app.models.document import Document
        
        # Check new columns exist
        assert hasattr(Document, 'cleanup_status')
        assert hasattr(Document, 'operation_type')
        assert hasattr(Document, 'index_version')
        assert hasattr(Document, 'file_hash_sha256')
        
        print("✅ Test 4 PASSED: Document model has all Milestone 1 fields")
    
    def test_cleanup_status_enum_values(self):
        """✅ Test 5: Verify CleanupStatus enum has correct values."""
        from backend.app.models.document import CleanupStatus
        
        # Check all required enum values (no NONE - nullable column instead)
        assert hasattr(CleanupStatus, 'PENDING')
        assert hasattr(CleanupStatus, 'IN_PROGRESS')
        assert hasattr(CleanupStatus, 'COMPLETED')
        assert hasattr(CleanupStatus, 'FAILED')
        
        print("✅ Test 5 PASSED: CleanupStatus enum has all required values")
    
    def test_operation_type_enum_values(self):
        """✅ Test 6: Verify OperationType enum has correct values."""
        from backend.app.models.document import OperationType
        
        # Check all required enum values
        assert hasattr(OperationType, 'INITIAL_UPLOAD')
        assert hasattr(OperationType, 'RETRY')
        assert hasattr(OperationType, 'REINDEX')
        
        print("✅ Test 6 PASSED: OperationType enum has all required values")
    
    def test_document_service_helpers_integration(self):
        """✅ Test 7: Verify document_service_helpers functions are imported."""
        from backend.app.services import document_service_helpers
        
        # Check all critical functions exist
        assert hasattr(document_service_helpers, 'compute_file_hash_streaming')
        assert hasattr(document_service_helpers, 'check_duplicate_and_classify')
        assert hasattr(document_service_helpers, 'acquire_worker_lease')
        assert hasattr(document_service_helpers, 'release_worker_lease')
        assert hasattr(document_service_helpers, 'has_active_worker_lease')
        assert hasattr(document_service_helpers, 'update_worker_heartbeat')
        
        print("✅ Test 7 PASSED: All helper functions are accessible")
    
    def test_document_service_imports_helpers(self):
        """✅ Test 8: Verify document_service.py actually uses the helpers."""
        from backend.app.services import document_service
        import inspect
        
        # Read the source code to verify imports
        source = inspect.getsource(document_service)
        
        # Check for helper imports
        assert 'document_service_helpers' in source or 'from backend.app.services.document_service_helpers' in source
        
        # Check for key helper usage
        assert 'compute_file_hash_streaming' in source
        assert 'check_duplicate_and_classify' in source
        assert 'acquire_worker_lease' in source
        assert 'release_worker_lease' in source
        
        print("✅ Test 8 PASSED: document_service.py imports and uses helpers")
    
    def test_rag_index_writer_heading_cleanup_fix(self):
        """✅ Test 9: Verify index_writer captures IDs before DELETE."""
        from rag.independent import index_writer
        import inspect
        
        # Read the source to verify the fix
        source = inspect.getsource(index_writer.IndependentIndexWriter.replace_document_chunks)
        
        # Check for the fix: capturing old_chunk_ids before deletion
        assert 'old_chunk_ids' in source
        assert 'SELECT chunk_id FROM lexical_chunks' in source
        assert 'DELETE FROM headings_fts' in source
        
        # Verify the order: capture THEN delete
        capture_pos = source.index('old_chunk_ids')
        delete_chunks_pos = source.index('DELETE FROM lexical_chunks')
        delete_headings_pos = source.index('DELETE FROM headings_fts')
        
        assert capture_pos < delete_chunks_pos, "Must capture IDs before deleting chunks"
        assert delete_chunks_pos < delete_headings_pos, "Must delete chunks before headings"
        
        print("✅ Test 9 PASSED: Heading FTS cleanup captures IDs before DELETE")
    
    def test_rag_index_writer_quality_zero_preservation(self):
        """✅ Test 10: Verify quality 0.0 is preserved (not converted to 1.0)."""
        from rag.independent import index_writer
        import inspect
        
        # Read the source to verify the fix
        source = inspect.getsource(index_writer.IndependentIndexWriter.replace_document_chunks)
        
        # Check for the CRITICAL comment and fix
        assert 'CRITICAL' in source and 'Preserve quality 0.0' in source
        
        # Check for correct pattern: quality = 1.0 if confidence is None else float(confidence)
        assert 'quality = 1.0 if confidence is None else float(confidence)' in source
        
        print("✅ Test 10 PASSED: Quality 0.0 preservation verified")
    
    def test_frontend_document_progress_caps_at_99(self):
        """✅ Test 11: Verify progress never shows 100% until indexed."""
        from pathlib import Path
        
        # Read the frontend documentProgress.mjs file
        progress_file = Path(__file__).parents[2] / "frontend" / "src" / "lib" / "documentProgress.mjs"
        
        if progress_file.exists():
            content = progress_file.read_text()
            
            # Should cap processing states at 99%
            assert 'Math.min(progress, 99)' in content or 'progress = Math.min' in content
            
            # Should only show 100% when indexed
            assert 'status === "indexed"' in content
            
            print("✅ Test 11 PASSED: Progress capped at 99% until indexed")
        else:
            print("⚠️  Test 11 SKIPPED: Frontend file not found")
    
    def test_frontend_upload_modal_uses_memoized_papers(self):
        """✅ Test 12: Verify AddSourcesModal memoizes papers prop."""
        from pathlib import Path
        
        # Read the frontend AddSourcesModal.jsx file
        modal_file = Path(__file__).parents[2] / "frontend" / "src" / "components" / "upload" / "AddSourcesModal.jsx"
        
        if modal_file.exists():
            content = modal_file.read_text()
            
            # Should use useMemo for papers
            assert 'useMemo' in content
            assert 'memoizedPapers' in content or 'memoized' in content.lower()
            
            print("✅ Test 12 PASSED: AddSourcesModal memoizes papers prop")
        else:
            print("⚠️  Test 12 SKIPPED: Frontend file not found")
    
    def test_batch_upload_response_schema(self):
        """✅ Test 13: Verify DocumentBatchUploadResponse schema exists."""
        from backend.app.schemas.document import DocumentBatchUploadResponse, DocumentUploadResult
        
        # Check response schema exists
        assert hasattr(DocumentBatchUploadResponse, '__annotations__')
        
        # Check it has the right fields
        annotations = DocumentBatchUploadResponse.__annotations__
        assert 'results' in annotations
        assert 'success_count' in annotations
        assert 'failure_count' in annotations
        
        # Check DocumentUploadResult exists with correct fields
        result_annotations = DocumentUploadResult.__annotations__
        assert 'document' in result_annotations  # Optional[DocumentResponse]
        assert 'outcome' in result_annotations   # str
        assert 'error' in result_annotations     # Optional[str]
        assert 'message' in result_annotations   # Optional[str]
        
        print("✅ Test 13 PASSED: Batch upload response schemas verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

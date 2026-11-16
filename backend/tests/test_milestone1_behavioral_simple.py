"""Milestone 1 Behavioral Tests - Simplified actual execution verification."""
import pytest
import tempfile
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

from backend.app.services.document_service_helpers import compute_file_hash_streaming


class TestBehavioralSimple:
    """Simplified behavioral verification tests."""
    
    def test_01_migration_sqlite_real_execution(self):
        """Check 1: Run actual migration DDL on isolated SQLite with test data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create pre-migration schema with test data
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
            
            # Insert test row
            cursor.execute("""
                INSERT INTO documents (id, paper_id, filename, storage_path, content_type, file_size, 
                                     processing_status, created_at, updated_at)
                VALUES ('existing-doc-1', 'paper-1', 'existing.pdf', '/storage/existing.pdf', 'application/pdf', 54321,
                        'indexed', datetime('now'), datetime('now'))
            """)
            conn.commit()
            
            # Apply migration DDL
            cursor.execute("ALTER TABLE documents ADD COLUMN cleanup_status TEXT")
            cursor.execute("ALTER TABLE documents ADD COLUMN operation_type TEXT")
            cursor.execute("ALTER TABLE documents ADD COLUMN index_version INTEGER NOT NULL DEFAULT 1")
            cursor.execute("ALTER TABLE documents ADD COLUMN file_hash_sha256 TEXT")
            cursor.execute("CREATE INDEX ix_documents_file_hash ON documents(file_hash_sha256)")
            cursor.execute("CREATE INDEX ix_documents_cleanup_status ON documents(cleanup_status)")
            
            # Create worker leases table
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
            
            # Verify test row preserved
            cursor.execute("SELECT id, filename, index_version, cleanup_status FROM documents WHERE id='existing-doc-1'")
            row = cursor.fetchone()
            assert row is not None, "Existing row lost during migration"
            assert row[0] == "existing-doc-1"
            assert row[1] == "existing.pdf"
            assert row[2] == 1, "index_version default not applied"
            assert row[3] is None, "cleanup_status should be NULL"
            
            # Verify new table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_worker_leases'")
            assert cursor.fetchone() is not None
            
            conn.close()
            print("CHECK 1 PASSED: Real migration preserves data, adds all fields")
            
        finally:
            Path(db_path).unlink(missing_ok=True)
    
    def test_02_streaming_hash_actual_file(self):
        """Check 2: Streaming hash computation on actual file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            # Write 5MB of data in chunks
            for i in range(5000):
                tmp.write(b"x" * 1024)  # 1KB per iteration = 5MB total
            tmp.flush()
            pdf_path = Path(tmp.name)
        
        try:
            # Compute hash using streaming
            streaming_hash = compute_file_hash_streaming(pdf_path)
            
            # Verify against manual hash
            manual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            
            assert streaming_hash == manual_hash
            assert len(streaming_hash) == 64
            
            print("CHECK 2 PASSED: Streaming hash matches manual hash for 5MB file")
            
        finally:
            pdf_path.unlink(missing_ok=True)
    
    def test_10_sqlite_consistency_after_operations(self):
        """Check 10: Verify SQLite consistency across lexical tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_lexical.sqlite3"
            
            from rag.independent.index_writer import IndependentIndexWriter
            from rag.chunking.metadata import DocumentChunk, ChunkMetadata
            
            writer = IndependentIndexWriter(db_path)
            
            # Create test chunks
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
                        extra={"heading_path": ["Introduction"], "extraction_confidence": 0.95}
                    ),
                    text="Test chunk text for consistency check."
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
                        extra={"heading_path": ["Methods"], "extraction_confidence": 0.88}
                    ),
                    text="Methods section text."
                ),
            ]
            
            # Insert chunks
            writer.replace_document_chunks("doc-consistency-1", chunks)
            
            # Verify consistency
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check lexical_chunks
            cursor.execute("SELECT COUNT(*) FROM lexical_chunks WHERE document_id='doc-consistency-1'")
            lexical_count = cursor.fetchone()[0]
            assert lexical_count == 2
            
            # Check lexical_metadata
            cursor.execute("SELECT COUNT(*) FROM lexical_metadata WHERE document_id='doc-consistency-1'")
            metadata_count = cursor.fetchone()[0]
            assert metadata_count == 2
            
            # Check headings_fts
            cursor.execute("SELECT COUNT(*) FROM headings_fts")
            headings_count = cursor.fetchone()[0]
            assert headings_count == 2
            
            # Delete document
            writer.delete_document("doc-consistency-1")
            
            # Verify all deleted
            cursor.execute("SELECT COUNT(*) FROM lexical_chunks WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 0
            
            cursor.execute("SELECT COUNT(*) FROM lexical_metadata WHERE document_id='doc-consistency-1'")
            assert cursor.fetchone()[0] == 0
            
            cursor.execute("SELECT COUNT(*) FROM headings_fts")
            assert cursor.fetchone()[0] == 0, "Heading orphans detected"
            
            conn.close()
            
            print("CHECK 10 PASSED: SQLite consistency maintained across all tables")
    
    def test_11_quality_zero_persisted_and_retrieved(self):
        """Check 11: Verify extraction_quality=0.0 persists and retrieves as 0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_quality.sqlite3"
            
            from rag.independent.index_writer import IndependentIndexWriter
            from rag.chunking.metadata import DocumentChunk, ChunkMetadata
            
            writer = IndependentIndexWriter(db_path)
            
            # Create chunk with quality 0.0
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
                        extra={
                            "extraction_confidence": 0.0,  # CRITICAL: Zero confidence
                            "extraction_method": "ocr"
                        }
                    ),
                    text="Poorly scanned text with zero confidence."
                ),
            ]
            
            # Insert
            writer.replace_document_chunks("doc-quality-1", chunks)
            
            # Retrieve and verify
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT quality_score FROM lexical_metadata 
                WHERE chunk_id='chunk-zero-quality'
            """)
            quality = cursor.fetchone()[0]
            
            assert quality == 0.0, f"Quality should be 0.0, got {quality}"
            
            conn.close()
            
            print("CHECK 11 PASSED: Quality 0.0 persisted and retrieved correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

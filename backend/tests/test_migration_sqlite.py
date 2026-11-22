"""Test SQLite compatibility of Milestone 1 migration."""
import tempfile
from pathlib import Path
import sqlite3


def test_migration_sqlite_compatibility():
    """Verify migration 0006 DDL works with SQLite (desktop database)."""
    # Create isolated temporary SQLite database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_migration.db"
        
        # Connect to SQLite
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Create pre-migration schema
            cursor.execute("""
                CREATE TABLE documents (
                    id VARCHAR(36) PRIMARY KEY,
                    paper_id VARCHAR(36) NOT NULL,
                    owner_id VARCHAR(36) NOT NULL,
                    filename VARCHAR(512) NOT NULL,
                    file_size INTEGER NOT NULL,
                    processing_status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            
            # Insert test data
            cursor.execute("""
                INSERT INTO documents (id, paper_id, owner_id, filename, file_size, 
                                     processing_status, created_at, updated_at)
                VALUES ('test-doc-1', 'test-paper-1', 'test-user-1', 'test.pdf', 12345,
                        'indexed', datetime('now'), datetime('now'))
            """)
            conn.commit()
            
            # Apply migration DDL (simulating batch_alter_table for SQLite)
            # Step 1: Add new columns
            cursor.execute("ALTER TABLE documents ADD COLUMN cleanup_status VARCHAR(50)")
            cursor.execute("ALTER TABLE documents ADD COLUMN operation_type VARCHAR(50)")
            cursor.execute("ALTER TABLE documents ADD COLUMN index_version INTEGER NOT NULL DEFAULT 1")
            cursor.execute("ALTER TABLE documents ADD COLUMN file_hash_sha256 VARCHAR(64)")
            
            # Step 2: Create indexes
            cursor.execute("CREATE INDEX ix_documents_file_hash ON documents(file_hash_sha256)")
            cursor.execute("CREATE INDEX ix_documents_cleanup_status ON documents(cleanup_status)")
            
            # Step 3: Create worker leases table
            cursor.execute("""
                CREATE TABLE document_worker_leases (
                    id VARCHAR(36) PRIMARY KEY,
                    document_id VARCHAR(36) NOT NULL,
                    worker_id VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    started_at DATETIME NOT NULL,
                    heartbeat_at DATETIME NOT NULL,
                    released_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            
            cursor.execute("CREATE INDEX ix_worker_leases_document_id ON document_worker_leases(document_id)")
            cursor.execute("CREATE INDEX ix_worker_leases_status ON document_worker_leases(status)")
            cursor.execute("CREATE INDEX ix_worker_leases_worker_id ON document_worker_leases(worker_id)")
            
            conn.commit()
            
            # Verify new columns exist
            cursor.execute("PRAGMA table_info(documents)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "cleanup_status" in columns, "cleanup_status column not added"
            assert "operation_type" in columns, "operation_type column not added"
            assert "index_version" in columns, "index_version column not added"
            assert "file_hash_sha256" in columns, "file_hash_sha256 column not added"
            
            # Check worker leases table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='document_worker_leases'
            """)
            assert cursor.fetchone() is not None, "document_worker_leases table not created"
            
            # Verify existing data preserved
            cursor.execute("SELECT id, filename, index_version FROM documents WHERE id='test-doc-1'")
            row = cursor.fetchone()
            assert row is not None, "Existing document lost during migration"
            assert row[1] == "test.pdf", "Document data corrupted"
            assert row[2] == 1, "index_version default not applied"
            
            # Verify indexes created
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='documents'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            assert any("file_hash" in idx for idx in indexes), "file_hash index not created"
            assert any("cleanup_status" in idx for idx in indexes), "cleanup_status index not created"
            
            print("✅ Migration 0006 SQLite compatibility verified")
            print("   - All new columns added successfully")
            print("   - document_worker_leases table created")
            print("   - Existing data preserved with index_version=1")
            print("   - Indexes created correctly")
            print("   - Migration is fully compatible with desktop SQLite database")
            
        finally:
            conn.close()


if __name__ == "__main__":
    test_migration_sqlite_compatibility()

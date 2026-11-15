"""
Comprehensive Security and Migration Tests for FTS5 Lexical Storage.

Tests:
  1. Fresh installation: VectorRepository creates 12-column FTS5 schema with owner_id UNINDEXED.
  2. Legacy migration: Converts 11-column table to 12-column table with trusted ownership mapping.
  3. Quarantine verification: Orphans and ambiguous mappings are isolated in quarantine table.
  4. Cross-user lexical search parity: Alice only sees Alice's chunks; Bob only sees Bob's.
  5. Idempotency: Re-running migration produces no changes or corruption.
  6. Transactional recovery: Interrupted migration rolls back cleanly with legacy table intact.
"""

import sqlite3
import pytest
from pathlib import Path
from typing import Dict, Any

from rag.chunking.metadata import ChunkMetadata, DocumentChunk
from rag.vectorstore.chroma_client import ChromaClientFactory
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.vector_repository import VectorRepository
from rag.config.settings import settings
from scripts.migrate_fts5_add_owner_id import FTS5MigrationEngine, get_table_columns


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Provide isolated paths for ChromaDB and lexical database."""
    persist_dir = tmp_path / "fts5_test_persist"
    persist_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "chroma_persist_dir", str(persist_dir))
    monkeypatch.setattr(settings, "chroma_collection_name", "test_fts5_isolated")
    monkeypatch.setattr(settings, "chroma_use_http", False)
    ChromaClientFactory.reset_client()
    yield persist_dir
    ChromaClientFactory.reset_client()


def test_fresh_installation_schema_and_isolation(isolated_dirs):
    """Scenario A: Fresh installation initializes FTS5 schema with owner_id from the start."""
    client = ChromaClientFactory.get_client(persist_dir=str(isolated_dirs), force_new=True)
    manager = CollectionManager(client=client)
    vector_repo = VectorRepository(manager)

    db_path = isolated_dirs / "researchlens_lexical.sqlite3"
    
    # Initialize connection which creates the virtual table
    with vector_repo._lexical_connection() as conn:
        cols = get_table_columns(conn, "lexical_chunks")
        assert "owner_id" in cols, f"Fresh installation must have owner_id, got: {cols}"
        assert cols[0] == "chunk_id"
        assert cols[1] == "owner_id"

    # Ingest representative Alice chunk
    chunk_alice = DocumentChunk(
        text="Alice fresh research on deep learning architectures.",
        metadata=ChunkMetadata(
            chunk_id="chunk_fresh_alice_01",
            owner_id="user_alice_fresh",
            paper_id="paper_alice_fresh",
            document_id="doc_alice_fresh",
            section="Methods",
            page_start=1,
            page_end=1,
            chunk_index=0,
            title="Fresh Research",
            filename="alice.pdf",
            locator="Methods p.1",
        )
    )
    vector_repo.upsert_chunks([chunk_alice], [[0.1] * 384])

    # Query with Alice owner_id
    res_alice = vector_repo.query_lexical("learning", where={"owner_id": "user_alice_fresh"})
    assert len(res_alice) == 1
    assert res_alice[0].id == "chunk_fresh_alice_01"

    # Query with Bob owner_id (isolation check)
    res_bob = vector_repo.query_lexical("learning", where={"owner_id": "user_bob_fresh"})
    assert len(res_bob) == 0

    # Query with missing/empty owner_id fails closed
    res_none = vector_repo.query_lexical("learning", where={"owner_id": ""})
    assert len(res_none) == 0

    # Upsert with missing owner_id must raise ValueError immediately
    chunk_no_owner = DocumentChunk(
        text="Unowned chunk text",
        metadata=ChunkMetadata(
            chunk_id="chunk_unowned_01",
            owner_id="",  # Invalid
            paper_id="p1",
            document_id="d1",
            section="s1",
            page_start=1,
            page_end=1,
            chunk_index=0,
            title="t",
            filename="f",
            locator="l",
        )
    )
    with pytest.raises(ValueError, match="owner_id is required"):
        vector_repo.upsert_chunks([chunk_no_owner], [[0.1] * 384])


def test_legacy_installation_migration(tmp_path):
    """Scenario B: Migration converts 11-column legacy database to 12-column with quarantine."""
    db_path = tmp_path / "legacy_lexical.sqlite3"

    # 1. Create legacy table without owner_id (exact 11 columns from older versions)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE VIRTUAL TABLE lexical_chunks USING fts5("
        "chunk_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, "
        "section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, "
        "filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61'"
        ")"
    )

    # Insert test data:
    # - Alice chunk 1 & 2
    # - Bob chunk 1
    # - Orphan chunk (no paper mapping)
    # - Ambiguous chunk (paper mapped to Alice, doc mapped to Bob)
    legacy_rows = [
        ("chunk_a1", "col", "paper_alice", "doc_alice_1", "Intro", 1, 1, "Alice Title", "a1.pdf", "p.1", "Alice quantum algorithms"),
        ("chunk_a2", "col", "paper_alice", "doc_alice_2", "Methods", 2, 2, "Alice Title", "a2.pdf", "p.2", "Alice complexity proofs"),
        ("chunk_b1", "col", "paper_bob", "doc_bob_1", "Methods", 1, 1, "Bob Title", "b1.pdf", "p.1", "Bob cryogenic experiments"),
        ("chunk_orphan", "col", "paper_unknown", "doc_unknown", "Notes", 1, 1, "Unknown", "u.pdf", "p.1", "Orphaned quantum text"),
        ("chunk_ambig", "col", "paper_alice", "doc_bob_conflict", "Discussion", 3, 3, "Mixed", "m.pdf", "p.3", "Ambiguous quantum text"),
    ]
    conn.executemany(
        "INSERT INTO lexical_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        legacy_rows,
    )
    conn.commit()
    conn.close()

    # Trusted mappings
    paper_owners = {
        "paper_alice": "user_alice_uuid",
        "paper_bob": "user_bob_uuid",
    }
    doc_owners = {
        "doc_alice_1": "user_alice_uuid",
        "doc_alice_2": "user_alice_uuid",
        "doc_bob_1": "user_bob_uuid",
        "doc_bob_conflict": "user_bob_uuid",  # Causes contradiction with paper_alice
    }

    engine = FTS5MigrationEngine(
        db_path=db_path,
        paper_owners=paper_owners,
        doc_owners=doc_owners,
    )

    # 2. Test Dry-Run (demonstrably non-mutating)
    dry_run_plan = engine.run_dry_run()
    assert dry_run_plan["status"] == "READY_FOR_MIGRATION"
    stats = dry_run_plan["statistics"]
    assert stats["total_legacy_rows"] == 5
    assert stats["confident_count"] == 3  # a1, a2, b1
    assert stats["orphan_count"] == 1     # orphan
    assert stats["ambiguous_count"] == 1  # ambig
    assert stats["distinct_owners"] == 2  # Alice, Bob

    # Verify db was NOT mutated by dry-run
    conn = sqlite3.connect(db_path)
    cols_after_dry = get_table_columns(conn, "lexical_chunks")
    assert "owner_id" not in cols_after_dry
    conn.close()

    # 3. Test Apply Mode
    apply_result = engine.run_apply()
    assert apply_result["status"] == "SUCCESS"
    assert apply_result["migrated_rows"] == 3
    assert apply_result["quarantined_rows"] == 2
    assert apply_result["total_rows"] == 5

    # 4. Verify post-migration database state
    conn = sqlite3.connect(db_path)
    migrated_cols = get_table_columns(conn, "lexical_chunks")
    assert "owner_id" in migrated_cols
    assert migrated_cols[1] == "owner_id"

    # Check quarantine table
    quarantine_rows = conn.execute("SELECT chunk_id, quarantine_reason FROM lexical_chunks_quarantine").fetchall()
    assert len(quarantine_rows) == 2
    reasons = {r[0]: r[1] for r in quarantine_rows}
    assert "orphan" in reasons["chunk_orphan"]
    assert "ambiguous" in reasons["chunk_ambig"]

    # Check backup table
    backup_count = conn.execute("SELECT count(*) FROM lexical_chunks_pre_owner_migration").fetchone()[0]
    assert backup_count == 5

    # 5. Search Parity & Owner Isolation
    # Alice search
    alice_matches = conn.execute(
        "SELECT chunk_id, owner_id FROM lexical_chunks WHERE lexical_chunks MATCH 'quantum' AND owner_id = ?",
        ("user_alice_uuid",),
    ).fetchall()
    assert len(alice_matches) == 1
    assert alice_matches[0][0] == "chunk_a1"

    # Bob search
    bob_matches = conn.execute(
        "SELECT chunk_id, owner_id FROM lexical_chunks WHERE lexical_chunks MATCH 'cryogenic' AND owner_id = ?",
        ("user_bob_uuid",),
    ).fetchall()
    assert len(bob_matches) == 1
    assert bob_matches[0][0] == "chunk_b1"

    # Bob querying Alice's content yields 0
    cross_matches = conn.execute(
        "SELECT chunk_id FROM lexical_chunks WHERE lexical_chunks MATCH 'quantum' AND owner_id = ?",
        ("user_bob_uuid",),
    ).fetchall()
    assert len(cross_matches) == 0

    conn.close()


def test_migration_idempotency(tmp_path):
    """Scenario C: Re-running migration on migrated database exits safely with no mutations."""
    db_path = tmp_path / "idempotent_test.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE VIRTUAL TABLE lexical_chunks USING fts5("
        "chunk_id UNINDEXED, owner_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, "
        "document_id UNINDEXED, section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, "
        "title UNINDEXED, filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61'"
        ")"
    )
    conn.execute(
        "INSERT INTO lexical_chunks VALUES ('c1', 'user_1', 'col', 'p1', 'd1', 's', 1, 1, 't', 'f', 'l', 'text')"
    )
    conn.commit()
    conn.close()

    engine = FTS5MigrationEngine(db_path=db_path, paper_owners={}, doc_owners={})
    dry_plan = engine.run_dry_run()
    assert dry_plan["status"] == "ALREADY_MIGRATED"

    apply_plan = engine.run_apply()
    assert apply_plan["status"] == "ALREADY_MIGRATED"


def test_interrupted_migration_rollback(tmp_path):
    """Scenario D: Failure during migration transaction rolls back completely."""
    db_path = tmp_path / "rollback_test.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE VIRTUAL TABLE lexical_chunks USING fts5("
        "chunk_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, "
        "section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, "
        "filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61'"
        ")"
    )
    conn.execute(
        "INSERT INTO lexical_chunks VALUES ('c1', 'col', 'p1', 'd1', 's', 1, 1, 't', 'f', 'l', 'text original')"
    )
    conn.commit()
    conn.close()

    # Migration engine with corrupted behavior simulated by monkeypatching
    engine = FTS5MigrationEngine(db_path=db_path, paper_owners={"p1": "owner_1"}, doc_owners={})

    # Cause an intentional error right before table rename
    orig_analyze = engine.analyze_records
    def mock_analyze(c):
        records, quarantined, stats = orig_analyze(c)
        # Corrupt stats to cause ValueError during integrity check
        stats["total_legacy_rows"] = 999
        return records, quarantined, stats

    engine.analyze_records = mock_analyze

    with pytest.raises(ValueError, match="Conservation check failed"):
        engine.run_apply()

    # Verify original table is completely intact
    conn = sqlite3.connect(db_path)
    cols = get_table_columns(conn, "lexical_chunks")
    assert "owner_id" not in cols
    row = conn.execute("SELECT chunk_id, text FROM lexical_chunks").fetchone()
    assert row[0] == "c1"
    assert row[1] == "text original"
    conn.close()


def test_copied_developer_database_migration_revalidation(tmp_path):
    """Scenario E: Real-world revalidation using an isolated copy of the developer database.
    
    Verifies that the actual 6,818 rows from the developer store migrate cleanly on a copy:
      - 4,355 real document chunks receive authoritative owner_id (4526f09d-ae50-47d8-8a73-ffe73e3dc0dd)
      - 2,463 ephemeral benchmark and test chunks are safely quarantined
      - Search parity and cross-user isolation are strictly preserved
      - The persistent developer database is demonstrably untouched
    """
    import shutil
    from scripts.migrate_fts5_add_owner_id import load_trusted_mappings_from_json

    live_db = Path(".chroma/researchlens_lexical.sqlite3")
    if not live_db.exists():
        pytest.skip(".chroma/researchlens_lexical.sqlite3 not present; skipping copy revalidation.")

    mapping_file = Path("trusted_ownership_export.json")
    if not mapping_file.exists():
        pytest.skip("trusted_ownership_export.json not present; skipping copy revalidation.")

    # 1. Create an isolated copy in tmp_path
    copied_db = tmp_path / "researchlens_lexical_copy.sqlite3"
    shutil.copy2(live_db, copied_db)

    # Verify original database metadata before test
    live_conn = sqlite3.connect(f"file:{live_db.resolve()}?mode=ro", uri=True)
    live_cols_before = get_table_columns(live_conn, "lexical_chunks")
    live_count_before = live_conn.execute("SELECT count(*) FROM lexical_chunks").fetchone()[0]
    live_conn.close()

    if "owner_id" in live_cols_before:
        # Live database is already migrated with owner_id
        assert "owner_id" in live_cols_before
        assert live_count_before == 4355
        return

    assert "owner_id" not in live_cols_before
    assert live_count_before == 6818

    # 2. Run Migration on the Copied Database
    paper_owners, doc_owners = load_trusted_mappings_from_json(mapping_file)
    engine = FTS5MigrationEngine(
        db_path=copied_db,
        paper_owners=paper_owners,
        doc_owners=doc_owners,
    )

    # Dry-run on copy
    plan = engine.run_dry_run()
    assert plan["status"] == "READY_FOR_MIGRATION"
    assert plan["statistics"]["total_legacy_rows"] == 6818
    assert plan["statistics"]["confident_count"] == 4355
    assert plan["statistics"]["orphan_count"] == 2463
    assert plan["statistics"]["ambiguous_count"] == 0
    assert plan["statistics"]["distinct_owners"] == 1

    # Apply on copy
    res = engine.run_apply()
    assert res["status"] == "SUCCESS"
    assert res["migrated_rows"] == 4355
    assert res["quarantined_rows"] == 2463
    assert res["total_rows"] == 6818

    # 3. Verify Copied Database Integrity
    conn = sqlite3.connect(copied_db)
    migrated_cols = get_table_columns(conn, "lexical_chunks")
    assert "owner_id" in migrated_cols
    assert migrated_cols[1] == "owner_id"

    # Confirm all 4,355 rows carry authoritative owner
    authorized_owner = "4526f09d-ae50-47d8-8a73-ffe73e3dc0dd"
    owner_rows = conn.execute(
        "SELECT count(*) FROM lexical_chunks WHERE owner_id = ?", (authorized_owner,)
    ).fetchone()[0]
    assert owner_rows == 4355

    # Confirm zero NULL or empty owner_ids
    empty_owners = conn.execute(
        "SELECT count(*) FROM lexical_chunks WHERE owner_id IS NULL OR trim(owner_id) = ''"
    ).fetchone()[0]
    assert empty_owners == 0

    # 4. Search Parity & Owner Isolation on Copied Database
    # Query for Cormen algorithms by authorized user
    auth_search = conn.execute(
        "SELECT chunk_id, title FROM lexical_chunks WHERE lexical_chunks MATCH 'algorithm' AND owner_id = ?",
        (authorized_owner,),
    ).fetchall()
    assert len(auth_search) > 0, "Authorized owner could not retrieve Cormen algorithm chunks"
    assert "Computer Science" in auth_search[0][1]

    # Query for Cormen algorithms by unauthorized user (attacker)
    unauth_search = conn.execute(
        "SELECT chunk_id FROM lexical_chunks WHERE lexical_chunks MATCH 'algorithm' AND owner_id = ?",
        ("unauthorized_attacker_id",),
    ).fetchall()
    assert len(unauth_search) == 0, "Cross-user isolation failure: unauthorized user accessed chunks"

    # 5. Quarantine Table Verification
    quarantine_count = conn.execute("SELECT count(*) FROM lexical_chunks_quarantine").fetchone()[0]
    assert quarantine_count == 2463
    # Check that test_perf_paper and researchlens_paper chunks are quarantined
    sample_reasons = conn.execute(
        "SELECT DISTINCT quarantine_reason FROM lexical_chunks_quarantine"
    ).fetchall()
    assert len(sample_reasons) == 1
    assert sample_reasons[0][0] == "orphan_no_trusted_owner_mapping"

    # 6. Backup Table Verification
    backup_count = conn.execute("SELECT count(*) FROM lexical_chunks_pre_owner_migration").fetchone()[0]
    assert backup_count == 6818

    # 7. Idempotency Check on Copied Database
    idempotent_plan = engine.run_apply()
    assert idempotent_plan["status"] == "ALREADY_MIGRATED"

    conn.close()

    # 8. Crucial Boundary Check: Confirm Persistent Live DB is 100% Unchanged
    live_conn = sqlite3.connect(f"file:{live_db.resolve()}?mode=ro", uri=True)
    live_cols_after = get_table_columns(live_conn, "lexical_chunks")
    live_count_after = live_conn.execute("SELECT count(*) FROM lexical_chunks").fetchone()[0]
    live_conn.close()

    assert live_cols_after == live_cols_before, "CRITICAL ERROR: Live database columns were mutated!"
    assert live_count_after == live_count_before, "CRITICAL ERROR: Live database count was modified!"


import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.library_service import LibraryService
from rag.independent.index_writer import IndependentIndexWriter


@pytest.fixture
def temp_lexical_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "researchlens_lexical.sqlite3"
    writer = IndependentIndexWriter(db_path=db_file)
    conn = sqlite3.connect(db_file)
    try:
        writer._ensure_schema(conn)
        conn.execute(
            "INSERT INTO lexical_chunks (chunk_id, owner_id, collection_name, paper_id, document_id, section, page_start, page_end, title, filename, locator, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "chunk_test_1",
                "owner_1",
                "default",
                "paper_1",
                "doc_1",
                "Section 1",
                1,
                2,
                "Algorithms",
                "algo.pdf",
                "Section 1 · p.1",
                "Red-black tree insertion is an operation that preserves balance.",
            ),
        )
        conn.execute(
            "INSERT INTO lexical_chunks (chunk_id, owner_id, collection_name, paper_id, document_id, section, page_start, page_end, title, filename, locator, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "chunk_test_2",
                "owner_1",
                "default",
                "paper_1",
                "doc_1",
                "Section 2",
                3,
                4,
                "Algorithms",
                "algo.pdf",
                "Section 2 · p.3",
                "Breadth-first search traverses vertices level by level using a FIFO queue.",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return db_file


def test_atomic_reindex_success(tmp_path: Path, temp_lexical_db: Path):
    temp_dir = tmp_path / "temp_reindex_run"
    temp_dir.mkdir()

    service = LibraryService(target_db_path=temp_lexical_db)
    result = service.reindex_atomic(temp_dir=temp_dir)

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["old_row_count"] == 2
    assert result["new_row_count"] == 2
    assert temp_lexical_db.exists()

    # Verify content in target db after atomic swap
    conn = sqlite3.connect(temp_lexical_db)
    try:
        count = conn.execute("SELECT count(*) FROM lexical_chunks").fetchone()[0]
        assert count == 2
    finally:
        conn.close()


def test_reindex_rollback_on_simulated_interruption(tmp_path: Path, temp_lexical_db: Path):
    temp_dir = tmp_path / "temp_reindex_fail"
    temp_dir.mkdir()

    # Read original data
    conn = sqlite3.connect(temp_lexical_db)
    try:
        orig_count = conn.execute("SELECT count(*) FROM lexical_chunks").fetchone()[0]
        orig_rows = conn.execute("SELECT chunk_id, text FROM lexical_chunks ORDER BY chunk_id").fetchall()
    finally:
        conn.close()

    service = LibraryService(target_db_path=temp_lexical_db)

    with pytest.raises(RuntimeError, match="Simulated interruption mid-reindex"):
        service.reindex_atomic(temp_dir=temp_dir, simulate_failure_before_swap=True)

    # Verify original file remains completely untouched
    assert temp_lexical_db.exists()
    bak_file = temp_lexical_db.with_suffix(".sqlite3.bak")
    assert not bak_file.exists()

    conn = sqlite3.connect(temp_lexical_db)
    try:
        curr_count = conn.execute("SELECT count(*) FROM lexical_chunks").fetchone()[0]
        curr_rows = conn.execute("SELECT chunk_id, text FROM lexical_chunks ORDER BY chunk_id").fetchall()
        assert curr_count == orig_count
        assert curr_rows == orig_rows
    finally:
        conn.close()


def test_reindex_status_polling():
    status = LibraryService.get_status()
    assert "status" in status
    assert "progress" in status


def test_library_reindex_api_endpoints():
    from backend.app.core.dependencies import get_current_user
    from backend.app.models.user import User

    fake_user = User(id="user_admin", email="admin@example.com", username="admin", hashed_password="pw", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        client = TestClient(app)
        res = client.get("/api/v1/library/reindex/status")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data

        res_post = client.post("/api/v1/library/reindex")
        assert res_post.status_code == 200
        post_data = res_post.json()
        assert post_data["status"] in ("running", "completed")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

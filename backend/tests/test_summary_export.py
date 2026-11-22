"""
Unit and integration tests for summary export and ingestion exclusion guard.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from backend.app.services.document_service import is_generated_summary_export
from backend.app.services.paper_service import PaperService
from backend.app.models.paper import Paper
from backend.app.models.user import User


def test_is_generated_summary_export_by_filename(tmp_path: Path):
    # Filename prefix checks
    f1 = tmp_path / "Grounded Summary - Algorithms.md"
    f1.write_text("Some text", encoding="utf-8")
    assert is_generated_summary_export(f1) is True

    f2 = tmp_path / "grounded_summary_test.txt"
    f2.write_text("Some text", encoding="utf-8")
    assert is_generated_summary_export(f2) is True

    f3 = tmp_path / ".summary_cache.json"
    f3.write_text("{}", encoding="utf-8")
    assert is_generated_summary_export(f3) is True


def test_is_generated_summary_export_by_frontmatter(tmp_path: Path):
    # Genuine looking filename but with generated summary header
    f1 = tmp_path / "CustomNotes.md"
    f1.write_text("<!-- researchlens:generated-summary version=1.0 -->\n# Summary", encoding="utf-8")
    assert is_generated_summary_export(f1) is True

    f2 = tmp_path / "Output.txt"
    f2.write_text("researchlens-grounded-summary\nDetailed analysis", encoding="utf-8")
    assert is_generated_summary_export(f2) is True


def test_is_generated_summary_export_allows_genuine_user_files(tmp_path: Path):
    # Genuine user research notes and summaries should NOT be excluded
    f1 = tmp_path / "Summary_of_Algorithms.md"
    f1.write_text("# Chapter 1 Notes\nThis is my personal summary.", encoding="utf-8")
    assert is_generated_summary_export(f1) is False

    f2 = tmp_path / "My_Executive_Summary.txt"
    f2.write_text("Key takeaways from the conference...", encoding="utf-8")
    assert is_generated_summary_export(f2) is False

    f3 = tmp_path / "Cormen_Algorithms_3rd.pdf"
    f3.write_bytes(b"%PDF-1.4...")
    assert is_generated_summary_export(f3) is False


@pytest.mark.asyncio
async def test_export_summary_atomic_write_and_content(tmp_path: Path, monkeypatch):
    # Mock personal research dir to isolated tmp_path
    from backend.app.core import config
    monkeypatch.setattr("backend.app.services.paper_service.get_personal_research_dir", lambda title: tmp_path)

    user = User(id="user-123", email="user@example.com")
    paper = Paper(
        id="paper-456",
        owner_id="user-123",
        title="Algorithms & Data Structures",
        summary_json={
            "paper_id": "paper-456",
            "answer": "### Overview\nThis is a grounded overview of algorithms [S1].\n\n### Key Sections\n- Chapter 1: Foundations [S2]",
            "sources": [
                {
                    "citation_key": "S1",
                    "title": "Introduction to Algorithms",
                    "page": 22,
                    "document_id": "doc-1",
                    "quote": "This book provides a comprehensive introduction.",
                },
                {
                    "citation_key": "S2",
                    "title": "Data Structures in C++",
                    "page": 24,
                    "document_id": "doc-2",
                    "quote": "An algorithm is a finite set of instructions.",
                },
            ],
            "is_stale": False,
        },
    )

    # Mock db and service
    class DummyDB:
        async def execute(self, *args, **kwargs):
            return None
        async def scalar(self, *args, **kwargs):
            return paper

    service = PaperService(db=DummyDB(), rag=None)
    # Stub get_owned to return our test paper
    async def fake_get_owned(u, pid):
        return paper
    monkeypatch.setattr(service, "get_owned", fake_get_owned)

    res = await service.export_summary(user, "paper-456")
    assert res["status"] == "success"
    assert "filename" in res

    exported_file = Path(res["path"])
    assert exported_file.exists()

    # Verify no leftover .tmp file
    tmp_files = list(tmp_path.glob(".*.tmp"))
    assert len(tmp_files) == 0

    content = exported_file.read_text(encoding="utf-8")
    assert "<!-- researchlens:generated-summary version=1.0 -->" in content
    assert "# Grounded Research Summary: Algorithms & Data Structures" in content
    assert "This book provides a comprehensive introduction." in content
    assert "An algorithm is a finite set of instructions." in content
    assert "### [S1] Section" in content
    assert "- **Document:** Introduction to Algorithms" in content
    assert "- **Locator:** Page 22" in content
    assert "### [S2] Section" in content
    assert "- **Document:** Data Structures in C++" in content
    assert "- **Locator:** Page 24" in content

    # And verify the exported file is recognized by our ingestion guard
    assert is_generated_summary_export(exported_file) is True

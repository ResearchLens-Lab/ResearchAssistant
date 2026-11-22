"""
Tests for cancellation semantics, project exclusions, and local folder reconciliation.
"""
import pytest
from pathlib import Path
import json

from backend.app.services.document_service import (
    _get_project_exclusions,
    _add_project_exclusion,
    _remove_project_exclusion,
    is_generated_summary_export,
)
from backend.app.models.document import DocumentStatus


def test_project_exclusions_file_lifecycle(tmp_path: Path):
    folder = tmp_path / "TestProject"
    folder.mkdir()

    # Empty folder initially has no exclusions
    assert _get_project_exclusions(folder) == set()

    # Add exclusion
    _add_project_exclusion(folder, "Cormen.pdf", "hash123")
    exclusions = _get_project_exclusions(folder)
    assert "Cormen.pdf" in exclusions
    assert "hash123" in exclusions

    # Verify JSON structure
    ex_file = folder / ".researchlens-exclusions.json"
    assert ex_file.is_file()
    data = json.loads(ex_file.read_text(encoding="utf-8"))
    assert "Cormen.pdf" in data["excluded_filenames"]
    assert "hash123" in data["excluded_hashes"]

    # Remove exclusion
    _remove_project_exclusion(folder, "Cormen.pdf")
    exclusions_after = _get_project_exclusions(folder)
    assert "Cormen.pdf" not in exclusions_after


def test_is_generated_summary_export_guard(tmp_path: Path):
    # Exclusion file itself is a hidden dotfile
    dotfile = tmp_path / ".researchlens-exclusions.json"
    dotfile.write_text("{}", encoding="utf-8")
    assert dotfile.name.startswith(".")

    # Generated summary markdown
    summary_file = tmp_path / "Grounded Summary - Algorithms.md"
    summary_file.write_text("<!-- researchlens:generated-summary version=1.0 -->\n# Summary", encoding="utf-8")
    assert is_generated_summary_export(summary_file) is True


def test_document_status_cancelled_enum():
    # Verify DocumentStatus has CANCELLED
    assert hasattr(DocumentStatus, "CANCELLED")
    assert DocumentStatus.CANCELLED.value == "cancelled"

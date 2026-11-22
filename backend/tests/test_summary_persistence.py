"""
Tests for summary persistence in Paper model and API response.
"""
import pytest
from backend.app.models.paper import Paper
from backend.app.schemas.paper import PaperResponse


def test_paper_model_has_summary_json():
    p = Paper(
        id="test-p1",
        owner_id="u1",
        title="Test Project",
        summary_json={
            "paper_id": "test-p1",
            "answer": "This is a persisted summary.",
            "sources": [],
            "is_stale": False,
        },
    )
    assert p.summary_json is not None
    assert p.summary_json["answer"] == "This is a persisted summary."


def test_paper_response_schema_serializes_summary_json():
    p = Paper(
        id="test-p1",
        owner_id="u1",
        title="Test Project",
        summary_json={
            "paper_id": "test-p1",
            "answer": "This is a persisted summary.",
            "sources": [],
            "is_stale": False,
        },
    )
    p.created_at = None
    p.updated_at = None
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    p.created_at = now
    p.updated_at = now

    resp = PaperResponse.model_validate(p)
    assert resp.summary_json is not None
    assert resp.summary_json["paper_id"] == "test-p1"
    assert resp.summary_json["answer"] == "This is a persisted summary."

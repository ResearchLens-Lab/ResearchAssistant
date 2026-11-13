"""Source-level comparison validation at the API service boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.app.core.exceptions import DocumentNotFoundError, RequestValidationAppError
from backend.app.models.document import Document
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.schemas.paper import PaperCompareRequest
from backend.app.services.paper_service import PaperService


def _user(name):
    user_id = str(uuid4())
    return User(id=user_id, username=name, email=f"{name}@test.com", hashed_password="hashed")


def _document(document_id, paper_id, filename, status="indexed"):
    return Document(
        id=document_id,
        paper_id=paper_id,
        filename=filename,
        storage_path=f"/tmp/{filename}",
        content_type="application/pdf",
        file_size=100,
        processing_status=status,
    )


@pytest.mark.asyncio
async def test_compare_accepts_two_documents_from_the_same_project(db):
    user = _user("same_project")
    project = Paper(id=str(uuid4()), owner_id=user.id, title="Project", description="Study")
    docs = [_document(str(uuid4()), project.id, "one.pdf"), _document(str(uuid4()), project.id, "two.pdf")]
    db.add_all([user, project, *docs])
    await db.commit()
    rag = SimpleNamespace(compare_papers=AsyncMock(return_value={"answer": "Compared [S1]", "sources": [], "metadata": {}}))

    result = await PaperService(db, rag).compare(
        user,
        PaperCompareRequest(document_ids=[doc.id for doc in docs], focus_area="Compare methods", output_format="side_by_side"),
    )

    call = rag.compare_papers.await_args
    assert call.kwargs["document_ids"] == [doc.id for doc in docs]
    assert call.kwargs["output_format"] == "side_by_side"
    assert result["document_ids"] == [doc.id for doc in docs]
    assert len(result["metadata"]["comparison_scope"]) == 2


@pytest.mark.asyncio
async def test_compare_rejects_document_owned_by_another_user(db):
    owner, other = _user("doc_owner"), _user("doc_other")
    own_project = Paper(id=str(uuid4()), owner_id=owner.id, title="My project", description="Study")
    other_project = Paper(id=str(uuid4()), owner_id=other.id, title="Other project", description="Study")
    docs = [_document(str(uuid4()), own_project.id, "one.pdf"), _document(str(uuid4()), other_project.id, "private.pdf")]
    db.add_all([owner, other, own_project, other_project, *docs])
    await db.commit()
    rag = SimpleNamespace(compare_papers=AsyncMock())

    with pytest.raises(DocumentNotFoundError):
        await PaperService(db, rag).compare(owner, PaperCompareRequest(document_ids=[doc.id for doc in docs]))
    rag.compare_papers.assert_not_awaited()


@pytest.mark.asyncio
async def test_compare_rejects_unindexed_document(db):
    user = _user("unindexed")
    project = Paper(id=str(uuid4()), owner_id=user.id, title="Project", description="Study")
    docs = [_document(str(uuid4()), project.id, "ready.pdf"), _document(str(uuid4()), project.id, "pending.pdf", "processing")]
    db.add_all([user, project, *docs])
    await db.commit()
    rag = SimpleNamespace(compare_papers=AsyncMock())

    with pytest.raises(RequestValidationAppError):
        await PaperService(db, rag).compare(user, PaperCompareRequest(document_ids=[doc.id for doc in docs]))
    rag.compare_papers.assert_not_awaited()

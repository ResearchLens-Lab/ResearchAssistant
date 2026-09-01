"""Shared fixtures: isolated in-memory database, fake RAG gateway, API client.

Tests never touch the development PostgreSQL database and never call the real
RAG pipeline — `get_db` and `get_rag_gateway` are overridden per test.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Test configuration must be in place before application modules are imported.
os.environ["APP_ENV"] = "testing"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
os.environ["RAG_TIMEOUT_SECONDS"] = "5"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.app.models  # noqa: F401  (registers all tables)
from backend.app.core.config import get_settings
from backend.app.core.dependencies import get_rag_gateway
from backend.app.core.exceptions import RAGUnavailableError
from backend.app.database.base import Base
from backend.app.database.session import get_db
from backend.app.main import app

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


class FakeRAGGateway:
    """Deterministic stand-in for the RAG boundary. `mode` controls behavior:
    'ok', 'unavailable' (raises 503) or 'ingest_failed'."""

    def __init__(self):
        self.mode = "ok"
        self.calls = []
        self.answer = "The paper proposes a novel method [S1]."

    def _source(self, paper_id, document_id=None):
        return {
            "source_id": "S1",
            "paper_id": paper_id,
            "document_id": document_id,
            "chunk_id": "chunk_001",
            "page": 4,
            "page_start": 4,
            "page_end": 4,
            "section": "Methodology",
            "text": "Supporting passage from the paper.",
            "score": 0.87,
            "title": "Test Paper",
        }

    def _check_available(self):
        if self.mode == "unavailable":
            raise RAGUnavailableError()

    async def ingest_document(self, file_path, paper_id, metadata=None):
        self.calls.append(("ingest_document", paper_id))
        self._check_available()
        document_id = (metadata or {}).get("document_id", "doc_unknown")
        if self.mode == "ingest_failed":
            return {
                "success": False,
                "status": "failed",
                "document_id": document_id,
                "paper_id": paper_id,
                "chunk_count": 0,
                "total_pages": 0,
                "error": "No text chunks could be extracted from the document.",
            }
        return {
            "success": True,
            "status": "indexed",
            "document_id": document_id,
            "paper_id": paper_id,
            "chunk_count": 7,
            "total_pages": 3,
            "error": None,
        }

    async def ask_question(self, question, paper_ids=None, top_k=None):
        self.calls.append(("ask_question", tuple(paper_ids or [])))
        self._check_available()
        pids = list(paper_ids or [])
        return {
            "answer": self.answer,
            "sources": [self._source(pid) for pid in pids],
            "paper_ids": pids,
        }

    async def summarize_paper(self, paper_id, top_k=8):
        self._check_available()
        return {
            "answer": f"Summary of {paper_id}.",
            "sources": [self._source(paper_id)],
            "paper_ids": [paper_id],
        }

    async def compare_papers(self, paper_ids, focus_area=None, top_k=10):
        self._check_available()
        return {
            "answer": "Comparison result.",
            "sources": [self._source(pid) for pid in paper_ids],
            "paper_ids": list(paper_ids),
        }

    async def delete_paper(self, paper_id):
        self.calls.append(("delete_paper", paper_id))
        return 0


@pytest.fixture(autouse=True)
def _test_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def rag_gateway():
    return FakeRAGGateway()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine, rag_gateway):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_rag_gateway] = lambda: rag_gateway
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


USER_CREDENTIALS = {
    "email": "abhay@example.com",
    "password": "strongpassword123",
    "full_name": "Abhay Kumar Singh",
}

SECOND_USER_CREDENTIALS = {
    "email": "other@example.com",
    "password": "anotherpassword123",
    "full_name": "Other User",
}


async def register_and_login(client: AsyncClient, credentials: dict) -> dict:
    """Registers (ignoring duplicates) and logs in; returns auth headers."""
    resp = await client.post("/api/v1/auth/register", json=credentials)
    assert resp.status_code in (201, 409), resp.text
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers(client):
    return await register_and_login(client, USER_CREDENTIALS)


@pytest_asyncio.fixture
async def second_user_headers(client):
    return await register_and_login(client, SECOND_USER_CREDENTIALS)


async def create_paper(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "title": "Attention Is All You Need",
        "abstract": "We propose the Transformer architecture.",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "publication_year": 2017,
        "venue": "NeurIPS",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/papers", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()

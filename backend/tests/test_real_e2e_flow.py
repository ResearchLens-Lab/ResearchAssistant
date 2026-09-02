"""End-to-End integration test for real PDF upload, real ChromaDB vector storage,
real RAG retrieval, and real grounded question answering.
"""

import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.database.base import Base
from backend.app.database.session import get_db
from backend.app.integrations.rag_gateway import RAGGateway
from rag.config.settings import settings


# 2-Page PDF document with academic sections and text content
REAL_TEST_PDF_BYTES = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 380 >>
stream
BT
/F1 12 Tf
72 712 Td
(Abstract) Tj
0 -20 Td
(We present ResearchLens, an evidence-grounded research assistant architecture.) Tj
0 -30 Td
(Introduction) Tj
0 -20 Td
(Navigating dense literature requires precise section-aware retrieval and citation verification.) Tj
0 -30 Td
(Methodology) Tj
0 -20 Td
(The framework leverages dense embeddings with 384-dimensional representations stored in ChromaDB.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
6 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 7 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
7 0 obj
<< /Length 340 >>
stream
BT
/F1 12 Tf
72 712 Td
(Experiments) Tj
0 -20 Td
(We evaluated ResearchLens on 500 benchmark papers and achieved 94.2 percent grounding accuracy.) Tj
0 -30 Td
(Conclusion) Tj
0 -20 Td
(The proposed system prevents hallucination and guarantees verifiable source citations.) Tj
ET
endstream
endobj
xref
0 8
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000122 00000 n 
0000000251 00000 n 
0000000684 00000 n 
0000000760 00000 n 
0000000889 00000 n 
trailer
<< /Size 8 /Root 1 0 R >>
startxref
1282
%%EOF"""


@pytest.mark.asyncio
async def test_real_end_to_end_upload_and_chat_flow(tmp_path, monkeypatch):
    # Set isolated Chroma persist dir and uploads for this test
    chroma_dir = tmp_path / "test_chroma"
    upload_dir = tmp_path / "test_uploads"
    monkeypatch.setattr(settings, "chroma_persist_dir", str(chroma_dir))
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    # Set up in-memory sqlite DB for test
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    # We do NOT override RAGGateway -> test real RAG integration
    real_rag_gateway = RAGGateway()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register & Login
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "e2e_researcher@test.com",
                "password": "SecurePassword123!",
                "full_name": "E2E Lead Researcher",
            },
        )
        assert reg.status_code == 201

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "e2e_researcher@test.com",
                "password": "SecurePassword123!",
            },
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Paper
        paper_res = await client.post(
            "/api/v1/papers",
            json={
                "title": "ResearchLens Evidence Architecture",
                "abstract": "Dense section-aware grounded retrieval framework.",
                "authors": ["Lead Researcher", "AI Assistant"],
                "publication_year": 2026,
                "venue": "NeurIPS",
            },
            headers=headers,
        )
        assert paper_res.status_code == 201
        paper_id = paper_res.json()["id"]

        # 3. Upload Real PDF
        files = {"file": ("researchlens_paper.pdf", io.BytesIO(REAL_TEST_PDF_BYTES), "application/pdf")}
        data = {"paper_id": paper_id}
        upload_res = await client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers,
        )
        assert upload_res.status_code == 201
        doc_json = upload_res.json()
        assert doc_json["processing_status"] == "indexed"
        assert doc_json["chunk_count"] >= 2
        assert doc_json["processing_error"] is None

        # 4. Ask Question about uploaded paper
        chat_res = await client.post(
            "/api/v1/chat",
            json={
                "question": "What accuracy did ResearchLens achieve in experiments?",
                "paper_ids": [paper_id],
            },
            headers=headers,
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert "conversation_id" in chat_data
        assert "answer" in chat_data
        assert len(chat_data["answer"]) > 0
        assert len(chat_data["sources"]) > 0

        # Verify source provenance
        first_src = chat_data["sources"][0]
        assert first_src["paper_id"] == paper_id
        assert first_src["source_id"].startswith("S")
        assert "text" in first_src

        # 5. Fetch Messages for Conversation
        conv_id = chat_data["conversation_id"]
        msgs_res = await client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers)
        assert msgs_res.status_code == 200
        messages_list = msgs_res.json()
        assert isinstance(messages_list, list)
        assert len(messages_list) == 2  # user message and assistant message
        assert messages_list[0]["role"] == "user"
        assert messages_list[1]["role"] == "assistant"
        assert len(messages_list[1]["sources"]) > 0

        # 6. Test Grounded Summary
        summary_res = await client.post(f"/api/v1/papers/{paper_id}/summary", headers=headers)
        assert summary_res.status_code == 200
        summary_data = summary_res.json()
        assert summary_data["paper_id"] == paper_id
        assert len(summary_data["answer"]) > 0
        assert len(summary_data["sources"]) > 0

        # 7. Test Multi-Paper Compare (with second paper)
        paper2_res = await client.post(
            "/api/v1/papers",
            json={"title": "Baseline Retrieval Model", "publication_year": 2025},
            headers=headers,
        )
        paper2_id = paper2_res.json()["id"]

        compare_res = await client.post(
            "/api/v1/papers/compare",
            json={
                "paper_ids": [paper_id, paper2_id],
                "focus_area": "Compare methodology and retrieval precision",
            },
            headers=headers,
        )
        assert compare_res.status_code == 200
        compare_data = compare_res.json()
        assert len(compare_data["answer"]) > 0
        assert len(compare_data["sources"]) > 0

    app.dependency_overrides.clear()

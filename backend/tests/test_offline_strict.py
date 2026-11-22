import socket
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.config import get_settings


@pytest.mark.asyncio
async def test_zero_outbound_network_connections_strict(monkeypatch):
    """
    P0-8 Real offline proof:
    Monkeypatches socket.socket.connect.
    If destination is not loopback (127.0.0.1, ::1, localhost), log and raise.
    Executes:
    1) one definition query
    2) one procedure query
    3) one complexity query
    4) one summarization
    5) one paper-create query
    Proves that 0 outbound connections were attempted.
    """
    outbound_attempts = []
    real_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        if host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
            outbound_attempts.append(address)
            raise PermissionError(f"Strict offline mode: outbound connection to {address} blocked.")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setenv("DESKTOP_RUNTIME", "true")
    monkeypatch.setenv("EXTERNAL_LOOKUPS_ENABLED", "false")
    get_settings.cache_clear()

    import uuid
    rand_suffix = uuid.uuid4().hex[:8]
    test_email = f"offline_{rand_suffix}@example.com"
    test_user = f"offline_{rand_suffix}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        # 1. Register / Login local user
        await client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": "Password123!",
            "full_name": "Offline Researcher",
            "username": test_user,
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "identifier": test_email,
            "password": "Password123!",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Paper-create query
        paper_resp = await client.post(
            "/api/v1/papers",
            headers=headers,
            json={"title": "Strict Offline Analysis", "authors": ["Offline Researcher"]},
        )
        assert paper_resp.status_code == 201, paper_resp.text
        paper_id = paper_resp.json()["id"]

        # 3. Summarization query
        # Paper has no docs yet, should return clean structured empty/baseline summary without network
        sum_resp = await client.post(f"/api/v1/papers/{paper_id}/summary", headers=headers)
        assert sum_resp.status_code == 200, sum_resp.text

        # 4. Direct RAG queries (definition, procedure, complexity) using engine/composer
        from rag.intelligence.query_analyzer import QueryAnalyzer, ResearchIntent
        from rag.intelligence.answer_composer import ResearchAnswerComposer
        from rag.intelligence.retrieval_engine import RetrievedSource
        from rag.intelligence.confidence_evaluator import ConfidenceReport, ConfidenceLevel

        analyzer = QueryAnalyzer()
        composer = ResearchAnswerComposer()

        sample_source = RetrievedSource(
            chunk_id="chk_offline_1",
            paper_id=paper_id,
            source_id="src_offline_1",
            text="A red-black tree is a binary search tree that satisfies the following red-black properties: 1. Every node is red or black. 2. The root is black.",
            title="Algorithms",
            locator="Section 13.1",
            page_start=308,
            document_id="doc_1",
        )
        conf = ConfidenceReport(
            level=ConfidenceLevel.STRONG,
            overall_confidence_score=0.95,
            is_definitive_answer=True,
            top_source=sample_source,
        )

        # 4a. Definition query
        q_def = analyzer.analyze("What is a red-black tree?")
        assert q_def.intent == ResearchIntent.DEFINITION
        ans_def = composer.compose(q_def, [sample_source], conf)
        assert "red-black tree" in ans_def.markdown_content.lower()

        # 4b. Procedure query
        q_proc = analyzer.analyze("How does red-black tree insertion work step by step?")
        assert q_proc.intent == ResearchIntent.PROCEDURE
        ans_proc = composer.compose(q_proc, [sample_source], conf)
        assert ans_proc.markdown_content

        # 4c. Complexity query
        q_comp = analyzer.analyze("What is the time complexity of red-black tree search?")
        assert q_comp.intent == ResearchIntent.COMPLEXITY
        ans_comp = composer.compose(q_comp, [sample_source], conf)
        assert ans_comp.markdown_content

    # PROOF: outbound_attempts must be strictly empty!
    assert outbound_attempts == [], f"Expected 0 outbound connections, but got: {outbound_attempts}"
    get_settings.cache_clear()

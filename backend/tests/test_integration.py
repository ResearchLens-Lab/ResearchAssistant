"""Full integration flow (§62): register → login → create paper → upload →
chat → persisted assistant answer with sources. RAG is a deterministic mock."""

from .conftest import VALID_PDF


async def test_full_flow(client, rag_gateway):
    # Register + login
    creds = {"email": "flow@example.com", "password": "flowpassword123"}
    resp = await client.post("/api/v1/auth/register", json=creds)
    assert resp.status_code == 201
    resp = await client.post("/api/v1/auth/login", json=creds)
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Create paper
    resp = await client.post(
        "/api/v1/papers",
        json={"title": "Integration Paper", "publication_year": 2024},
        headers=headers,
    )
    assert resp.status_code == 201
    paper_id = resp.json()["id"]

    # Upload document → indexed through the RAG boundary
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("paper.pdf", VALID_PDF, "application/pdf")},
        data={"paper_id": paper_id},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["processing_status"] == "indexed"

    # Ask a question
    resp = await client.post(
        "/api/v1/chat",
        json={
            "question": "What is the main contribution of this paper?",
            "paper_ids": [paper_id],
            "conversation_id": None,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    chat = resp.json()
    assert chat["answer"]
    assert chat["sources"][0]["paper_id"] == paper_id

    # Assistant answer and sources are persisted
    resp = await client.get(
        f"/api/v1/conversations/{chat['conversation_id']}/messages", headers=headers
    )
    messages = resp.json()
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"
    assert messages[1]["sources"][0]["paper_id"] == paper_id

    # The same shared paper_id flowed through every boundary call
    assert ("ingest_document", paper_id) in rag_gateway.calls
    assert ("ask_question", (paper_id,)) in rag_gateway.calls

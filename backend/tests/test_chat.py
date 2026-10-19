import json

from .conftest import create_paper


async def ask(client, headers, paper_ids, question="What is the main contribution?",
              conversation_id=None):
    return await client.post(
        "/api/v1/chat",
        json={
            "question": question,
            "paper_ids": paper_ids,
            "conversation_id": conversation_id,
        },
        headers=headers,
    )


async def test_chat_creates_conversation(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await ask(client, auth_headers, [paper["id"]])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["conversation_id"]
    assert body["message_id"]
    assert body["answer"]
    assert body["paper_ids"] == [paper["id"]]
    assert body["sources"][0]["paper_id"] == paper["id"]
    assert body["sources"][0]["section"] == "Methodology"


async def test_chat_reuses_existing_conversation(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    first = (await ask(client, auth_headers, [paper["id"]])).json()
    second = (
        await ask(
            client,
            auth_headers,
            [paper["id"]],
            question="What dataset did they use?",
            conversation_id=first["conversation_id"],
        )
    ).json()
    assert second["conversation_id"] == first["conversation_id"]

    resp = await client.get(
        f"/api/v1/conversations/{first['conversation_id']}/messages",
        headers=auth_headers,
    )
    messages = resp.json()
    assert len(messages) == 4  # two user + two assistant turns
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


async def test_multi_paper_chat(client, auth_headers, rag_gateway):
    paper_a = await create_paper(client, auth_headers, title="Paper A")
    paper_b = await create_paper(client, auth_headers, title="Paper B")
    resp = await ask(
        client, auth_headers, [paper_a["id"], paper_b["id"]],
        question="Compare the methodologies.",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_ids"] == [paper_a["id"], paper_b["id"]]
    # Paper-specific source identity is preserved.
    assert {s["paper_id"] for s in body["sources"]} == {paper_a["id"], paper_b["id"]}
    assert ("ask_question", (paper_a["id"], paper_b["id"])) in rag_gateway.calls


async def test_chat_with_unknown_paper(client, auth_headers):
    resp = await ask(client, auth_headers, ["no-such-paper"])
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_chat_with_foreign_paper_denied(
    client, auth_headers, second_user_headers
):
    paper = await create_paper(client, auth_headers)
    resp = await ask(client, second_user_headers, [paper["id"]])
    assert resp.status_code == 404


async def test_chat_requires_auth(client):
    resp = await client.post(
        "/api/v1/chat", json={"question": "Hi?", "paper_ids": ["x"]}
    )
    assert resp.status_code == 401


async def test_stream_requires_auth(client):
    resp = await client.post("/api/v1/chat/stream", json={"question": "Hi?", "paper_ids": ["x"]})
    assert resp.status_code == 401


async def test_stream_emits_progress_and_persists_one_final_response(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    response = await client.post("/api/v1/chat/stream", json={
        "question": "What is the main contribution?", "paper_ids": [paper["id"]],
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    kinds = [event["type"] for event in events]
    assert kinds[0:2] == ["started", "planning_started"]
    assert "retrieval_started" in kinds and "sources_found" in kinds
    assert kinds[-1] == "completed"
    assert all(event["event_id"] == events[0]["event_id"] for event in events)
    final = events[-1]["data"]
    assert final["answer"]
    messages = (await client.get(f"/api/v1/conversations/{final['conversation_id']}/messages", headers=auth_headers)).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == final["answer"]
    assert messages[-1]["sources"][0]["source_id"] == "S1"


async def test_chat_rag_unavailable(client, auth_headers, rag_gateway):
    paper = await create_paper(client, auth_headers)
    rag_gateway.mode = "unavailable"
    resp = await ask(client, auth_headers, [paper["id"]])
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "RAG_UNAVAILABLE"

    # Nothing was persisted for the failed request.
    resp = await client.get("/api/v1/conversations", headers=auth_headers)
    assert resp.json()["total"] == 0


async def test_sources_are_persisted_on_assistant_message(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    body = (await ask(client, auth_headers, [paper["id"]])).json()
    resp = await client.get(
        f"/api/v1/conversations/{body['conversation_id']}/messages",
        headers=auth_headers,
    )
    messages = resp.json()
    user_msg, assistant_msg = messages[0], messages[1]
    assert user_msg["sources"] is None
    assert assistant_msg["sources"][0]["chunk_id"] == "chunk_001"
    assert assistant_msg["sources"][0]["score"] == 0.87
    assert assistant_msg["content"] == body["answer"]


async def test_conversation_crud_and_ownership(
    client, auth_headers, second_user_headers
):
    paper = await create_paper(client, auth_headers)
    created = await client.post(
        "/api/v1/conversations",
        json={"title": "My reading notes", "paper_ids": [paper["id"]]},
        headers=auth_headers,
    )
    assert created.status_code == 201
    conv_id = created.json()["id"]

    # Owner sees it; others get 404.
    assert (
        await client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    ).status_code == 200
    assert (
        await client.get(
            f"/api/v1/conversations/{conv_id}", headers=second_user_headers
        )
    ).status_code == 404

    listed = (await client.get("/api/v1/conversations", headers=auth_headers)).json()
    assert listed["total"] == 1

    deleted = await client.delete(
        f"/api/v1/conversations/{conv_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (
        await client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    ).status_code == 404


async def test_chat_conversation_title_from_question(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    body = (await ask(client, auth_headers, [paper["id"]], question="Short question?")).json()
    conv = (
        await client.get(
            f"/api/v1/conversations/{body['conversation_id']}", headers=auth_headers
        )
    ).json()
    assert conv["title"] == "Short question?"
    assert conv["paper_ids"] == [paper["id"]]

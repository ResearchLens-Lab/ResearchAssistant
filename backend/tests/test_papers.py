from .conftest import create_paper


async def test_create_paper(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    assert paper["id"]
    assert paper["title"] == "Attention Is All You Need"
    assert paper["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper["publication_year"] == 2017


async def test_create_paper_title_only(client, auth_headers):
    resp = await client.post("/api/v1/papers", json={"title": "Only Title"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Only Title"
    assert data["description"] in ("", None)


async def test_create_paper_requires_auth(client):
    resp = await client.post("/api/v1/papers", json={"title": "No Auth"})
    assert resp.status_code == 401


async def test_create_paper_requires_title(client, auth_headers):
    resp = await client.post("/api/v1/papers", json={}, headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_get_paper(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.get(f"/api/v1/papers/{paper['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == paper["id"]


async def test_get_unknown_paper(client, auth_headers):
    resp = await client.get("/api/v1/papers/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_cross_user_access_denied(client, auth_headers, second_user_headers):
    paper = await create_paper(client, auth_headers)
    # Another user probing the UUID must not learn the paper exists.
    resp = await client.get(f"/api/v1/papers/{paper['id']}", headers=second_user_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_list_papers(client, auth_headers):
    await create_paper(client, auth_headers, title="Paper One")
    await create_paper(client, auth_headers, title="Paper Two")
    resp = await client.get("/api/v1/papers", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_list_papers_is_scoped_to_owner(
    client, auth_headers, second_user_headers
):
    await create_paper(client, auth_headers)
    resp = await client.get("/api/v1/papers", headers=second_user_headers)
    assert resp.json()["total"] == 0


async def test_list_papers_pagination(client, auth_headers):
    for i in range(5):
        await create_paper(client, auth_headers, title=f"Paper {i}")
    resp = await client.get(
        "/api/v1/papers?page=2&page_size=2", headers=auth_headers
    )
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2


async def test_update_paper(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.patch(
        f"/api/v1/papers/{paper['id']}",
        json={"title": "Updated Title", "publication_year": 2018},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Title"
    assert body["publication_year"] == 2018
    # Untouched fields survive a partial update.
    assert body["venue"] == "NeurIPS"


async def test_update_paper_cross_user_denied(
    client, auth_headers, second_user_headers
):
    paper = await create_paper(client, auth_headers)
    resp = await client.patch(
        f"/api/v1/papers/{paper['id']}",
        json={"title": "Hijacked"},
        headers=second_user_headers,
    )
    assert resp.status_code == 404


async def test_delete_paper(client, auth_headers, rag_gateway):
    paper = await create_paper(client, auth_headers)
    resp = await client.delete(f"/api/v1/papers/{paper['id']}", headers=auth_headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/papers/{paper['id']}", headers=auth_headers)
    assert resp.status_code == 404
    # Indexed vectors are cleaned up through the RAG boundary.
    assert ("delete_paper", paper["id"]) in rag_gateway.calls


async def test_delete_paper_does_not_remove_database_or_original_when_index_cleanup_fails(client, auth_headers, rag_gateway):
    from .test_documents import upload
    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"], filename="keep-on-cleanup-error.pdf")
    document_id = uploaded.json()["id"]
    from backend.app.core.config import get_settings
    stored_path = get_settings().upload_path / f"{document_id}.pdf"
    assert stored_path.is_file()

    rag_gateway.mode = "unavailable"
    deleted = await client.delete(f"/api/v1/papers/{paper['id']}", headers=auth_headers)
    assert deleted.status_code == 503
    assert stored_path.is_file()
    still_owned = await client.get(f"/api/v1/papers/{paper['id']}", headers=auth_headers)
    assert still_owned.status_code == 200


async def test_summary_endpoint(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post(
        f"/api/v1/papers/{paper['id']}/summary", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_id"] == paper["id"]
    assert body["answer"] == f"Summary of {paper['id']}."
    assert body["sources"][0]["paper_id"] == paper["id"]


async def test_compare_endpoint(client, auth_headers):
    paper_a = await create_paper(client, auth_headers, title="Paper A")
    paper_b = await create_paper(client, auth_headers, title="Paper B")
    resp = await client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [paper_a["id"], paper_b["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_ids"] == [paper_a["id"], paper_b["id"]]
    assert body["answer"] == "Comparison result."
    assert len(body["sources"]) == 2
    assert body["metadata"]["research"]["sufficiency"]["status"] == "conflicting"


async def test_compare_requires_two_papers(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [paper["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_compare_with_foreign_paper_denied(
    client, auth_headers, second_user_headers
):
    mine = await create_paper(client, auth_headers)
    theirs = await create_paper(client, second_user_headers)
    resp = await client.post(
        "/api/v1/papers/compare",
        json={"paper_ids": [mine["id"], theirs["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_create_paper_requires_description(client, auth_headers):
    resp = await client.post(
        "/api/v1/papers",
        json={"title": "Paper Without Description", "description": "   "},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "description" in resp.text.lower()


async def test_create_paper_with_description(client, auth_headers):
    resp = await client.post(
        "/api/v1/papers",
        json={
            "title": "Quantum Computing Survey",
            "description": "Comprehensive review of superconducting qubit algorithms.",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Quantum Computing Survey"
    assert data["description"] == "Comprehensive review of superconducting qubit algorithms."

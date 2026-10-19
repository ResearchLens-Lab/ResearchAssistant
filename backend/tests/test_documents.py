from .conftest import VALID_PDF, create_paper


async def upload(client, headers, paper_id, filename="paper.pdf", content=VALID_PDF,
                 content_type="application/pdf"):
    return await client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, content, content_type)},
        data={"paper_id": paper_id},
        headers=headers,
    )


async def test_upload_valid_pdf(client, auth_headers, rag_gateway):
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["paper_id"] == paper["id"]
    assert body["filename"] == "paper.pdf"
    assert body["processing_status"] == "indexed"
    assert body["chunk_count"] == 7
    assert body["processing_error"] is None
    assert "storage_path" not in body  # internal path never exposed
    assert ("ingest_document", paper["id"]) in rag_gateway.calls


async def test_upload_empty_file(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"], content=b"")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_upload_unsupported_extension(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await upload(
        client, auth_headers, paper["id"], filename="paper.docx",
        content=b"not a pdf", content_type="application/msword",
    )
    assert resp.status_code == 400


async def test_upload_accepts_spreadsheet_and_slide_archive_signatures(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    for filename in ("data.xlsx", "slides.pptx"):
        resp = await upload(client, auth_headers, paper["id"], filename=filename,
                            content=b"PK\x03\x04fixture", content_type="application/octet-stream")
        assert resp.status_code == 201, resp.text
        assert resp.json()["filename"] == filename


async def test_upload_wrong_magic_bytes(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"], content=b"plain text data")
    assert resp.status_code == 400


async def test_upload_oversized_file(client, auth_headers):
    # MAX_UPLOAD_SIZE_MB=1 in the test environment.
    paper = await create_paper(client, auth_headers)
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 100)
    resp = await upload(client, auth_headers, paper["id"], content=big)
    assert resp.status_code == 400


async def test_upload_to_unknown_paper(client, auth_headers):
    resp = await upload(client, auth_headers, "no-such-paper")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_upload_to_foreign_paper_denied(
    client, auth_headers, second_user_headers
):
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, second_user_headers, paper["id"])
    assert resp.status_code == 404


async def test_upload_rag_ingestion_failure(client, auth_headers, rag_gateway):
    rag_gateway.mode = "ingest_failed"
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["processing_status"] == "failed"
    assert "chunks" in body["processing_error"]


async def test_upload_rag_unavailable(client, auth_headers, rag_gateway):
    rag_gateway.mode = "unavailable"
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"])
    # The upload itself succeeded; ingestion is recorded as failed and can be retried.
    assert resp.status_code == 201
    assert resp.json()["processing_status"] == "failed"


async def test_get_document(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    uploaded = (await upload(client, auth_headers, paper["id"])).json()
    resp = await client.get(
        f"/api/v1/documents/{uploaded['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == uploaded["id"]


async def test_get_document_cross_user_denied(
    client, auth_headers, second_user_headers
):
    paper = await create_paper(client, auth_headers)
    uploaded = (await upload(client, auth_headers, paper["id"])).json()
    resp = await client.get(
        f"/api/v1/documents/{uploaded['id']}", headers=second_user_headers
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


async def test_list_paper_documents(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    await upload(client, auth_headers, paper["id"])
    await upload(client, auth_headers, paper["id"], filename="revision2.pdf")
    resp = await client.get(
        f"/api/v1/papers/{paper['id']}/documents", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

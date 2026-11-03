import io
import zipfile

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
    assert body["processing_stage"] == "ready"
    assert body["processing_progress"] == 100
    assert body["processing_progress_type"] == "actual"
    assert body["processing_started_at"]
    assert body["processing_heartbeat_at"]
    assert body["processing_completed_units"] == 7
    assert body["processing_total_units"] == 7
    assert body["processing_unit"] == "chunks"
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


async def test_batch_upload_indexes_multiple_supported_files_to_selected_project(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("first.pdf", VALID_PDF, "application/pdf")), ("files", ("notes.txt", b"UTF-8 source notes", "text/plain"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success_count"] == 2
    assert body["failure_count"] == 0
    assert {item["filename"] for item in body["documents"]} == {"first.pdf", "notes.txt"}
    assert {item["paper_id"] for item in body["documents"]} == {paper["id"]}


async def test_batch_upload_keeps_processing_other_files_after_one_file_fails(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("bad.pdf", b"not a pdf", "application/pdf")),
               ("files", ("good.pdf", VALID_PDF, "application/pdf"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["failure_count"] == 1, body
    assert body["success_count"] == 1
    assert body["documents"][0]["filename"] == "good.pdf"


async def test_batch_upload_enforces_total_size_and_returns_clear_error(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    large = b"%PDF-1.4\n" + b"x" * (1100 * 1024)
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("one.pdf", large, "application/pdf")), ("files", ("two.pdf", large, "application/pdf"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "total upload limit" in resp.json()["error"]["message"]


async def test_batch_upload_reports_oversized_file(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    oversized = b"%PDF-1.4\n" + b"x" * (1024 * 1024 + 100)
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("too-big.pdf", oversized, "application/pdf"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["failure_count"] == 1
    assert "1 MB" in resp.json()["failures"][0]["error"]


async def test_batch_upload_rejects_unsafe_zip_paths(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("sources.zip", archive_bytes.getvalue(), "application/zip"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["success_count"] == 0
    assert "Unsafe archive member" in resp.json()["failures"][0]["error"]


async def test_batch_upload_rejects_excessive_zip_compression_ratio(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("notes.txt", "A" * (2 * 1024 * 1024))
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("sources.zip", archive_bytes.getvalue(), "application/zip"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["success_count"] == 0
    assert "compression ratio" in resp.json()["failures"][0]["error"]


async def test_batch_upload_caps_zip_entry_count(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        for index in range(101):
            archive.writestr(f"source-{index}.txt", "short source")
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("sources.zip", archive_bytes.getvalue(), "application/zip"))],
        data={"paper_id": paper["id"]}, headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["success_count"] == 0
    assert "more than 100 files" in resp.json()["failures"][0]["error"]


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


async def test_batch_upload_to_foreign_paper_is_denied(client, auth_headers, second_user_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post(
        "/api/v1/documents/upload/batch",
        files=[("files", ("paper.pdf", VALID_PDF, "application/pdf"))],
        data={"paper_id": paper["id"]}, headers=second_user_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_upload_rag_ingestion_failure(client, auth_headers, rag_gateway):
    rag_gateway.mode = "ingest_failed"
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["processing_status"] == "failed"
    assert "chunks" in body["processing_error"]


async def test_document_is_not_ready_when_chroma_and_fts_counts_disagree(client, auth_headers, rag_gateway):
    rag_gateway.mode = "inconsistent"
    paper = await create_paper(client, auth_headers)
    response = await upload(client, auth_headers, paper["id"], filename="inconsistent.pdf")
    body = response.json()
    assert body["processing_status"] == "failed"
    assert body["processing_stage"] == "failed"
    assert body["processing_progress"] < 100
    assert body["chunk_count"] == 0
    assert "consistency check failed" in body["processing_error"]
    assert rag_gateway.indexed_chunks[body["id"]] == 0


async def test_upload_rag_unavailable(client, auth_headers, rag_gateway):
    rag_gateway.mode = "unavailable"
    paper = await create_paper(client, auth_headers)
    resp = await upload(client, auth_headers, paper["id"])
    # The upload itself succeeded; ingestion is recorded as failed and can be retried.
    assert resp.status_code == 201
    assert resp.json()["processing_status"] == "failed"


async def test_upload_timeout_is_terminal_without_ready_progress_or_stale_chunk_count(client, auth_headers, rag_gateway):
    rag_gateway.mode = "timeout"
    paper = await create_paper(client, auth_headers)
    response = await upload(client, auth_headers, paper["id"], filename="timeout.pdf")
    body = response.json()
    assert body["processing_status"] == "failed"
    assert body["processing_stage"] == "failed"
    assert body["processing_progress"] < 100
    assert body["chunk_count"] == 0
    assert "timed out" in body["processing_error"].casefold()


async def test_failed_document_retries_same_stored_source_without_creating_a_duplicate(client, auth_headers, rag_gateway):
    rag_gateway.mode = "ingest_failed"
    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"], filename="retry.pdf")
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    assert uploaded.json()["processing_status"] == "failed"

    rag_gateway.mode = "ok"
    retried = await client.post(f"/api/v1/documents/{document_id}/retry", headers=auth_headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["id"] == document_id
    assert retried.json()["processing_status"] == "indexed"
    assert retried.json()["processing_progress"] == 100
    assert rag_gateway.calls.count(("ingest_document", paper["id"])) == 2


async def test_only_one_concurrent_retry_can_claim_a_failed_document(client, auth_headers, rag_gateway):
    import asyncio
    rag_gateway.mode = "ingest_failed"
    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"], filename="atomic-retry.pdf")
    document_id = uploaded.json()["id"]
    assert uploaded.json()["processing_status"] == "failed"

    rag_gateway.mode = "blocking"
    rag_gateway.ingest_started = asyncio.Event()
    rag_gateway.ingest_release = asyncio.Event()
    first_retry = asyncio.create_task(client.post(f"/api/v1/documents/{document_id}/retry", headers=auth_headers))
    await asyncio.wait_for(rag_gateway.ingest_started.wait(), timeout=2)
    second_retry = await client.post(f"/api/v1/documents/{document_id}/retry", headers=auth_headers)
    assert second_retry.status_code == 400
    assert "already being processed" in second_retry.json()["error"]["message"]

    rag_gateway.ingest_release.set()
    first_response = await first_retry
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["processing_status"] == "indexed"


async def test_processing_document_cannot_be_retried_as_a_duplicate_job(client, auth_headers, db_engine):
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from backend.app.models.document import Document

    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"], filename="active.pdf")
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        await session.execute(update(Document).where(Document.id == uploaded.json()["id"]).values(processing_status="processing"))
        await session.commit()

    response = await client.post(f"/api/v1/documents/{uploaded.json()['id']}/retry", headers=auth_headers)
    assert response.status_code == 400
    assert "already being processed" in response.json()["error"]["message"]


async def test_stalled_processing_status_recovers_to_retryable_failure(client, auth_headers, db_engine):
    from datetime import datetime, timedelta
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from backend.app.models.document import Document

    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"], filename="stalled.pdf")
    old = datetime.utcnow() - timedelta(minutes=20)
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        await session.execute(update(Document).where(Document.id == uploaded.json()["id"]).values(
            processing_status="processing", processing_stage="generating_embeddings",
            processing_heartbeat_at=old, updated_at=old,
        ))
        await session.commit()

    response = await client.get(f"/api/v1/documents/{uploaded.json()['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["processing_status"] == "failed"
    assert response.json()["processing_stage"] == "failed"
    assert "Retry this source" in response.json()["processing_error"]
    assert response.json()["chunk_count"] == 0
    assert response.json()["processing_progress"] == 0


async def test_get_document(client, auth_headers):
    paper = await create_paper(client, auth_headers)
    uploaded = (await upload(client, auth_headers, paper["id"])).json()
    resp = await client.get(
        f"/api/v1/documents/{uploaded['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == uploaded["id"]
    assert resp.json()["processing_progress"] == 100
    assert resp.json()["processing_started_at"] == uploaded["processing_started_at"]


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


async def test_list_documents_for_multiple_owned_projects(client, auth_headers):
    paper_a = await create_paper(client, auth_headers, title="Project A")
    paper_b = await create_paper(client, auth_headers, title="Project B")
    await upload(client, auth_headers, paper_a["id"], filename="a.pdf")
    await upload(client, auth_headers, paper_b["id"], filename="b.pdf")
    resp = await client.post("/api/v1/documents/by-papers", json={"paper_ids": [paper_a["id"], paper_b["id"]]}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [doc["filename"] for doc in body[paper_a["id"]]] == ["a.pdf"]
    assert [doc["filename"] for doc in body[paper_b["id"]]] == ["b.pdf"]


async def test_batch_document_list_rejects_foreign_project_ids(client, auth_headers, second_user_headers):
    paper = await create_paper(client, auth_headers)
    resp = await client.post("/api/v1/documents/by-papers", json={"paper_ids": [paper["id"]]}, headers=second_user_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PAPER_NOT_FOUND"


async def test_cancel_document_endpoint_cancels_active_document(client, auth_headers, db_engine):
    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"])
    doc_id = uploaded.json()["id"]

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from backend.app.models.document import Document, DocumentStatus
    from sqlalchemy import update

    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        await session.execute(
            update(Document).where(Document.id == doc_id).values(
                processing_status=DocumentStatus.PROCESSING.value,
                processing_stage="extracting_text"
            )
        )
        await session.commit()

    resp = await client.post(f"/api/v1/documents/{doc_id}/cancel", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == doc_id
    assert body["processing_status"] == "cancelled"
    assert body["processing_stage"] == "cancelled"
    assert "cancelled" in body["processing_error"].lower()


async def test_cancel_document_requires_ownership(client, auth_headers, second_user_headers):
    paper = await create_paper(client, auth_headers)
    uploaded = await upload(client, auth_headers, paper["id"])
    doc_id = uploaded.json()["id"]

    resp = await client.post(f"/api/v1/documents/{doc_id}/cancel", headers=second_user_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

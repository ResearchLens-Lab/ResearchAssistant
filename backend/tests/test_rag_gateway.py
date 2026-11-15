import asyncio

import pytest

from backend.app.core.exceptions import RAGUnavailableError
from backend.app.integrations.rag_gateway import RAGGateway


@pytest.mark.asyncio
async def test_gateway_applies_ingestion_specific_timeout():
    class SlowClient:
        def ingest_document(self, **kwargs):
            import time
            time.sleep(0.15)

    gateway = RAGGateway(client=SlowClient(), timeout_seconds=1)
    with pytest.raises(RAGUnavailableError, match="timed out"):
        await gateway._call("ingest_document", timeout_seconds=0.01)


@pytest.mark.asyncio
async def test_ingestion_timeout_requests_cooperative_stop_and_keeps_lock_until_worker_exits(monkeypatch):
    import threading
    import time
    from backend.app.integrations.rag_client import RAGClient
    from rag.pipelines.ingest_pipeline import IngestResult

    started = threading.Event()
    cancellation_seen = threading.Event()
    release = threading.Event()
    attempts = []

    class SlowPipeline:
        def ingest_file(self, file_path, paper_id=None, metadata=None, progress_callback=None, cancel_event=None):
            attempts.append(cancel_event)
            if len(attempts) == 1:
                started.set()
                while not cancel_event.is_set():
                    time.sleep(.002)
                cancellation_seen.set()
                assert release.wait(2)
                return IngestResult(success=False, status="failed", document_id="doc-timeout",
                                    paper_id=paper_id, error="cancelled")
            return IngestResult(success=True, status="indexed", document_id="doc-timeout",
                                paper_id=paper_id, chunk_count=1)

    class Repo:
        def delete_document_chunks(self, _document_id):
            return 0

    client = RAGClient(ingest_pipeline=SlowPipeline(), query_pipeline=object(), vector_repo=Repo())
    gateway = RAGGateway(client=client)
    monkeypatch.setattr("backend.app.integrations.rag_gateway.get_settings", lambda: type(
        "Settings", (), {"rag_ingest_timeout_seconds": 0.02}
    )())
    upload = asyncio.create_task(gateway.ingest_document("source.pdf", "paper", {"document_id": "doc-timeout"}))
    assert await asyncio.to_thread(started.wait, 1)
    with pytest.raises(RAGUnavailableError, match="Cancellation was requested"):
        await upload
    assert await asyncio.to_thread(cancellation_seen.wait, 1)

    immediate_retry = await asyncio.to_thread(
        client.ingest_document, "source.pdf", "paper", {"document_id": "doc-timeout"}
    )
    assert immediate_retry["active_attempt"] is True
    assert len(attempts) == 1

    release.set()
    for _ in range(100):
        retry = await asyncio.to_thread(
            client.ingest_document, "source.pdf", "paper", {"document_id": "doc-timeout"}
        )
        if retry["success"]:
            break
        await asyncio.sleep(.005)
    assert retry["success"] is True
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_ingest_uses_longer_configured_timeout(monkeypatch):
    class SlowClient:
        def ingest_document(self, **kwargs):
            return {"success": True}

    gateway = RAGGateway(client=SlowClient(), timeout_seconds=0.01)
    monkeypatch.setattr("backend.app.integrations.rag_gateway.get_settings", lambda: type("Settings", (), {"rag_ingest_timeout_seconds": 0.5})())
    result = await gateway.ingest_document("file.pdf", "paper")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_ingestion_progress_callback_crosses_worker_thread():
    class ProgressClient:
        def ingest_document(self, progress_callback=None, **kwargs):
            for stage in ("extracting_text", "chunking", "generating_embeddings", "indexing"):
                progress_callback({"stage": stage})
            return {"success": True}

    events = []
    gateway = RAGGateway(client=ProgressClient())
    await gateway.ingest_document("file.pdf", "paper", progress_callback=events.append)
    assert [event["stage"] for event in events] == [
        "extracting_text", "chunking", "generating_embeddings", "indexing"
    ]


@pytest.mark.asyncio
async def test_gateway_preserves_actionable_gemini_configuration_errors():
    class InvalidGeminiClient:
        def ask_question(self, **kwargs):
            """Mock that raises configuration error."""
            raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY.")

    gateway = RAGGateway(client=InvalidGeminiClient())
    with pytest.raises(RAGUnavailableError, match="Set GEMINI_API_KEY"):
        await gateway.ask_question(question="test", user_id="user_test")


@pytest.mark.asyncio
async def test_gateway_exposes_unsupported_generation_provider_clearly():
    class LocalIngestionOnlyClient:
        def ask_question(self, **kwargs):
            """Mock that raises provider error."""
            raise ValueError("Unsupported LLM provider 'local'. Choose 'gemini' or 'mock'.")

    gateway = RAGGateway(client=LocalIngestionOnlyClient())
    with pytest.raises(RAGUnavailableError, match="Unsupported LLM provider 'local'"):
        await gateway.ask_question(question="test", user_id="user_test")

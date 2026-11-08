import threading

from backend.app.integrations.rag_client import RAGClient
from rag.pipelines.ingest_pipeline import IngestResult


def test_rag_client_does_not_start_duplicate_ingest_while_worker_is_still_running():
    started = threading.Event()
    finish = threading.Event()

    class SlowPipeline:
        def ingest_file(self, file_path, paper_id=None, metadata=None, progress_callback=None, cancel_event=None):
            started.set()
            assert finish.wait(2)
            return IngestResult(
                success=True, status="indexed", document_id="doc-1", paper_id=paper_id,
                chunk_count=1, total_pages=1,
            )

    client = RAGClient(ingest_pipeline=SlowPipeline(), query_pipeline=object(), vector_repo=object())
    results = []
    worker = threading.Thread(target=lambda: results.append(client.ingest_document(
        "source.pdf", "paper-1", {"document_id": "doc-1"}
    )))
    worker.start()
    assert started.wait(2)

    duplicate = client.ingest_document("source.pdf", "paper-1", {"document_id": "doc-1"})
    assert duplicate["success"] is False
    assert duplicate["active_attempt"] is True
    assert "still running" in duplicate["error"]

    finish.set()
    worker.join(2)
    assert not worker.is_alive()
    assert results[0]["success"] is True
    assert client.ingest_document("source.pdf", "paper-1", {"document_id": "doc-1"})["success"] is True


def test_different_document_ingestions_can_run_concurrently():
    both_started = threading.Barrier(2)

    class ConcurrentPipeline:
        def ingest_file(self, file_path, paper_id=None, metadata=None, progress_callback=None, cancel_event=None):
            both_started.wait(timeout=2)
            return IngestResult(success=True, status="indexed", document_id=metadata["document_id"],
                                paper_id=paper_id, chunk_count=1)

    client = RAGClient(ingest_pipeline=ConcurrentPipeline(), query_pipeline=object(), vector_repo=object())
    results = {}
    threads = [threading.Thread(target=lambda doc_id=doc: results.setdefault(doc_id, client.ingest_document(
        f"{doc_id}.pdf", "paper", {"document_id": doc_id}
    ))) for doc in ("doc-a", "doc-b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
    assert all(not thread.is_alive() for thread in threads)
    assert set(results) == {"doc-a", "doc-b"}
    assert all(result["success"] for result in results.values())


def test_paper_deletion_is_rejected_while_one_of_its_ingestions_is_active():
    started = threading.Event()
    release = threading.Event()

    class SlowPipeline:
        def ingest_file(self, file_path, paper_id=None, metadata=None, progress_callback=None, cancel_event=None):
            started.set()
            assert release.wait(2)
            return IngestResult(success=True, status="indexed", document_id=metadata["document_id"],
                                paper_id=paper_id, chunk_count=1)

        def delete_paper(self, _paper_id):
            raise AssertionError("delete must not start during ingestion")

    client = RAGClient(ingest_pipeline=SlowPipeline(), query_pipeline=object(), vector_repo=object())
    result = []
    worker = threading.Thread(target=lambda: result.append(client.ingest_document(
        "active.pdf", "paper-active", {"document_id": "active-doc"}
    )))
    worker.start()
    assert started.wait(1)
    try:
        client.delete_paper("paper-active")
        raise AssertionError("active paper deletion should fail")
    except RuntimeError as exc:
        assert "being indexed" in str(exc)
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert result[0]["success"] is True



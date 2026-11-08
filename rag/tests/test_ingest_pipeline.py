from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.ingestion.document_loader import TextDocumentLoader
from rag.chunking.chunker import DocumentChunker


def test_very_long_unpunctuated_pdf_text_is_split_below_embedding_limits():
    content = " ".join(f"algorithm{index}" for index in range(1800))
    document = TextDocumentLoader().load_text(
        content,
        {"paper_id": "large-paper", "document_id": "large-document", "source_format": "pdf"},
    )
    chunks = DocumentChunker(chunk_size=500, chunk_overlap=80).chunk_document(document)
    assert len(chunks) > 1
    assert all(chunk.metadata.token_count <= 580 for chunk in chunks)
    assert chunks[0].metadata.page_start == 1
    assert chunks[-1].metadata.page_end == document.total_pages


def test_embedding_failure_removes_partial_index_and_reports_failed_result(vector_repo, mock_embedder):
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    pipeline.batch_generator.batch_size = 1
    original_embed = mock_embedder.embed_documents
    calls = 0

    def fail_after_first_batch(texts):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated embedding timeout")
        return original_embed(texts)

    mock_embedder.embed_documents = fail_after_first_batch
    content = " ".join(f"evidence{i}." for i in range(1200))
    result = pipeline.ingest_text(
        content, paper_id="partial-paper",
        metadata={"document_id": "partial-document"},
    )
    assert result.success is False
    assert "simulated embedding timeout" in result.error
    assert vector_repo.count_chunks({"document_id": "partial-document"}) == 0


def test_cleanup_failure_is_reported_without_replacing_embedding_error(vector_repo, mock_embedder):
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    pipeline.batch_generator.batch_size = 1
    original_embed = mock_embedder.embed_documents
    calls = 0

    def fail_embedding(texts):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("primary embedding failure")
        return original_embed(texts)

    mock_embedder.embed_documents = fail_embedding
    vector_repo.delete_document_chunks = lambda _doc_id: (_ for _ in ()).throw(OSError("cleanup disk failure"))
    result = pipeline.ingest_text(
        " ".join(f"recoveryfact{index}." for index in range(1200)),
        paper_id="cleanup-paper", metadata={"document_id": "cleanup-document"},
    )
    assert result.success is False
    assert "primary embedding failure" in result.error
    assert "index cleanup failed" in result.error and "cleanup disk failure" in result.error


def test_fts_failure_after_chroma_upsert_is_not_reported_as_success(vector_repo, mock_embedder):
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    vector_repo._upsert_lexical = lambda _chunks: (_ for _ in ()).throw(RuntimeError("FTS write failed"))
    result = pipeline.ingest_text(
        "A local source passage with enough content to create a chunk.",
        paper_id="fts-paper", metadata={"document_id": "fts-failure-document"},
    )
    assert result.success is False
    assert "FTS write failed" in result.error
    assert vector_repo.count_chunks({"document_id": "fts-failure-document"}) == 0


def test_reingestion_reconciles_obsolete_chunk_ids(vector_repo, mock_embedder):
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    metadata = {"document_id": "changing-source", "filename": "source.txt"}
    first = pipeline.ingest_text("First distinct passage. " * 200, paper_id="paper", metadata=metadata)
    assert first.success and first.chunk_count > 1
    second = pipeline.ingest_text("Short replacement passage.", paper_id="paper", metadata=metadata)
    assert second.success and second.chunk_count == 1
    counts = vector_repo.document_index_counts("changing-source")
    assert counts["ids_match"]
    assert counts["chroma_count"] == counts["fts_count"] == 1


def test_cancellation_during_embedding_stops_before_indexing_and_cleans_document(vector_repo, mock_embedder):
    import threading

    embedding_started = threading.Event()
    finish_embedding = threading.Event()
    cancel_event = threading.Event()
    original_embed = mock_embedder.embed_documents

    def blocked_embedding(texts):
        embedding_started.set()
        assert finish_embedding.wait(2)
        return original_embed(texts)

    mock_embedder.embed_documents = blocked_embedding
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    results = []
    worker = threading.Thread(target=lambda: results.append(pipeline.ingest_text(
        "A synthetic passage for safe cooperative cancellation.", paper_id="cancel-paper",
        metadata={"document_id": "cancel-document"}, cancel_event=cancel_event,
    )))
    worker.start()
    assert embedding_started.wait(1)
    cancel_event.set()
    finish_embedding.set()
    worker.join(2)
    assert not worker.is_alive()
    assert results[0].success is False
    assert "cancelled at safe boundary" in results[0].error
    counts = vector_repo.document_index_counts("cancel-document")
    assert counts["chroma_count"] == counts["fts_count"] == 0
    assert counts["ids_match"] is True


def test_pipeline_emits_real_ordered_processing_stages(vector_repo, mock_embedder):
    pipeline = IngestionPipeline(embedder=mock_embedder, vector_repo=vector_repo)
    events = []
    result = pipeline.ingest_text(
        "A short source sentence with evidence.", paper_id="stage-paper",
        metadata={"document_id": "stage-document"}, progress_callback=events.append,
    )
    assert result.success is True
    stage_changes = []
    for event in events:
        if not stage_changes or stage_changes[-1] != event["stage"]:
            stage_changes.append(event["stage"])
    assert stage_changes == ["chunking", "generating_embeddings", "indexing", "ready"]
    progress_values = [event["progress"] for event in events]
    assert progress_values == sorted(progress_values)
    assert progress_values[-1] == 100
    assert any(event.get("total_chunks") for event in events)
    assert vector_repo.count_chunks({"document_id": "stage-document"}) == result.chunk_count


def test_fastembed_pipeline_splits_oversized_chunks_before_indexing(vector_repo, tmp_path):
    from rag.embeddings.cache import SQLiteEmbeddingCache
    from rag.embeddings.embedder import FastEmbedder

    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "embeddings.sqlite3"))
    embedded_texts = []

    def split_for_test(text):
        midpoint = len(text) // 2
        return [(text[:midpoint], 250), (text[midpoint:], 251)]

    def fake_embed(texts):
        embedded_texts.extend(texts)
        return [[0.1] * 384 for _ in texts]

    embedder.split_text_for_embedding = split_for_test
    embedder.embed_documents = fake_embed
    pipeline = IngestionPipeline(embedder=embedder, vector_repo=vector_repo)
    content = "Introduction\n\n" + "Evidence passage with preserved page metadata. " * 18

    result = pipeline.ingest_text(
        content,
        paper_id="token-paper",
        metadata={"document_id": "token-doc", "filename": "token.pdf", "source_format": "pdf"},
    )

    assert result.success is True
    assert result.chunk_count == 2
    assert len(embedded_texts) == 2
    assert vector_repo.count_chunks({"document_id": "token-doc"}) == 2
    stored = vector_repo.collection.get(where={"document_id": "token-doc"}, include=["documents", "metadatas"])
    assert len(stored["ids"]) == 2
    assert all(metadata["token_count"] <= 512 for metadata in stored["metadatas"])
    assert len(set(stored["ids"])) == 2


def test_local_fastembed_pdf_ingestion_does_not_initialize_generation(vector_repo, tmp_path, monkeypatch):
    import pymupdf
    from rag.config.settings import settings
    from rag.embeddings.cache import SQLiteEmbeddingCache
    from rag.embeddings.embedder import FastEmbedder
    from backend.app.integrations.rag_client import RAGClient

    monkeypatch.setattr(settings, "llm_provider", "local")
    pdf_path = tmp_path / "local_only.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Local embedding fixture fact: the blue marker is 42.")
    pdf.save(pdf_path)
    pdf.close()

    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "embedding-cache.sqlite3"))
    embedder.split_text_for_embedding = lambda text: [(text, 12)]
    embedder.embed_documents = lambda texts: [[0.01] * 384 for _ in texts]
    pipeline = IngestionPipeline(embedder=embedder, vector_repo=vector_repo)
    client = RAGClient(ingest_pipeline=pipeline, vector_repo=vector_repo)

    result = client.ingest_document(str(pdf_path), "local-paper", {
        "document_id": "local-fastembed-doc", "filename": pdf_path.name,
    })
    assert result["success"] is True
    assert result["chunk_count"] > 0
    assert vector_repo.count_chunks({"document_id": "local-fastembed-doc"}) == result["chunk_count"]
    assert client._query_pipeline._generator is None

import asyncio

import pytest
import pymupdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.app.models  # register ORM models
from backend.app.database.base import Base
from backend.app.models.document import Document
from backend.app.models.paper import Paper
from backend.app.models.user import User
from rag.config.settings import settings
from rag.embeddings.cache import SQLiteEmbeddingCache
from rag.embeddings.embedder import FastEmbedder
from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.vectorstore.chroma_client import ChromaClientFactory
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.vector_repository import VectorRepository


@pytest.mark.asyncio
async def test_reindex_resets_stale_count_cleans_failed_attempt_and_retries_idempotently(
    tmp_path, monkeypatch
):
    from scripts import reindex_documents as reindex

    monkeypatch.setattr(settings, "llm_provider", "local")
    ChromaClientFactory.reset_client()
    test_chroma_client = ChromaClientFactory.get_client(persist_dir=str(tmp_path / "chroma"), force_new=True)
    repository = VectorRepository(CollectionManager(client=test_chroma_client))
    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "embedding-cache.sqlite3"))
    embedder.split_text_for_embedding = lambda text: [(text, 20)]
    embedder.embed_documents = lambda texts: [[0.02] * 384 for _ in texts]
    ingestion = IngestionPipeline(embedder=embedder, vector_repo=repository)

    pdf_path = tmp_path / "reindex_fixture.pdf"
    pdf = pymupdf.open()
    for page_number, fact in enumerate(("The test beacon is BLUEBIRD.", "The launch year is 2039."), 1):
        page = pdf.new_page()
        section = "Results" if page_number == 1 else "Conclusion"
        page.insert_text((72, 72), f"{page_number}. {section}\n{fact} " + ("Supporting evidence. " * 180))
    pdf.save(pdf_path)
    pdf.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reindex-test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(reindex, "get_session_factory", lambda: factory)

    async with factory() as session:
        user = User(email="reindex@example.test", username="reindex_test", hashed_password="test")
        session.add(user)
        await session.flush()
        paper = Paper(owner_id=user.id, title="Isolated reindex fixture", authors=["Test Author"])
        session.add(paper)
        await session.flush()
        document = Document(
            paper_id=paper.id, filename=pdf_path.name, storage_path=str(pdf_path),
            content_type="application/pdf", file_size=pdf_path.stat().st_size,
            processing_status="indexed", processing_stage="ready", chunk_count=99,
        )
        session.add(document)
        await session.commit()
        document_id, paper_id = document.id, paper.id

    class Gateway:
        def __init__(self):
            self.fail_after_upsert = False

        async def ingest_document(self, file_path, paper_id, metadata=None, progress_callback=None):
            original = repository.upsert_chunks
            if self.fail_after_upsert:
                self.fail_after_upsert = False

                def upsert_then_fail(chunks, vectors):
                    original(chunks, vectors)
                    raise RuntimeError("injected post-index failure")

                repository.upsert_chunks = upsert_then_fail
            try:
                return await asyncio.to_thread(
                    lambda: _ingest_result(ingestion, file_path, paper_id, metadata, progress_callback)
                )
            finally:
                repository.upsert_chunks = original

        async def get_document_index_counts(self, target_id):
            return await asyncio.to_thread(repository.document_index_counts, target_id)

        async def delete_document_chunks(self, target_id):
            return await asyncio.to_thread(repository.delete_document_chunks, target_id)

    def _ingest_result(ingest_pipeline, file_path, target_paper_id, metadata, callback):
        return ingest_pipeline.ingest_file(file_path, target_paper_id, metadata, callback).model_dump()

    gateway = Gateway()
    monkeypatch.setattr(reindex, "RAGGateway", lambda: gateway)

    # Success establishes a real positive prior count and exact store agreement.
    assert await reindex.reindex_documents([document_id], False, apply=True) == (1, 0)
    async with factory() as session:
        before = await session.get(Document, document_id)
        prior_count = before.chunk_count
        assert before.processing_status == "indexed" and prior_count > 0
    initial = repository.document_index_counts(document_id)
    assert initial["chroma_count"] == initial["fts_count"] == prior_count
    assert initial["ids_match"] is True

    # Inject an error after the actual Chroma and FTS upsert. Ingest cleanup and
    # the reindex terminal-state reconciliation must both leave zero records.
    gateway.fail_after_upsert = True
    assert await reindex.reindex_documents([document_id], False, apply=True) == (0, 1)
    async with factory() as session:
        failed = await session.get(Document, document_id)
        assert failed.processing_status == "failed"
        assert failed.processing_stage == "failed"
        assert failed.chunk_count == 0
        assert "injected post-index failure" in failed.processing_error
    cleaned = repository.document_index_counts(document_id)
    assert cleaned["chroma_count"] == cleaned["fts_count"] == 0
    assert cleaned["ids_match"] is True

    # Retry succeeds; repeating the same apply is idempotent by stable IDs.
    assert await reindex.reindex_documents([document_id], False, apply=True) == (1, 0)
    after_retry = repository.document_index_counts(document_id)
    async with factory() as session:
        recovered = await session.get(Document, document_id)
        assert recovered.processing_status == "indexed"
        assert recovered.chunk_count == after_retry["chroma_count"] == after_retry["fts_count"]
    ids_after_retry = set(repository.collection.get(where={"document_id": document_id})["ids"])
    assert await reindex.reindex_documents([document_id], False, apply=True) == (1, 0)
    ids_after_repeat = set(repository.collection.get(where={"document_id": document_id})["ids"])
    assert ids_after_repeat == ids_after_retry
    assert repository.document_index_counts(document_id)["chroma_count"] == prior_count

    # Check exact source page provenance survives the indexing/reindex path.
    stored = repository.collection.get(where={"document_id": document_id}, include=["documents", "metadatas"])
    assert any("BLUEBIRD" in text and meta["page_start"] == 1 for text, meta in zip(stored["documents"], stored["metadatas"]))
    assert any("2039" in text and meta["page_start"] == 2 for text, meta in zip(stored["documents"], stored["metadatas"]))
    await engine.dispose()
    ChromaClientFactory.shutdown_client()

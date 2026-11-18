"""Isolated Phase 2.5 quality evaluation using the locally cached FastEmbed model."""

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")

from rag.chunking.metadata import ChunkMetadata, DocumentChunk
from rag.config.settings import settings
from rag.embeddings.cache import SQLiteEmbeddingCache
from rag.embeddings.embedder import FastEmbedder
from rag.pipelines.query_pipeline import QueryPipeline
from rag.retrieval.query import QueryRequest, RetrievedSource
from rag.retrieval.retriever import ResearchRetriever
from rag.vectorstore.chroma_client import ChromaClientFactory
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.vector_repository import VectorRepository


FIXTURE = Path(__file__).parent / "fixtures" / "phase2_5_quality_v1.json"


def _close_clients(*clients):
    systems = {id(system): system for client in clients if client is not None
               if (system := getattr(client, "_system", None)) is not None}
    for system in systems.values():
        stop = getattr(system, "stop", None)
        if callable(stop):
            stop()
    ChromaClientFactory.reset_client()


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_local_fastembed_retrieval_quality_and_provenance(tmp_path, monkeypatch):
    data = _fixture()
    monkeypatch.setattr(settings, "embedding_provider", "fastembed")
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(settings, "embedding_dimension", 384)
    monkeypatch.setattr(settings, "fastembed_cache_dir", str((Path(__file__).parents[2] / ".model_cache").resolve()))
    monkeypatch.setattr(settings, "embedding_cache_path", str(tmp_path / "embedding-cache.sqlite3"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "chroma_collection_name", "phase25_eval")
    monkeypatch.setattr(settings, "chroma_namespace_by_embedding", True)
    monkeypatch.setattr(settings, "chroma_use_http", False)
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "retrieval_min_score", 0.0)
    monkeypatch.setattr(settings, "retrieval_top_k", 5)
    ChromaClientFactory.reset_client()
    client = ChromaClientFactory.get_client(persist_dir=str(tmp_path / "chroma"), force_new=True)
    repository = VectorRepository(CollectionManager(client=client))
    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "embedding-cache.sqlite3"))

    chunks = []
    for document in data["documents"]:
        for passage in document["passages"]:
            chunk = DocumentChunk(text=passage["text"], metadata=ChunkMetadata(
                chunk_id=passage["chunk_id"], paper_id=document["paper_id"],
                document_id=document["document_id"], page_start=passage["page"],
                page_end=passage["page"], section=passage["section"], chunk_index=len(chunks),
                owner_id="test_user_fixture",
                title=document["title"], filename=document["filename"],
                locator=f"{passage['section']} · page {passage['page']}",
            ))
            chunks.append(chunk)

    # Exercise a cold embedding batch, then a warm cache hit without another inference call.
    started = time.perf_counter()
    cold_vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    cold_seconds = time.perf_counter() - started
    started = time.perf_counter()
    warm_vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    warm_seconds = time.perf_counter() - started
    assert len(cold_vectors) == len(chunks)
    assert all(len(vector) == 384 for vector in cold_vectors)
    assert warm_vectors == cold_vectors
    repository.upsert_chunks(chunks, cold_vectors)
    retriever = ResearchRetriever(embedder=embedder, vector_repo=repository)

    recall_values, reciprocal_ranks = [], []
    citation_tp = citation_fp = citation_fn = page_correct = page_total = 0
    abstention_correct = abstention_total = 0
    case_results = []
    for case in data["cases"]:
        ranked = retriever.retrieve(
            QueryRequest(question=case["question"], paper_ids=case["scope"], top_k=5),
            owner_id="test_user_fixture",
        )
        ranked_ids = [source.chunk_id for source in ranked]
        expected = set(case["relevant_chunk_ids"])
        assert all(source.paper_id in case["scope"] for source in ranked)
        if expected:
            recall_values.append(len(expected.intersection(ranked_ids)) / len(expected))
            reciprocal_ranks.append(1 / (min((ranked_ids.index(cid) + 1 for cid in expected if cid in ranked_ids), default=math.inf)))

        pipeline = QueryPipeline(retriever=retriever)
        result = pipeline.answer_question(case["question"], user_id="test_user_fixture", paper_ids=case["scope"], top_k=5)
        cited_ids = {source.chunk_id for source in result.sources}
        if expected:
            citation_tp += len(cited_ids & expected)
            citation_fp += len(cited_ids - expected)
            citation_fn += len(expected - cited_ids)
            for chunk_id in expected:
                page_total += 1
                citation = next((source for source in result.sources if source.chunk_id == chunk_id), None)
                if citation and citation.page_start == case.get("expected_pages", {}).get(chunk_id):
                    page_correct += 1
        if case.get("abstain_expected"):
            abstention_total += 1
            no_out_of_scope_leak = not any(
                citation.paper_id == case.get("answer_only_outside_scope") for citation in result.sources
            )
            abstained = "insufficient evidence" in result.answer.casefold()
            abstention_correct += int(abstained and no_out_of_scope_leak)
            assert no_out_of_scope_leak
            assert abstained, (case["id"], result.answer)
        if case.get("different_systems_not_conflict"):
            assert result.metadata["research"]["sufficiency"]["status"] != "conflicting"
            assert {"atlas-p2", "boreal-p2"}.issubset(cited_ids)
        if case["id"] == "multi_passage_atlas_profile":
            # The direct factual route must retain both distinct evidence passages.
            assert {"atlas-p1", "atlas-p2"}.issubset(cited_ids)
            assert all("Atlas-Protocol.pdf" == source.filename for source in result.sources)
        if case["id"] in {"absent_recall", "scope_excludes_answer"}:
            assert result.metadata["research"]["sufficiency"]["status"] == "insufficient"
        case_results.append({
            "id": case["id"], "ranked_chunk_ids": ranked_ids,
            "cited_chunk_ids": sorted(cited_ids), "answer_mode": result.metadata.get("answer_mode"),
            "sufficiency": result.metadata.get("research", {}).get("sufficiency", {}).get("status"),
            "citation_pages": {source.chunk_id: source.page_start for source in result.sources},
        })

    counts = repository.document_index_counts("doc-atlas-01")
    assert counts["ids_match"] and counts["chroma_count"] == 2 and counts["fts_count"] == 2
    all_count = repository.collection.count()
    repository.upsert_chunks(chunks, cold_vectors)
    assert repository.collection.count() == all_count == len(chunks)
    assert repository.document_index_counts("doc-boreal-02")["ids_match"]
    with repository._lexical_connection() as connection:
        row_count, unique_count = connection.execute(
            "SELECT count(*), count(DISTINCT chunk_id) FROM lexical_chunks WHERE collection_name=?",
            (repository.collection.name,),
        ).fetchone()
    assert row_count == unique_count == len(chunks)

    metrics = {
        "cases_total": len(data["cases"]),
        "answerable_retrieval_cases": len(recall_values),
        "recall_at_5": round(sum(recall_values) / len(recall_values), 4),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        "citation_precision": round(citation_tp / max(1, citation_tp + citation_fp), 4),
        "citation_recall": round(citation_tp / max(1, citation_tp + citation_fn), 4),
        "page_locator_accuracy": round(page_correct / max(1, page_total), 4),
        "abstention_accuracy": f"{abstention_correct}/{abstention_total}",
        "chroma_count": repository.collection.count(),
        "fts_ids_match": all(repository.document_index_counts(doc["document_id"])["ids_match"] for doc in data["documents"]),
        "embedding_dimension": len(cold_vectors[0]),
        "embedding_cache_warm_equal": warm_vectors == cold_vectors,
        "cold_embedding_seconds": round(cold_seconds, 4),
        "warm_embedding_seconds": round(warm_seconds, 4),
        "collection": repository.collection.name,
        "cases": case_results,
    }
    print("PHASE2_5_METRICS=" + json.dumps(metrics, sort_keys=True))
    _close_clients(client)


def test_response_cache_eviction_preserves_budget_ledger_and_connections_close(tmp_path, monkeypatch):
    from rag.generation.local_state import SQLiteLLMState

    state = SQLiteLLMState(tmp_path / "state.sqlite3")
    monkeypatch.setattr(SQLiteLLMState, "RESPONSE_CACHE_MAX_ROWS", 3)
    for index in range(6):
        state.put_response(f"key-{index}", f"response-{index}")
    with state._connect() as connection:
        assert connection.execute("SELECT count(*) FROM llm_response_cache").fetchone()[0] == 3
    assert state.get_response("key-0") is None
    assert state.get_response("key-5") == "response-5"
    assert state.reserve_call("isolated-test", 2) == 1
    assert state.reserve_call("isolated-test", 2) == 2
    renamed = state.path.with_suffix(".moved")
    state.path.rename(renamed)
    assert renamed.exists()

    cache_path = tmp_path / "embeddings.sqlite3"
    cache = SQLiteEmbeddingCache(cache_path)
    cache.put("model-v1", "fixture passage", [0.1, 0.2])
    assert cache.get("model-v1", "fixture passage") == [0.10000000149011612, 0.20000000298023224]
    cache_path.rename(cache_path.with_suffix(".moved"))


def test_budget_reservations_are_atomic_across_independent_state_instances(tmp_path):
    from rag.generation.local_state import LLMUsageBudgetExceeded, SQLiteLLMState

    path = tmp_path / "shared-budget.sqlite3"
    states = [SQLiteLLMState(path) for _ in range(6)]

    def reserve(index):
        try:
            return states[index % len(states)].reserve_call("isolated-multi-instance", 5)
        except LLMUsageBudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        values = list(pool.map(reserve, range(36)))
    assert sorted(value for value in values if value is not None) == [1, 2, 3, 4, 5]


def test_isolated_chroma_concurrent_query_upsert_delete_retry_and_second_client(tmp_path, monkeypatch):
    from rag.embeddings.embedder import DeterministicMockEmbedder
    from rag.chunking.metadata import ChunkMetadata, DocumentChunk

    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma-concurrency"))
    monkeypatch.setattr(settings, "chroma_collection_name", "phase25_concurrency")
    monkeypatch.setattr(settings, "chroma_namespace_by_embedding", False)
    monkeypatch.setattr(settings, "embedding_provider", "mock")
    monkeypatch.setattr(settings, "embedding_model", "phase25-test-384")
    ChromaClientFactory.reset_client()
    path = str(tmp_path / "chroma-concurrency")
    client = ChromaClientFactory.get_client(persist_dir=path, force_new=True)
    repository = VectorRepository(CollectionManager(client=client))
    embedder = DeterministicMockEmbedder(384)
    chunks = [DocumentChunk(text=f"Concurrency fixture passage {i} with unique token marker{i}.", metadata=ChunkMetadata(
        chunk_id=f"stress-{i}", paper_id="stress-paper", document_id="stress-document", page_start=i + 1,
        page_end=i + 1, section="Results", chunk_index=i, filename="stress.pdf", locator=f"Page {i+1}", owner_id="test_user_fixture"))
        for i in range(4)]
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    repository.upsert_chunks(chunks, vectors)
    errors = []
    second_client = None
    second_collection = None
    second_client_result = "unsupported"
    try:
        second_client = ChromaClientFactory.get_client(persist_dir=path, force_new=True)
        second_collection = CollectionManager(client=second_client).get_or_create_collection()
        second_client_result = "supported"
    except Exception as exc:
        second_client_result = f"unsupported: {type(exc).__name__}"

    def retrieve_repeatedly():
        for _ in range(16):
            try:
                repository.query_vectors(embedder.embed_query("fixture marker2"), top_k=4)
            except Exception as exc:  # capture the historic Chroma error without hiding it
                errors.append(f"{type(exc).__name__}: {exc}")

    def retry_indexing():
        for _ in range(8):
            try:
                repository.upsert_chunks(chunks, vectors)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

    def retrieve_from_second_client():
        for _ in range(16):
            try:
                second_collection.query(query_embeddings=[embedder.embed_query("fixture marker2")],
                    n_results=4, include=["documents", "metadatas", "distances"])
            except Exception as exc:
                errors.append(f"second-client {type(exc).__name__}: {exc}")

    def cleanup_and_retry():
        for _ in range(5):
            try:
                repository.delete_document_chunks("stress-document")
                repository.upsert_chunks(chunks, vectors)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

    workers = [retrieve_repeatedly, retry_indexing, cleanup_and_retry]
    if second_collection is not None:
        workers.append(retrieve_from_second_client)
    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futures = [pool.submit(worker) for worker in workers]
        for future in futures:
            future.result()
    if second_collection is not None:
        second_client_result += ", concurrent queries completed"

    repository.delete_document_chunks("stress-document")
    repository.upsert_chunks(chunks, vectors)
    counts = repository.document_index_counts("stress-document")
    assert counts["ids_match"] and counts["chroma_count"] == counts["fts_count"] == len(chunks)
    with repository._lexical_connection() as connection:
        rows, unique_rows = connection.execute(
            "SELECT count(*), count(DISTINCT chunk_id) FROM lexical_chunks WHERE collection_name=? AND document_id=?",
            (repository.collection.name, "stress-document"),
        ).fetchone()
    assert rows == unique_rows == len(chunks)
    assert not any("Error finding id" in error for error in errors), errors
    print("PHASE2_5_CHROMA=" + json.dumps({"concurrent_errors": errors,
        "historic_error_reproduced": any("Error finding id" in error for error in errors),
        "second_client": second_client_result, "final_counts": counts}, sort_keys=True))
    _close_clients(client, second_client)


def test_direct_fact_quotes_all_requested_top_k_evidence_and_abstains_on_partial(monkeypatch):
    from rag.research.orchestrator import ResearchPlan

    monkeypatch.setattr(settings, "llm_provider", "gemini")

    class TwoPassageRetriever:
        def retrieve(self, _request, *args, **kwargs):
            return [
                RetrievedSource(source_id="S1", chunk_id="id-p1", paper_id="p", document_id="d", page_start=1,
                    page_end=1, section="Methods", text="Atlas identifier is AX-17A.", score=.9, filename="atlas.pdf", locator="Methods · page 1"),
                RetrievedSource(source_id="S2", chunk_id="id-p2", paper_id="p", document_id="d", page_start=2,
                    page_end=2, section="Results", text="Atlas accuracy was 91.2 percent on 2024-03-14.", score=.8, filename="atlas.pdf", locator="Results · page 2"),
            ]

    class FixedPlanner:
        def plan(self, question, *_args):
            return ResearchPlan(question=question, intent="direct", search_queries=[question], max_retrieval_rounds=1)

    pipeline = QueryPipeline(retriever=TwoPassageRetriever(), planner=FixedPlanner())
    direct = pipeline.answer_question("What identifier and accuracy were reported?", user_id="u", paper_ids=["p"], top_k=5)
    assert {source.chunk_id for source in direct.sources} == {"id-p1", "id-p2"}
    assert {source.page_start for source in direct.sources} == {1, 2}

    class PartialSufficiency:
        def assess(self, *_args):
            from rag.research.orchestrator import SufficiencyAssessment
            return SufficiencyAssessment(status="partial", coverage=.2, missing_terms=["accuracy"])

    partial = QueryPipeline(retriever=TwoPassageRetriever(), planner=FixedPlanner(), sufficiency_checker=PartialSufficiency())
    result = partial.answer_question("What is the exact quantum recall?", paper_ids=["p"], user_id="u")
    assert result.metadata["answer_mode"] == "evidence_only"
    assert result.metadata["generation_reason"] == "insufficient_evidence"
    assert "insufficient evidence" in result.answer.casefold()


def test_comparison_uses_configured_generation_adapter_and_valid_citations(tmp_path, monkeypatch):
    from rag.generation.generator import GroundedGenerator
    from rag.generation.llm_client import BaseLLMClient

    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "phase25-deterministic-adapter")
    monkeypatch.setattr(settings, "llm_daily_call_budget", 5)
    monkeypatch.setattr(settings, "embedding_cache_path", str(tmp_path / "generation-state.sqlite3"))

    class DeterministicAdapter(BaseLLMClient):
        api_key = "test-only"
        supports_streaming = False
        def __init__(self): self.calls = 0
        def generate(self, *_args, **_kwargs):
            self.calls += 1
            return "Atlas reported 91.2 percent accuracy [S1]. Boreal reported 87.6 percent accuracy [S2]."

    class FixedRetriever:
        def retrieve(self, _request, *args, **kwargs):
            return [
                RetrievedSource(source_id="S1", chunk_id="atlas-p2", paper_id="paper-atlas-01", document_id="doc-atlas-01",
                    page_start=2, page_end=2, section="Results", text="Atlas reported an accuracy of 91.2 percent on 2024-03-14 using 64 nodes.",
                    score=.9, filename="Atlas-Protocol.pdf", locator="Results · page 2"),
                RetrievedSource(source_id="S2", chunk_id="boreal-p2", paper_id="paper-boreal-02", document_id="doc-boreal-02",
                    page_start=2, page_end=2, section="Results", text="Boreal reported an accuracy of 87.6 percent on 2024-04-02 using 96 nodes.",
                    score=.8, filename="Boreal-Protocol.pdf", locator="Results · page 2"),
            ]

    adapter = DeterministicAdapter()
    result = QueryPipeline(retriever=FixedRetriever(), generator=GroundedGenerator(adapter)).answer_question(
        "Compare Atlas and Boreal reported accuracy values.",
        paper_ids=["paper-atlas-01", "paper-boreal-02"], user_id="quality-test-user")
    assert adapter.calls == 1
    assert result.metadata["answer_mode"] == "generated"
    assert result.metadata["generation_provider"] == "gemini"
    assert {source.chunk_id for source in result.sources} == {"atlas-p2", "boreal-p2"}
    assert {source.filename for source in result.sources} == {"Atlas-Protocol.pdf", "Boreal-Protocol.pdf"}
    assert {source.page_start for source in result.sources} == {2}

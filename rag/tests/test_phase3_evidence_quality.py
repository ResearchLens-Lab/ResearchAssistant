"""Versioned local-only Phase 3 retrieval and evidence-verification checks."""
import json
import math
import re
from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")

from rag.chunking.metadata import ChunkMetadata, DocumentChunk
from rag.config.settings import settings
from rag.embeddings.cache import SQLiteEmbeddingCache
from rag.embeddings.embedder import FastEmbedder
from rag.pipelines.query_pipeline import QueryPipeline
from rag.research.claim_verifier import ClaimEvidenceVerifier
from rag.research.orchestrator import EvidenceSufficiencyChecker
from rag.retrieval.query import QueryRequest, RetrievedSource
from rag.retrieval.retriever import ResearchRetriever
from rag.vectorstore.chroma_client import ChromaClientFactory
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.vector_repository import VectorRepository

FIXTURE = Path(__file__).parent / "fixtures" / "phase3_quality_v1.json"


def _close(client):
    system = getattr(client, "_system", None)
    stop = getattr(system, "stop", None)
    if callable(stop):
        stop()
    ChromaClientFactory.reset_client()


def test_phase3_local_retrieval_scope_citations_conflicts_and_verification(tmp_path, monkeypatch):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    monkeypatch.setattr(settings, "embedding_provider", "fastembed")
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(settings, "embedding_dimension", 384)
    monkeypatch.setattr(settings, "fastembed_cache_dir", str((Path(__file__).parents[2] / ".model_cache").resolve()))
    monkeypatch.setattr(settings, "embedding_cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "chroma_collection_name", "phase3_eval")
    monkeypatch.setattr(settings, "chroma_namespace_by_embedding", True)
    monkeypatch.setattr(settings, "chroma_use_http", False)
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "retrieval_min_score", 0.0)
    monkeypatch.setattr(settings, "retrieval_top_k", 5)
    ChromaClientFactory.reset_client()
    client = ChromaClientFactory.get_client(persist_dir=str(tmp_path / "chroma"), force_new=True)
    repo = VectorRepository(CollectionManager(client=client))
    embedder = FastEmbedder(cache=SQLiteEmbeddingCache(tmp_path / "cache.sqlite3"))

    chunks = []
    by_chunk = {}
    for document in data["documents"]:
        for index, passage in enumerate(document["passages"]):
            chunk = DocumentChunk(text=passage["text"], metadata=ChunkMetadata(
                chunk_id=passage["chunk_id"], paper_id=document["paper_id"],
                document_id=document["document_id"], page_start=passage["page"], page_end=passage["page"],
                section="Results", chunk_index=index, filename=document["filename"],
                title=document["filename"], locator=f"Results · page {passage['page']}", owner_id="test_user_fixture"))
            chunks.append(chunk)
            by_chunk[passage["chunk_id"]] = passage
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    assert len(vectors) == len(chunks) and all(len(vector) == 384 for vector in vectors)
    repo.upsert_chunks(chunks, vectors)
    retriever = ResearchRetriever(embedder=embedder, vector_repo=repo)

    recalls, reciprocal_ranks = [], []
    citation_tp = citation_fp = citation_fn = page_ok = page_total = 0
    abstentions = []
    case_results = []
    for case in data["retrieval_cases"]:
        result = retriever.retrieve(
            QueryRequest(question=case["question"], paper_ids=case["scope"], top_k=5),
            owner_id="test_user_fixture",
        )
        ids = [source.chunk_id for source in result]
        assert all(source.paper_id in case["scope"] for source in result), case["id"]
        expected = set(case["relevant_chunk_ids"])
        if expected:
            recalls.append(len(expected & set(ids)) / len(expected))
            reciprocal_ranks.append(1 / min(ids.index(chunk_id) + 1 for chunk_id in expected if chunk_id in ids))
        pipeline_result = QueryPipeline(retriever=retriever).answer_question(
            case["question"], user_id="test_user_fixture", paper_ids=case["scope"]
        )
        cited = {source.chunk_id for source in pipeline_result.sources}
        if expected:
            citation_tp += len(expected & cited)
            citation_fp += len(cited - expected)
            citation_fn += len(expected - cited)
            for chunk_id, page in case.get("pages", {}).items():
                page_total += 1
                found = next((source for source in pipeline_result.sources if source.chunk_id == chunk_id), None)
                page_ok += int(found is not None and found.page_start == page and found.filename is not None)
        if case.get("abstain"):
            good = pipeline_result.metadata["research"]["sufficiency"]["status"] == "insufficient"
            abstentions.append(good)
            assert good, (case["id"], pipeline_result.metadata)
        case_results.append({"id": case["id"], "retrieved": ids, "cited": sorted(cited), "expected": sorted(expected)})

    source_by_id = {}
    for document in data["documents"]:
        for passage in document["passages"]:
            source_by_id[passage["chunk_id"]] = RetrievedSource(
                source_id="S1", chunk_id=passage["chunk_id"], paper_id=document["paper_id"],
                document_id=document["document_id"], page_start=passage["page"], page_end=passage["page"],
                section="Results", text=passage["text"], filename=document["filename"], locator=f"page:{passage['page']}",
            )
    checker = EvidenceSufficiencyChecker()
    conflict_results = {}
    legacy_conflicts = {}
    for case in data["conflict_cases"]:
        sources = [source_by_id[chunk_id] for chunk_id in case["source_chunks"]]
        assessment = checker.assess("What reported accuracy or precision values?", sources)
        actual = assessment.status == "conflicting"
        conflict_results[case["id"]] = actual
        assert actual is case["conflict"], (case["id"], assessment.model_dump())
        # Reproduce the previous metric-only, cross-paper rule on the same gold
        # cases to make the conflict-classifier baseline comparable.
        old_by_metric = {}
        for source in sources:
            for metric in ("accuracy", "precision", "recall", "bleu", "f1", "error rate"):
                values = re.findall(
                    rf"\b{re.escape(metric)}\b[^.\n]{{0,50}}?\b(\d+(?:\.\d+)?)\s*(?:%|percent)?",
                    source.text, re.I,
                )
                if values:
                    old_by_metric.setdefault(metric, {}).setdefault(source.paper_id, set()).update(values)
        legacy_conflicts[case["id"]] = any(
            len(set().union(*papers.values())) > 1 and len(papers) > 1
            for papers in old_by_metric.values()
        )
    legacy_accuracy = sum(legacy_conflicts[case["id"]] is case["conflict"] for case in data["conflict_cases"])
    assert legacy_accuracy == 2

    verifier = ClaimEvidenceVerifier()
    atlas = source_by_id["atlas-metric"]
    wrong_decimal = verifier.verify("Atlas accuracy was 91 percent on 2024-03-14 [S1].", [atlas], ["atlas"])
    assert wrong_decimal.items[0].status == "contradicted"
    unrelated_date = verifier.verify("Atlas accuracy was 91.2 percent on 2024-03-15 [S1].", [atlas], ["atlas"])
    assert unrelated_date.items[0].status == "unsupported"
    wrong_identifier = verifier.verify("Atlas identifier was AX-19A [S1].", [source_by_id["atlas-id"]], ["atlas"])
    assert wrong_identifier.items[0].status == "contradicted"

    counts = repo.document_index_counts("atlas-doc")
    assert counts["ids_match"] and counts["chroma_count"] == counts["fts_count"] == 2
    all_counts = repo.document_index_counts("within-doc")
    assert all_counts["ids_match"] and all_counts["chroma_count"] == all_counts["fts_count"] == 2
    metrics = {
        "fixture": FIXTURE.name, "retrieval_cases": len(data["retrieval_cases"]),
        "answerable_cases": len(recalls), "recall_at_5": round(sum(recalls) / len(recalls), 4),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        "citation_precision": round(citation_tp / max(1, citation_tp + citation_fp), 4),
        "citation_recall": round(citation_tp / max(1, citation_tp + citation_fn), 4),
        "page_locator_accuracy": round(page_ok / max(1, page_total), 4),
        "abstention_accuracy": f"{sum(abstentions)}/{len(abstentions)}",
        "cases": case_results,
        "conflict_cases": conflict_results, "legacy_conflict_accuracy": f"{legacy_accuracy}/{len(data['conflict_cases'])}",
        "collection_count": repo.collection.count(),
        "atlas_ids_match": counts["ids_match"], "within_doc_ids_match": all_counts["ids_match"],
    }
    print("PHASE3_QUALITY_METRICS=" + json.dumps(metrics, sort_keys=True))
    _close(client)

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.models.document import Document
from backend.app.models.knowledge_graph import KGGraphCandidate, KGGraphEvidence, KGImportRun, KGNode, KGRelationship
from backend.app.models.paper import Paper
from backend.app.models.user import User
from backend.app.services.knowledge_graph_service import GraphValidationError, KnowledgeGraphService
from rag.document_intelligence.models import DocumentIntelligence, KnowledgeRecord
from rag.document_intelligence.store import ExtractionStore


@pytest.fixture
def graph_source(tmp_path):
    owner_id, paper_id, document_id = str(uuid4()), str(uuid4()), str(uuid4())
    page = "We propose Dynamic Programming. We use Greedy Algorithm."
    parts = [("method", "We propose Dynamic Programming."), ("method", "We use Greedy Algorithm.")]
    records = []
    start = 0
    for i, (category, sentence) in enumerate(parts):
        position = page.index(sentence, start)
        records.append(KnowledgeRecord(record_id=f"record-{i}", category=category, exact_text=sentence,
            document_id=document_id, page_number=1, section_id="section-methods", block_id=f"block-{i}",
            char_start=position, char_end=position+len(sentence), extraction_method="fixture",
            extraction_version="phase4-rules-1", confidence=.55, uncertainty="synthetic fixture"))
        start = position + len(sentence)
    snapshot = DocumentIntelligence(run_id="fixture-run", content_hash="a"*64, document_id=document_id,
        paper_id=paper_id, filename="synthetic.txt", file_type="txt", title="Synthetic fixture",
        page_count=1, extraction_status="complete", pages=[{"page_number": 1, "text": page}],
        knowledge_records=records)
    store = ExtractionStore(tmp_path / "phase4")
    store.save(snapshot)
    for record in records:
        store.review(document_id, snapshot.run_id, record.record_id, "approve", "fixture-reviewer")
    return owner_id, paper_id, document_id, snapshot, store


async def _seed_owner(session, owner_id, paper_id, document_id):
    session.add(User(id=owner_id, email=f"{owner_id}@example.invalid", hashed_password="synthetic-test"))
    session.add(Paper(id=paper_id, owner_id=owner_id, title="Synthetic fixture paper"))
    session.add(Document(id=document_id, paper_id=paper_id, filename="synthetic.txt", storage_path="fixture",
                         content_type="text/plain", file_size=64))
    await session.commit()


@pytest.mark.asyncio
async def test_approved_only_import_review_graph_traversal_and_audit(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        plan = await service.import_plan(owner_id, document_id, snapshot.run_id)
        assert plan["candidate_count"] == 2
        assert (await session.scalar(select(func.count()).select_from(KGImportRun))) == 0
        imported = await service.import_approved(owner_id, document_id, snapshot.run_id)
        await session.commit()
        repeated = await service.import_approved(owner_id, document_id, snapshot.run_id)
        assert repeated["idempotent"] is True
        candidates = await service.list_candidates(owner_id)
        assert len(candidates) == 2
        first = await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Dynamic Programming")
        second = await service.review_candidate(owner_id, candidates[1].id, "approve_node", "reviewer", "METHOD", "Greedy Algorithm")
        edge = await service.add_relationship(owner_id, candidates[0].id, first["node_id"], "RELATED_TO", second["node_id"], "reviewer")
        await session.commit()
        neighborhood = await service.neighborhood(owner_id, first["node_id"], depth=2)
        assert {node.id for node in neighborhood["nodes"]} == {second["node_id"]}
        path = await service.find_path(owner_id, first["node_id"], second["node_id"])
        assert path and path["steps"][0]["relationship"].id == edge.id
        version = edge.version
        await service.correct_relationship(owner_id, edge.id, first["node_id"], "RELATED_TO", second["node_id"], "corrector")
        assert edge.version == version + 1
        await service.set_relationship_status(owner_id, edge.id, "disputed", "reviewer", "conflicting evidence")
        assert await service.find_path(owner_id, first["node_id"], second["node_id"]) is None
        await service.set_relationship_status(owner_id, edge.id, "current", "reviewer", "resolved after review")
        await session.commit()
        audit = await service.audit(owner_id)
        assert audit["node_counts_by_type"] == {"CONCEPT": 1, "METHOD": 1}
        assert audit["edge_counts_by_type"] == {"RELATED_TO": 1}
        assert audit["evidence_count"] == 3
        assert not audit["integrity_issues"]
        assert audit["provenance_coverage"] == 1.0


@pytest.mark.asyncio
async def test_invalid_edge_types_owner_scope_and_private_evidence_filter(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        await service.import_approved(owner_id, document_id, snapshot.run_id)
        candidates = await service.list_candidates(owner_id)
        first = await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Concept A")
        second = await service.review_candidate(owner_id, candidates[1].id, "approve_node", "reviewer", "PERSON", "Person B")
        with pytest.raises(GraphValidationError, match="does not allow"):
            await service.add_relationship(owner_id, candidates[0].id, first["node_id"], "AUTHORED_BY", second["node_id"], "reviewer")
        with pytest.raises(GraphValidationError, match="Unknown active graph node"):
            await service.node_detail(str(uuid4()), first["node_id"])
        await session.commit()


@pytest.mark.asyncio
async def test_phase4_rejection_after_import_blocks_graph_approval(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        await service.import_approved(owner_id, document_id, snapshot.run_id)
        candidate = (await service.list_candidates(owner_id))[0]
        store.review(document_id, snapshot.run_id, candidate.record_id, "reject", "later-reviewer")
        with pytest.raises(GraphValidationError, match="no longer approved"):
            await service.review_candidate(owner_id, candidate.id, "approve_node", "reviewer", "CONCEPT", "Stale concept")
        assert (await session.scalar(select(func.count()).select_from(KGNode))) == 0


@pytest.mark.asyncio
async def test_later_phase4_rejection_hides_previously_accepted_graph_assertions(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        await service.import_approved(owner_id, document_id, snapshot.run_id)
        candidates = await service.list_candidates(owner_id)
        first = await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Concept A")
        second = await service.review_candidate(owner_id, candidates[1].id, "approve_node", "reviewer", "CONCEPT", "Concept B")
        await service.add_relationship(owner_id, candidates[0].id, first["node_id"], "RELATED_TO", second["node_id"], "reviewer")
        await session.commit()
        store.review(document_id, snapshot.run_id, candidates[0].record_id, "reject", "later-reviewer")
        with pytest.raises(GraphValidationError, match="Unknown active graph node"):
            await service.node_detail(owner_id, first["node_id"])
        with pytest.raises(GraphValidationError, match="Unknown active graph node"):
            await service.find_path(owner_id, first["node_id"], second["node_id"])


@pytest.mark.asyncio
async def test_older_extraction_run_cannot_be_imported_after_a_newer_run(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    latest = snapshot.model_copy(update={"run_id": "later-run", "content_hash": "c"*64})
    store.save(latest)
    for record in latest.knowledge_records:
        store.review(document_id, latest.run_id, record.record_id, "approve", "later-reviewer")
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        with pytest.raises(GraphValidationError, match="current successful Phase 4 run"):
            await service.import_plan(owner_id, document_id, snapshot.run_id)
        assert await session.scalar(select(func.count()).select_from(KGImportRun)) == 0


@pytest.mark.asyncio
async def test_private_source_requires_opt_in_and_is_filtered_from_queries(db_engine, graph_source, tmp_path):
    owner_id, paper_id, document_id, snapshot, _ = graph_source
    private_store = ExtractionStore(tmp_path / "private-phase4")
    private_snapshot = snapshot.model_copy(update={"run_id": "private-run", "content_hash": "b"*64, "private_source": True})
    private_store.save(private_snapshot)
    for record in private_snapshot.knowledge_records:
        private_store.review(document_id, private_snapshot.run_id, record.record_id, "approve", "private-reviewer")
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, private_store)
        with pytest.raises(GraphValidationError, match="allow-private"):
            await service.import_plan(owner_id, document_id, private_snapshot.run_id)
        await service.import_approved(owner_id, document_id, private_snapshot.run_id, allow_private=True)
        candidates_hidden = await service.list_candidates(owner_id)
        candidates = await service.list_candidates(owner_id, allow_private=True)
        assert candidates_hidden == [] and len(candidates) == 2
        with pytest.raises(GraphValidationError, match="allow-private"):
            await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Private concept")
        promoted = await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Private concept", allow_private=True)
        assert await service.node_evidence(owner_id, promoted["node_id"]) == []
        assert len(await service.node_evidence(owner_id, promoted["node_id"], allow_private=True)) == 1


@pytest.mark.asyncio
async def test_merge_and_undo_preserve_edges_and_evidence(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        await service.import_approved(owner_id, document_id, snapshot.run_id)
        candidates = await service.list_candidates(owner_id)
        a = await service.review_candidate(owner_id, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Dynamic Programming")
        b = await service.review_candidate(owner_id, candidates[1].id, "approve_node", "reviewer", "CONCEPT", "Dynamic Programming Variant")
        target = KGNode(owner_id=owner_id, node_type="METHOD", canonical_name="Example Method",
            identity_key="example method", identifiers={}, metadata_json={}, first_document_id=document_id,
            first_extraction_run_id=snapshot.run_id, review_status="approved")
        session.add(target); await session.flush()
        session.add(service._evidence_for_node(owner_id, target.id, candidates[0], "reviewer")); await session.flush()
        edge = await service.add_relationship(owner_id, candidates[1].id, b["node_id"], "RELATED_TO", target.id, "reviewer")
        decision = await service.merge_nodes(owner_id, a["node_id"], b["node_id"], "reviewer", "reviewed duplicate")
        await session.flush()
        assert edge.source_node_id == a["node_id"]
        assert await service.node_evidence(owner_id, a["node_id"])
        undone = await service.undo_merge(owner_id, decision.id, "reviewer", "undo for test")
        await session.flush()
        assert undone.decision == "undo_merge"
        assert edge.source_node_id == b["node_id"]
        assert (await service.node_detail(owner_id, b["node_id"])).merged_into_id is None


@pytest.mark.asyncio
async def test_import_rollback_preserves_history_and_is_idempotent(db_engine, graph_source):
    owner_id, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed_owner(session, owner_id, paper_id, document_id)
        service = KnowledgeGraphService(session, store)
        imported = await service.import_approved(owner_id, document_id, snapshot.run_id)
        await session.commit()
        result = await service.rollback_import(owner_id, imported["import_run_id"], "reviewer", "withdraw import")
        repeated = await service.rollback_import(owner_id, imported["import_run_id"], "reviewer", "repeat")
        await session.commit()
        assert result["status"] == "rolled_back"
        assert repeated["idempotent"] is True
        assert await service.list_candidates(owner_id) == []
        assert len(await service.list_candidates(owner_id, status="rolled_back")) == 2


def test_relationship_endpoint_validation_is_explicit():
    from backend.app.services.knowledge_graph_service import validate_relationship
    validate_relationship("PAPER", "AUTHORED_BY", "PERSON")
    with pytest.raises(GraphValidationError):
        validate_relationship("PERSON", "AUTHORED_BY", "PAPER")


async def test_graph_api_requires_auth_and_scopes_graph_statistics(client, auth_headers, second_user_headers):
    unauthenticated = await client.get("/api/v1/knowledge-graph/status")
    assert unauthenticated.status_code == 401
    own = await client.get("/api/v1/knowledge-graph/status", headers=auth_headers)
    other = await client.get("/api/v1/knowledge-graph/status", headers=second_user_headers)
    assert own.status_code == 200 and other.status_code == 200
    assert own.json()["node_counts_by_type"] == {}
    assert other.json()["node_counts_by_type"] == {}


async def test_graph_import_endpoint_requires_explicit_confirmation(client, auth_headers):
    response = await client.post("/api/v1/knowledge-graph/imports", headers=auth_headers,
        json={"document_id": str(uuid4()), "extraction_run_id": "selected-run", "confirm": False})
    assert response.status_code == 400

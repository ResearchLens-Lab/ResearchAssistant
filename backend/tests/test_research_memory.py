from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.models.conversation import Conversation
from backend.app.models.knowledge_graph import KGGraphEvidence, KGNode, KGRelationship, KGGraphCandidate
from backend.app.models.research_memory import MemoryRecord, MemorySourceEvidence, MemoryObservationEvent
from backend.app.models.user import User
from backend.app.models.paper import Paper
from backend.app.models.document import Document
from backend.app.services.knowledge_graph_service import KnowledgeGraphService
from backend.app.services.research_memory_service import MemoryValidationError, ResearchMemoryService
from backend.app.services.research_memory_evaluation import evaluate_memory_fixture
from rag.document_intelligence.store import ExtractionStore
from backend.tests.test_knowledge_graph import graph_source


def test_synthetic_memory_evaluation_reports_bounded_metrics():
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / "fixtures" / "phase6_synthetic_memory.json").read_text(encoding="utf-8"))
    result = evaluate_memory_fixture(fixture, k=3)
    assert result["sample_sizes"]["retrieval_queries"] == 2
    assert result["retrieval"]["recall@3"] == 1.0
    assert result["associations"]["false_association_rate"] == 0.0
    assert result["contradictions"]["false_candidate_rate"] == 0.25
    assert result["research_gaps"]["type_and_recording_accuracy"] == 1.0
    assert result["temporal"]["check_accuracy"] == 1.0


@pytest.mark.asyncio
async def test_formation_is_explicit_idempotent_provenance_aware_and_searchable(db_engine, graph_source):
    owner, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(User(id=owner, email=f"{owner}@example.invalid", hashed_password="synthetic"))
        db.add(Paper(id=paper_id, owner_id=owner, title="Synthetic fixture paper"))
        db.add(Document(id=document_id, paper_id=paper_id, filename="fixture.txt", storage_path="fixture",
                        content_type="text/plain", file_size=100))
        await db.commit()
        graph = KnowledgeGraphService(db, store)
        await graph.import_approved(owner, document_id, snapshot.run_id)
        candidates = await graph.list_candidates(owner)
        nodes = []
        for candidate, kind, title in zip(candidates, ["CONCEPT", "METHOD"], ["Dynamic Programming", "Greedy Algorithm"]):
            reviewed = await graph.review_candidate(owner, candidate.id, "approve_node", "reviewer", kind, title)
            nodes.append(reviewed["node_id"])
        edge = await graph.add_relationship(owner, candidates[0].id, nodes[0], "RELATED_TO", nodes[1], "reviewer")
        await db.commit()

        memory = ResearchMemoryService(db, KnowledgeGraphService(db, store))
        empty = await memory.formation_preview(owner, [], [])
        assert empty["status"] == "no_eligible_real_inputs"
        preview = await memory.formation_preview(owner, nodes, [edge.id])
        assert preview["eligible_count"] == 3
        formed = await memory.form(owner, nodes, [edge.id])
        assert formed["created_count"] == 3
        await db.commit()
        repeated = await memory.form(owner, nodes, [edge.id])
        assert repeated["idempotent"] is True
        assert await db.scalar(select(func.count()).select_from(MemoryRecord).where(MemoryRecord.owner_id == owner,
            MemoryRecord.memory_type == "SEMANTIC")) == 3
        assert await db.scalar(select(func.count()).select_from(MemorySourceEvidence).join(MemoryRecord).where(MemoryRecord.owner_id == owner)) >= 6
        assert await db.scalar(select(func.count()).select_from(MemoryObservationEvent).where(MemoryObservationEvent.owner_id == owner)) >= 6
        result = await memory.search(owner, "Dynamic Programming")
        assert result["direct_evidence"]
        assert all(row["evidence"] for row in result["direct_evidence"])
        assert any("Dynamic Programming" in row["title"] for row in result["direct_evidence"])
        associations = await memory.list_associations(owner, "CANDIDATE")
        assert associations and associations[0]["supporting_sources"] and associations[0]["evidence_current"]
        reviewed = await memory.review_association(owner, associations[0]["association"].id, "confirm", owner)
        assert reviewed.status == "CONFIRMED_ASSOCIATION"
        connected = await memory.search(owner, "Dynamic Programming")
        assert any(item["established_fact"] and item["supporting_sources"] for item in connected["related_connections"])
        before = await db.scalar(select(MemoryRecord).where(MemoryRecord.owner_id == owner,
            MemoryRecord.memory_type == "SEMANTIC", MemoryRecord.title == "Dynamic Programming"))
        graph_service = KnowledgeGraphService(db, store)
        await graph_service.correct_node(owner, nodes[0], "Dynamic Programming Corrected", "CONCEPT", "reviewer")
        await db.commit()
        corrected = await memory.form(owner, nodes, [edge.id])
        assert corrected["idempotent"] is False
        await db.commit()
        after = await db.get(MemoryRecord, before.id)
        assert after.title == "Dynamic Programming Corrected"
        history = await memory.history(owner, before.id)
        assert any(event.event_type == "CORRECTION_OBSERVED" for event in history)


@pytest.mark.asyncio
async def test_session_memory_requires_opt_in_and_owner_scoping(db_engine, graph_source):
    owner, paper_id, document_id, snapshot, store = graph_source
    conversation_id = str(uuid4())
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(User(id=owner, email=f"{owner}@example.invalid", hashed_password="synthetic"))
        db.add(Paper(id=paper_id, owner_id=owner, title="Synthetic fixture paper"))
        db.add(Document(id=document_id, paper_id=paper_id, filename="fixture.txt", storage_path="fixture",
                        content_type="text/plain", file_size=100))
        db.add(Conversation(id=conversation_id, user_id=owner, title="Synthetic research"))
        await db.commit()
        graph = KnowledgeGraphService(db, store)
        await graph.import_approved(owner, document_id, snapshot.run_id)
        candidates = await graph.list_candidates(owner)
        item = await graph.review_candidate(owner, candidates[0].id, "approve_node", "reviewer", "CONCEPT", "Dynamic Programming")
        await db.commit()
        evidence_id = await db.scalar(select(KGGraphEvidence.id).where(KGGraphEvidence.node_id == item["node_id"]))
        service = ResearchMemoryService(db, KnowledgeGraphService(db, store))
        with pytest.raises(MemoryValidationError, match="opt-in"):
            await service.capture_session_observation(owner, conversation_id, "review this concept", [evidence_id])
        await service.set_session_opt_in(owner, conversation_id, True)
        captured = await service.capture_session_observation(owner, conversation_id, "review this concept", [evidence_id])
        assert captured.privacy_classification == "SESSION"
        await db.commit()
        deleted = await service.delete_session_memory(owner, captured.id, owner)
        assert deleted["audit_retained"] is True


@pytest.mark.asyncio
async def test_opposed_reviewed_assertions_remain_candidates_until_reviewer_resolution(db_engine, graph_source):
    owner, paper_id, document_id, snapshot, store = graph_source
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        db.add(User(id=owner, email=f"{owner}@example.invalid", hashed_password="synthetic"))
        db.add(Paper(id=paper_id, owner_id=owner, title="Synthetic fixture paper"))
        db.add(Document(id=document_id, paper_id=paper_id, filename="fixture.txt", storage_path="fixture",
                        content_type="text/plain", file_size=100))
        await db.commit()
        graph = KnowledgeGraphService(db, store)
        await graph.import_approved(owner, document_id, snapshot.run_id)
        candidates = await graph.list_candidates(owner)
        finding = await graph.review_candidate(owner, candidates[0].id, "approve_node", "reviewer", "FINDING", "Finding A")
        claim = await graph.review_candidate(owner, candidates[1].id, "approve_node", "reviewer", "CLAIM", "Claim B")
        support = await graph.add_relationship(owner, candidates[0].id, finding["node_id"], "SUPPORTS", claim["node_id"], "reviewer")
        conflict = await graph.add_relationship(owner, candidates[1].id, finding["node_id"], "CONTRADICTS", claim["node_id"], "reviewer")
        await db.commit()
        service = ResearchMemoryService(db, KnowledgeGraphService(db, store))
        await service.form(owner, [finding["node_id"], claim["node_id"]], [support.id, conflict.id])
        await db.commit()
        from backend.app.models.research_memory import MemoryContradiction
        row = await db.scalar(select(MemoryContradiction).where(MemoryContradiction.owner_id == owner))
        assert row is not None and row.status == "CANDIDATE"
        candidates_view = await service.list_contradictions(owner, "CANDIDATE")
        assert len(candidates_view) == 1
        assert len(candidates_view[0]["assertions"]) == 2
        assert all(assertion["evidence"] for assertion in candidates_view[0]["assertions"])
        resolved = await service.resolve_contradiction(owner, row.id, "TRUE_CONFLICT", {"dataset": "same synthetic fixture"}, owner)
        assert resolved.status == "TRUE_CONFLICT"
        await db.commit()
        assert (await db.get(KGRelationship, support.id)).assertion_status == "disputed"
        assert (await db.get(KGRelationship, conflict.id)).assertion_status == "disputed"

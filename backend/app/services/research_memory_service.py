from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.base import utcnow
from backend.app.models.knowledge_graph import KGGraphEvidence, KGNode, KGRelationship
from backend.app.models.research_memory import (
    MemoryAssociation, MemoryContradiction, MemoryGraphReference,
    MemoryObservationEvent, MemoryProcessingRun, MemoryRecord,
    MemoryResearchGap, MemoryReviewEvent, MemorySourceEvidence,
    MemorySessionOptIn,
)
from backend.app.models.conversation import Conversation
from backend.app.services.knowledge_graph_service import KnowledgeGraphService

MEMORY_TYPES = {"EPISODIC", "SEMANTIC", "SOURCE", "TEMPORAL", "ASSOCIATIVE", "CONTRADICTION", "RESEARCH_GAP"}
MAX_LIMIT = 100
MAX_FORMATION_SCOPE = 200
ASSOCIATION_SCORING = {"shared_reviewed_entity": 0.35, "maximum": 1.0}


class MemoryValidationError(ValueError):
    pass


def _terms(s: str) -> set[str]:
    return {t for t in re.findall(r"[\w-]+", s.casefold()) if len(t) > 2}


def _json_identity(obj: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


class ResearchMemoryService:
    """Deterministic, owner-scoped associative/temporal memory operations."""
    def __init__(self, db: AsyncSession, graph: KnowledgeGraphService | None = None):
        self.db = db
        self.graph = graph or KnowledgeGraphService(db)
        self._active_owner: str | None = None
        self._evidence_validity: dict[str, bool] = {}

    async def _evidence_is_active(self, owner_id: str, evidence: KGGraphEvidence) -> bool:
        if evidence.id not in self._evidence_validity:
            self._evidence_validity[evidence.id] = await self.graph._evidence_current_for_owner(owner_id, evidence)
        return self._evidence_validity[evidence.id]

    async def status(self, owner_id: str) -> dict[str, Any]:
        counts = {}
        for typ in MEMORY_TYPES:
            counts[typ.lower()] = int(await self.db.scalar(select(func.count()).select_from(MemoryRecord).where(
                MemoryRecord.owner_id == owner_id, MemoryRecord.memory_type == typ)) or 0)
        return {"ready": True, "enabled_by_default": False, "counts": counts,
                "associations": int(await self.db.scalar(select(func.count()).select_from(MemoryAssociation).where(MemoryAssociation.owner_id == owner_id)) or 0),
                "contradictions": int(await self.db.scalar(select(func.count()).select_from(MemoryContradiction).where(MemoryContradiction.owner_id == owner_id)) or 0),
                "open_gaps": int(await self.db.scalar(select(func.count()).select_from(MemoryResearchGap).where(MemoryResearchGap.owner_id == owner_id, MemoryResearchGap.status == "OPEN")) or 0)}

    async def _selected_graph(self, owner_id: str, node_ids: list[str], relationship_ids: list[str]) -> tuple[list[KGNode], list[KGRelationship]]:
        if len(node_ids) + len(relationship_ids) > MAX_FORMATION_SCOPE:
            raise MemoryValidationError(f"Selected scope is limited to {MAX_FORMATION_SCOPE} graph assertions")
        nodes = list((await self.db.scalars(select(KGNode).where(KGNode.owner_id == owner_id,
            KGNode.id.in_(set(node_ids)), KGNode.review_status == "approved", KGNode.merged_into_id.is_(None)))).all()) if node_ids else []
        rels = list((await self.db.scalars(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.id.in_(set(relationship_ids)), KGRelationship.review_status == "approved",
            KGRelationship.assertion_status == "current"))).all()) if relationship_ids else []
        if len(nodes) != len(set(node_ids)) or len(rels) != len(set(relationship_ids)):
            raise MemoryValidationError("Every selected graph assertion must be current, approved, and owned by this user")
        return nodes, rels

    async def _valid_evidence(self, owner_id: str, *, node_id: str | None = None,
                              relationship_id: str | None = None, allow_private: bool = False) -> list[KGGraphEvidence]:
        stmt = select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id,
            KGGraphEvidence.review_status == "approved")
        stmt = stmt.where(KGGraphEvidence.node_id == node_id) if node_id else stmt.where(KGGraphEvidence.relationship_id == relationship_id)
        rows = list((await self.db.scalars(stmt.order_by(KGGraphEvidence.created_at).limit(500))).all())
        valid = []
        for ev in rows:
            if ev.private_source and not allow_private:
                continue
            if await self._evidence_is_active(owner_id, ev):
                valid.append(ev)
        return valid

    async def _active_memory_sources(self, owner_id: str, memory_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = list((await self.db.scalars(select(MemorySourceEvidence).join(MemoryRecord).where(
            MemoryRecord.owner_id == owner_id, MemorySourceEvidence.memory_id == memory_id,
            MemorySourceEvidence.evidence_status == "CURRENT").order_by(MemorySourceEvidence.observed_at.desc()).limit(limit))).all())
        active = []
        for ev in rows:
            ge = await self.db.get(KGGraphEvidence, ev.graph_evidence_id) if ev.graph_evidence_id else None
            if ge is not None and await self._evidence_is_active(owner_id, ge):
                active.append({"source_evidence_id": ev.id, "document_id": ev.source_document_id,
                    "paper_id": ev.source_paper_id, "page": ev.page_number, "section_id": ev.section_id,
                    "passage": ev.exact_text, "record_id": ev.record_id})
        return active

    async def formation_preview(self, owner_id: str, node_ids: list[str], relationship_ids: list[str], allow_private: bool = False) -> dict[str, Any]:
        nodes, rels = await self._selected_graph(owner_id, node_ids, relationship_ids)
        eligible_nodes, eligible_rels, excluded = [], [], []
        for n in nodes:
            ev = await self._valid_evidence(owner_id, node_id=n.id, allow_private=allow_private)
            (eligible_nodes if ev else excluded).append({"id": n.id, "title": n.canonical_name, "graph_version": n.version,
                "evidence_count": len(ev), "evidence_ids": [e.id for e in ev]} if ev else {"id": n.id, "reason": "no_current_approved_evidence"})
        for r in rels:
            ev = await self._valid_evidence(owner_id, relationship_id=r.id, allow_private=allow_private)
            src = await self.db.get(KGNode, r.source_node_id); tgt = await self.db.get(KGNode, r.target_node_id)
            item = {"id": r.id, "title": f"{src.canonical_name} {r.relationship_type} {tgt.canonical_name}",
                    "graph_version": r.version, "evidence_count": len(ev), "evidence_ids": [e.id for e in ev]}
            (eligible_rels if ev else excluded).append(item if ev else {"id": r.id, "reason": "no_current_approved_evidence"})
        return {"selected_nodes": len(nodes), "selected_relationships": len(rels),
                "eligible_nodes": eligible_nodes, "eligible_relationships": eligible_rels, "excluded": excluded,
                "eligible_count": len(eligible_nodes) + len(eligible_rels),
                "status": "ready" if eligible_nodes or eligible_rels else "no_eligible_real_inputs"}

    async def _memory_for_graph_ref(self, node_id: str | None = None, rel_id: str | None = None) -> MemoryRecord | None:
        stmt = select(MemoryRecord).join(MemoryGraphReference).where(MemoryRecord.owner_id == self._active_owner,
            MemoryGraphReference.graph_node_id == node_id if node_id else MemoryGraphReference.graph_relationship_id == rel_id)
        return await self.db.scalar(stmt.limit(1))

    async def _add_source(self, owner_id: str, memory: MemoryRecord, ev: KGGraphEvidence) -> bool:
        prior = await self.db.scalar(select(MemorySourceEvidence.id).where(
            MemorySourceEvidence.memory_id == memory.id, MemorySourceEvidence.graph_evidence_id == ev.id))
        if prior:
            return False
        source = MemorySourceEvidence(memory_id=memory.id, graph_evidence_id=ev.id,
            source_document_id=ev.source_document_id, source_paper_id=ev.source_paper_id,
            extraction_run_id=ev.extraction_run_id, record_id=ev.record_id, page_number=ev.page_number,
            section_id=ev.section_id, exact_text=ev.exact_text, char_start=ev.char_start, char_end=ev.char_end,
            privacy_classification="PRIVATE" if ev.private_source else "RESEARCH")
        self.db.add(source); await self.db.flush()
        key = f"source:{memory.id}:{ev.id}"
        if not await self.db.scalar(select(MemoryObservationEvent.id).where(MemoryObservationEvent.owner_id == owner_id, MemoryObservationEvent.idempotency_key == key)):
            self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type="SOURCE_ADDED",
                actor_type="SYSTEM", occurred_at=utcnow(), details={"source_evidence_id": source.id, "document_id": ev.source_document_id,
                "record_id": ev.record_id, "page": ev.page_number}, idempotency_key=key))
        # Preserve the observation as episodic memory and a separately addressable source record.
        for kind, event_key, title, content in [
            ("SOURCE", f"source-memory:{ev.id}", f"Source passage · {ev.source_document_id} · p.{ev.page_number}",
             {"document_id": ev.source_document_id, "paper_id": ev.source_paper_id, "page": ev.page_number,
              "section_id": ev.section_id, "record_id": ev.record_id}),
            ("EPISODIC", f"episode:{ev.id}", f"Observed evidence · {memory.title}",
             {"observation": "reviewed graph evidence encountered", "memory_id": memory.id,
              "document_id": ev.source_document_id, "page": ev.page_number, "observed_at": utcnow().isoformat()}),
        ]:
            if await self.db.scalar(select(MemoryObservationEvent.id).where(MemoryObservationEvent.owner_id == owner_id,
                    MemoryObservationEvent.idempotency_key == event_key)):
                continue
            aux = MemoryRecord(owner_id=owner_id, memory_type=kind, title=title, content=content,
                status="CURRENT" if kind == "SOURCE" else "OBSERVATION",
                privacy_classification="PRIVATE" if ev.private_source else "RESEARCH")
            self.db.add(aux); await self.db.flush()
            self.db.add(MemorySourceEvidence(memory_id=aux.id, graph_evidence_id=ev.id,
                source_document_id=ev.source_document_id, source_paper_id=ev.source_paper_id,
                extraction_run_id=ev.extraction_run_id, record_id=ev.record_id, page_number=ev.page_number,
                section_id=ev.section_id, exact_text=ev.exact_text, char_start=ev.char_start, char_end=ev.char_end,
                privacy_classification="PRIVATE" if ev.private_source else "RESEARCH"))
            refs = list((await self.db.scalars(select(MemoryGraphReference).where(MemoryGraphReference.memory_id == memory.id))).all())
            for ref in refs:
                self.db.add(MemoryGraphReference(memory_id=aux.id, graph_node_id=ref.graph_node_id,
                    graph_relationship_id=ref.graph_relationship_id, graph_version=ref.graph_version))
            self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=aux.id,
                event_type="SOURCE_PRESERVED" if kind == "SOURCE" else "RESEARCH_OBSERVATION",
                actor_type="SYSTEM", details={"evidence_id": ev.id, "parent_memory_id": memory.id}, idempotency_key=event_key))
        return True

    async def form(self, owner_id: str, node_ids: list[str], relationship_ids: list[str], allow_private: bool = False) -> dict[str, Any]:
        self._active_owner = owner_id
        preview = await self.formation_preview(owner_id, node_ids, relationship_ids, allow_private)
        evidence_ids = sorted(eid for item in preview["eligible_nodes"] + preview["eligible_relationships"] for eid in item["evidence_ids"])
        graph_versions = sorted((item["id"], item["graph_version"]) for item in preview["eligible_nodes"] + preview["eligible_relationships"])
        scope_hash = _json_identity({"nodes": sorted(set(node_ids)), "relationships": sorted(set(relationship_ids)),
            "evidence_ids": evidence_ids, "graph_versions": graph_versions, "allow_private": allow_private})
        run = await self.db.scalar(select(MemoryProcessingRun).where(MemoryProcessingRun.owner_id == owner_id, MemoryProcessingRun.scope_hash == scope_hash))
        if run and run.status == "completed":
            return {"run_id": run.id, "idempotent": True, "created_count": run.created_count, "eligible_count": run.eligible_count, "status": run.status}
        run = run or MemoryProcessingRun(owner_id=owner_id, scope_hash=scope_hash,
            selected_node_ids=sorted(set(node_ids)), selected_relationship_ids=sorted(set(relationship_ids)), status="running")
        self.db.add(run); await self.db.flush()
        nodes, rels = await self._selected_graph(owner_id, node_ids, relationship_ids)
        made = 0
        for node in nodes:
            evs = await self._valid_evidence(owner_id, node_id=node.id, allow_private=allow_private)
            if not evs: continue
            memory = await self._memory_for_graph_ref(node_id=node.id)
            new_memory = memory is None
            if new_memory:
                memory = MemoryRecord(owner_id=owner_id, memory_type="SEMANTIC", title=node.canonical_name,
                    content={"node_type": node.node_type, "description": node.description, "canonical_name": node.canonical_name},
                    status="CURRENT", first_observed_at=node.first_observed_at,
                    last_confirmed_at=max((e.reviewed_at for e in evs), default=node.last_confirmed_at))
                self.db.add(memory); await self.db.flush()
                self.db.add(MemoryGraphReference(memory_id=memory.id, graph_node_id=node.id, graph_version=node.version)); made += 1
                key = f"created:node:{node.id}"
                self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type="FIRST_OBSERVED",
                    actor_type="SYSTEM", occurred_at=utcnow(), details={"node_id": node.id}, idempotency_key=key))
            else:
                ref = await self.db.scalar(select(MemoryGraphReference).where(MemoryGraphReference.memory_id == memory.id,
                    MemoryGraphReference.graph_node_id == node.id))
                if ref is not None and ref.graph_version != node.version:
                    old = {"title": memory.title, "content": memory.content, "status": memory.status, "graph_version": ref.graph_version}
                    new_content = {"node_type": node.node_type, "description": node.description, "canonical_name": node.canonical_name}
                    new = {"title": node.canonical_name, "content": new_content, "status": "CURRENT", "graph_version": node.version}
                    memory.title, memory.content, memory.status = new["title"], new_content, new["status"]
                    memory.version += 1; ref.graph_version = node.version
                    self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id,
                        event_type="CORRECTION_OBSERVED", actor_type="SYSTEM", occurred_at=utcnow(),
                        details={"graph_node_id": node.id, "old": old, "new": new},
                        idempotency_key=f"graph-version:node:{node.id}:{node.version}"))
            independent_before = await self.db.scalar(select(func.count(func.distinct(MemorySourceEvidence.source_paper_id))).where(MemorySourceEvidence.memory_id == memory.id)) or 0
            added = 0
            for ev in evs: added += int(await self._add_source(owner_id, memory, ev))
            independent_after = await self.db.scalar(select(func.count(func.distinct(MemorySourceEvidence.source_paper_id))).where(MemorySourceEvidence.memory_id == memory.id)) or 0
            if added and not new_memory:
                memory.last_confirmed_at = max((e.reviewed_at for e in evs), default=memory.last_confirmed_at); memory.version += 1
                kind = "INDEPENDENT_CONFIRMATION" if independent_after > independent_before else "REPEATED_OBSERVATION"
                key = f"{kind}:{memory.id}:{','.join(sorted(e.id for e in evs))}"
                exists = await self.db.scalar(select(MemoryObservationEvent.id).where(MemoryObservationEvent.owner_id == owner_id, MemoryObservationEvent.idempotency_key == key))
                if not exists: self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type=kind,
                    actor_type="SYSTEM", occurred_at=utcnow(), details={"new_source_count": added, "independent_source_count": independent_after}, idempotency_key=key))
        for rel in rels:
            evs = await self._valid_evidence(owner_id, relationship_id=rel.id, allow_private=allow_private)
            if not evs: continue
            memory = await self._memory_for_graph_ref(rel_id=rel.id)
            if memory is None:
                src, tgt = await self.db.get(KGNode, rel.source_node_id), await self.db.get(KGNode, rel.target_node_id)
                memory = MemoryRecord(owner_id=owner_id, memory_type="SEMANTIC", title=f"{src.canonical_name} {rel.relationship_type} {tgt.canonical_name}",
                    content={"subject": src.canonical_name, "subject_node_id": src.id, "predicate": rel.relationship_type,
                             "object": tgt.canonical_name, "object_node_id": tgt.id}, status=rel.assertion_status,
                    first_observed_at=rel.first_observed_at,
                    last_confirmed_at=max((e.reviewed_at for e in evs), default=rel.last_confirmed_at))
                self.db.add(memory); await self.db.flush(); self.db.add(MemoryGraphReference(memory_id=memory.id,
                    graph_relationship_id=rel.id, graph_version=rel.version)); made += 1
                self.db.add(MemoryGraphReference(memory_id=memory.id, graph_node_id=src.id, graph_version=src.version))
                self.db.add(MemoryGraphReference(memory_id=memory.id, graph_node_id=tgt.id, graph_version=tgt.version))
                self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type="FIRST_OBSERVED", actor_type="SYSTEM",
                    details={"relationship_id": rel.id}, idempotency_key=f"created:rel:{rel.id}"))
            else:
                ref = await self.db.scalar(select(MemoryGraphReference).where(MemoryGraphReference.memory_id == memory.id,
                    MemoryGraphReference.graph_relationship_id == rel.id))
                if ref is not None and ref.graph_version != rel.version:
                    src, tgt = await self.db.get(KGNode, rel.source_node_id), await self.db.get(KGNode, rel.target_node_id)
                    old = {"title": memory.title, "content": memory.content, "status": memory.status, "graph_version": ref.graph_version}
                    new_content = {"subject": src.canonical_name, "subject_node_id": src.id, "predicate": rel.relationship_type,
                        "object": tgt.canonical_name, "object_node_id": tgt.id}
                    new = {"title": f"{src.canonical_name} {rel.relationship_type} {tgt.canonical_name}",
                        "content": new_content, "status": rel.assertion_status, "graph_version": rel.version}
                    memory.title, memory.content, memory.status = new["title"], new_content, new["status"]
                    memory.version += 1; ref.graph_version = rel.version
                    self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id,
                        event_type="CORRECTION_OBSERVED", actor_type="SYSTEM", occurred_at=utcnow(),
                        details={"graph_relationship_id": rel.id, "old": old, "new": new},
                        idempotency_key=f"graph-version:relationship:{rel.id}:{rel.version}"))
            independent_before = await self.db.scalar(select(func.count(func.distinct(MemorySourceEvidence.source_paper_id))).where(MemorySourceEvidence.memory_id == memory.id)) or 0
            added = 0
            for ev in evs: added += int(await self._add_source(owner_id, memory, ev))
            if added:
                independent_after = await self.db.scalar(select(func.count(func.distinct(MemorySourceEvidence.source_paper_id))).where(MemorySourceEvidence.memory_id == memory.id)) or 0
                memory.last_confirmed_at = max((e.reviewed_at for e in evs), default=memory.last_confirmed_at)
                memory.version += 1
                event_type = "INDEPENDENT_CONFIRMATION" if independent_after > independent_before else "REPEATED_OBSERVATION"
                key = f"{event_type}:{memory.id}:{','.join(sorted(e.id for e in evs))}"
                if not await self.db.scalar(select(MemoryObservationEvent.id).where(MemoryObservationEvent.owner_id == owner_id,
                        MemoryObservationEvent.idempotency_key == key)):
                    self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type=event_type,
                        actor_type="SYSTEM", details={"new_source_count": added, "independent_source_count": independent_after},
                        idempotency_key=key))
        await self._detect_contradictions(owner_id, rels)
        await self.db.flush()
        selected_mem_stmt = select(MemoryRecord).join(MemoryGraphReference).where(
            MemoryGraphReference.graph_node_id.in_(set(node_ids)) if node_ids else MemoryGraphReference.graph_relationship_id.in_(set(relationship_ids)))
        selected_memories = list((await self.db.scalars(selected_mem_stmt.limit(MAX_FORMATION_SCOPE))).all())
        await self._discover_associations(owner_id, [m.id for m in selected_memories])
        run.status, run.eligible_count, run.created_count, run.completed_at = "completed", preview["eligible_count"], made, utcnow()
        self.db.add(run)
        return {"run_id": run.id, "idempotent": False, "created_count": made, "eligible_count": preview["eligible_count"], "status": run.status,
                "preview": preview, "association_candidates": "created where reviewed evidence or graph references overlap"}

    async def _detect_contradictions(self, owner_id: str, selected: list[KGRelationship]) -> int:
        # Only explicit, reviewed opposing predicates over identical endpoints qualify.
        opposite = {"SUPPORTS": "CONTRADICTS", "CONTRADICTS": "SUPPORTS"}
        created = 0
        for rel in selected:
            other_type = opposite.get(rel.relationship_type)
            if not other_type: continue
            matches = list((await self.db.scalars(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
                KGRelationship.source_node_id == rel.source_node_id, KGRelationship.target_node_id == rel.target_node_id,
                KGRelationship.relationship_type == other_type, KGRelationship.review_status == "approved",
                KGRelationship.assertion_status == "current").limit(20))).all())
            for other in matches:
                a, b = sorted([rel.id, other.id])
                exists = await self.db.scalar(select(MemoryContradiction.id).where(MemoryContradiction.owner_id == owner_id,
                    MemoryContradiction.assertion_a_id == a, MemoryContradiction.assertion_b_id == b))
                if exists: continue
                if not await self._valid_evidence(owner_id, relationship_id=other.id): continue
                candidate = MemoryContradiction(owner_id=owner_id, assertion_a_id=a, assertion_b_id=b,
                    status="CANDIDATE", comparison_basis={"same_subject": True, "same_object": True,
                    "opposing_reviewed_predicates": True}, experimental_context={"requires_human_context_review": True}, uncertainty=0.8)
                self.db.add(candidate); await self.db.flush()
                src, tgt = await self.db.get(KGNode, rel.source_node_id), await self.db.get(KGNode, rel.target_node_id)
                memory = MemoryRecord(owner_id=owner_id, memory_type="CONTRADICTION",
                    title=f"Conflicting reviewed assertions about {src.canonical_name} and {tgt.canonical_name}",
                    content={"candidate_id": candidate.id, "assertion_ids": [a, b], "status": "CANDIDATE"}, status="CANDIDATE")
                self.db.add(memory); await self.db.flush()
                for assertion_id in [a, b]:
                    assertion = await self.db.get(KGRelationship, assertion_id)
                    self.db.add(MemoryGraphReference(memory_id=memory.id, graph_relationship_id=assertion_id))
                    for ev in await self._valid_evidence(owner_id, relationship_id=assertion_id):
                        await self._add_source(owner_id, memory, ev)
                created += 1
        return created

    async def _discover_associations(self, owner_id: str, memory_ids: list[str]) -> int:
        if not memory_ids: return 0
        refs = list((await self.db.execute(select(MemoryGraphReference.memory_id, MemoryGraphReference.graph_node_id).join(
            MemoryRecord, MemoryRecord.id == MemoryGraphReference.memory_id).where(MemoryRecord.owner_id == owner_id,
            MemoryRecord.memory_type == "SEMANTIC", MemoryGraphReference.memory_id.in_(set(memory_ids)),
            MemoryGraphReference.graph_node_id.is_not(None)).limit(1000))).all())
        buckets: dict[str, set[str]] = {}
        for mid, nid in refs: buckets.setdefault(nid, set()).add(mid)
        pairs: dict[tuple[str, str], set[str]] = {}
        for nid, mids in buckets.items():
            ordered = sorted(mids)
            for i, left in enumerate(ordered):
                for right in ordered[i+1:i+21]: pairs.setdefault((left, right), set()).add(nid)
        count = 0
        for (left, right), shared in list(pairs.items())[:500]:
            exists = await self.db.scalar(select(MemoryAssociation.id).where(MemoryAssociation.owner_id == owner_id,
                MemoryAssociation.source_memory_id == left, MemoryAssociation.target_memory_id == right, MemoryAssociation.category == "SHARED_GRAPH_ENTITY"))
            if exists: continue
            shared_labels = list((await self.db.scalars(select(KGNode.canonical_name).where(KGNode.id.in_(shared)).limit(20))).all())
            # One memory with multiple graph nodes can tie another through a shared reviewed entity.
            if not shared_labels: continue
            self.db.add(MemoryAssociation(owner_id=owner_id, source_memory_id=left, target_memory_id=right,
                category="SHARED_GRAPH_ENTITY", explanation="Both memories reference the same reviewed graph entity: " + ", ".join(shared_labels),
                score=min(ASSOCIATION_SCORING["maximum"], ASSOCIATION_SCORING["shared_reviewed_entity"] * len(shared)),
                score_components={"shared_reviewed_entities": len(shared), "weights": ASSOCIATION_SCORING}, status="CANDIDATE")); count += 1
        return count

    async def search(self, owner_id: str, query: str, *, scope_id: str | None = None, document_ids: list[str] | None = None,
                     memory_types: list[str] | None = None, limit: int = 20) -> dict[str, Any]:
        limit = min(max(1, limit), MAX_LIMIT)
        stmt = select(MemoryRecord).where(MemoryRecord.owner_id == owner_id, MemoryRecord.status.not_in(["DELETED", "REJECTED"]))
        if scope_id: stmt = stmt.where(MemoryRecord.scope_id == scope_id)
        if memory_types:
            invalid = set(memory_types) - MEMORY_TYPES
            if invalid: raise MemoryValidationError("Unknown memory type filter")
            stmt = stmt.where(MemoryRecord.memory_type.in_(memory_types))
        # Limit before local lexical scoring to prevent whole-store loads.
        records = list((await self.db.scalars(stmt.order_by(MemoryRecord.updated_at.desc()).limit(1000))).all())
        query_terms = _terms(query)
        ranked = []
        for rec in records:
            text = rec.title + " " + json.dumps(rec.content, ensure_ascii=False)
            overlap = query_terms & _terms(text)
            if not overlap: continue
            score = len(overlap) / max(1, len(query_terms))
            ranked.append((rec, overlap, score))
        ranked.sort(key=lambda x: (-x[2], x[0].title.casefold(), x[0].id))
        direct, related = [], []
        # Only provenance-check a bounded head of lexical candidates.
        for rec, overlap, score in ranked[:max(50, min(1000, limit * 5))]:
            evidence_rows = list((await self.db.scalars(select(MemorySourceEvidence).where(MemorySourceEvidence.memory_id == rec.id,
                MemorySourceEvidence.evidence_status == "CURRENT").order_by(MemorySourceEvidence.observed_at.desc()).limit(20))).all())
            active = []
            for ev in evidence_rows:
                ge = await self.db.get(KGGraphEvidence, ev.graph_evidence_id) if ev.graph_evidence_id else None
                if ge is not None and await self._evidence_is_active(owner_id, ge):
                    if document_ids and ev.source_document_id not in document_ids: continue
                    active.append({"document_id": ev.source_document_id, "paper_id": ev.source_paper_id, "run_id": ev.extraction_run_id,
                        "page": ev.page_number, "section_id": ev.section_id, "passage": ev.exact_text, "record_id": ev.record_id})
            if not active: continue
            item = {"memory_id": rec.id, "type": rec.memory_type, "title": rec.title, "content": rec.content,
                "status": rec.status, "first_observed_at": rec.first_observed_at.isoformat(),
                "last_confirmed_at": rec.last_confirmed_at.isoformat() if rec.last_confirmed_at else None,
                "rank_score": round(score, 4), "rank_explanation": {"matched_terms": sorted(overlap), "query_term_coverage": round(score, 4)},
                "evidence": active}
            direct.append(item)
        direct.sort(key=lambda x: (-x["rank_score"], x["title"].casefold(), x["memory_id"]))
        top_ids = [x["memory_id"] for x in direct[:limit]]
        related_rows = list((await self.db.scalars(select(MemoryAssociation).where(MemoryAssociation.owner_id == owner_id,
            or_(MemoryAssociation.source_memory_id.in_(top_ids), MemoryAssociation.target_memory_id.in_(top_ids)),
            MemoryAssociation.status.in_(["CONFIRMED_ASSOCIATION", "CANDIDATE", "REVIEW_REQUIRED"])).limit(limit*3))).all()) if top_ids else []
        related = []
        for a in related_rows:
            source_refs = await self._active_memory_sources(owner_id, a.source_memory_id, 10)
            target_refs = await self._active_memory_sources(owner_id, a.target_memory_id, 10)
            if not source_refs or not target_refs: continue
            related.append({"association_id": a.id, "source_memory_id": a.source_memory_id, "target_memory_id": a.target_memory_id,
                "category": a.category, "status": a.status, "explanation": a.explanation, "score": a.score,
                "score_components": a.score_components, "supporting_sources": source_refs + target_refs,
                "established_fact": a.status == "CONFIRMED_ASSOCIATION"})
        matched_rel_ids = set()
        if top_ids:
            matched_rel_ids.update((await self.db.scalars(select(MemoryGraphReference.graph_relationship_id).where(
                MemoryGraphReference.memory_id.in_(top_ids), MemoryGraphReference.graph_relationship_id.is_not(None)).limit(200))).all())
        contradiction_stmt = select(MemoryContradiction).where(MemoryContradiction.owner_id == owner_id,
            MemoryContradiction.status.in_(["CANDIDATE", "REVIEW_REQUIRED", "UNRESOLVED"]))
        if matched_rel_ids:
            contradiction_stmt = contradiction_stmt.where(or_(MemoryContradiction.assertion_a_id.in_(matched_rel_ids),
                MemoryContradiction.assertion_b_id.in_(matched_rel_ids)))
        else:
            contradiction_stmt = contradiction_stmt.where(False)
        contradiction_rows = list((await self.db.scalars(contradiction_stmt.limit(limit))).all())
        gap_stmt = select(MemoryResearchGap).where(MemoryResearchGap.owner_id == owner_id, MemoryResearchGap.status == "OPEN")
        if query_terms:
            gap_stmt = gap_stmt.where(or_(*[MemoryResearchGap.question.ilike(f"%{term}%") for term in sorted(query_terms)[:8]]))
        gap_rows = list((await self.db.scalars(gap_stmt.limit(limit))).all())
        return {"query": query, "direct_evidence": direct[:limit], "related_connections": related,
            "suggested_associations": [a for a in related if a["status"] != "CONFIRMED_ASSOCIATION"],
            "contradictions": [await self._contradiction_detail(owner_id, c) for c in contradiction_rows],
            "research_gaps": [{"id": g.id, "type": g.gap_type, "question": g.question, "reason": g.reason,
                "scope": g.scope, "status": g.status} for g in gap_rows]}

    async def _contradiction_detail(self, owner_id: str, row: MemoryContradiction) -> dict[str, Any]:
        assertions = []
        for assertion_id in [row.assertion_a_id, row.assertion_b_id]:
            rel = await self.db.scalar(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
                KGRelationship.id == assertion_id))
            if rel is None: continue
            src, tgt = await self.db.get(KGNode, rel.source_node_id), await self.db.get(KGNode, rel.target_node_id)
            evs = await self._valid_evidence(owner_id, relationship_id=rel.id)
            assertions.append({"assertion_id": rel.id, "subject": src.canonical_name if src else None,
                "predicate": rel.relationship_type, "object": tgt.canonical_name if tgt else None,
                "assertion_status": rel.assertion_status,
                "evidence": [{"document_id": e.source_document_id, "paper_id": e.source_paper_id,
                    "page": e.page_number, "section_id": e.section_id, "passage": e.exact_text} for e in evs]})
        return {"id": row.id, "status": row.status, "assertion_a_id": row.assertion_a_id,
            "assertion_b_id": row.assertion_b_id, "assertions": assertions,
            "basis": row.comparison_basis, "context": row.experimental_context,
            "uncertainty": row.uncertainty, "resolution": row.resolution}

    async def create_gap(self, owner_id: str, question: str, gap_type: str, scope: dict, reason: str,
                         inspected_sources: list, actor_id: str) -> MemoryResearchGap:
        allowed = {"LIBRARY_EVIDENCE_GAP", "DOCUMENT_INFORMATION_GAP", "CONFLICT_UNRESOLVED", "POTENTIAL_RESEARCH_GAP"}
        if gap_type not in allowed: raise MemoryValidationError("Invalid gap type")
        mem = MemoryRecord(owner_id=owner_id, memory_type="RESEARCH_GAP", title=question[:500],
            content={"question": question, "scope": scope, "reason": reason}, status="OPEN", privacy_classification="RESEARCHER_CREATED")
        self.db.add(mem); await self.db.flush()
        gap = MemoryResearchGap(owner_id=owner_id, memory_id=mem.id, gap_type=gap_type, question=question,
            scope=scope, reason=reason, inspected_sources=inspected_sources)
        self.db.add(gap); await self.db.flush()
        self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=mem.id, event_type="GAP_CREATED", actor_type="USER",
            actor_id=actor_id, details={"gap_id": gap.id, "gap_type": gap_type}, idempotency_key=f"gap:{gap.id}"))
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="GAP", target_id=gap.id, action="CREATED", actor_id=actor_id,
            details={"gap_type": gap_type, "scope": scope}))
        return gap

    async def review_association(self, owner_id: str, association_id: str, action: str, actor_id: str) -> MemoryAssociation:
        actions = {"confirm": "CONFIRMED_ASSOCIATION", "reject": "REJECTED", "review": "REVIEW_REQUIRED"}
        if action not in actions: raise MemoryValidationError("Action must be confirm, reject, or review")
        row = await self.db.scalar(select(MemoryAssociation).where(MemoryAssociation.owner_id == owner_id, MemoryAssociation.id == association_id))
        if row is None: raise MemoryValidationError("Unknown association")
        if action == "confirm":
            if not await self._active_memory_sources(owner_id, row.source_memory_id) or not await self._active_memory_sources(owner_id, row.target_memory_id):
                raise MemoryValidationError("An association needs current reviewed evidence on both memories before confirmation")
        old = row.status; row.status = actions[action]; row.confirmed_at = utcnow() if action == "confirm" else row.confirmed_at
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="ASSOCIATION", target_id=row.id,
            action=actions[action], actor_id=actor_id, details={"old_status": old, "explanation": row.explanation}))
        return row

    async def list_associations(self, owner_id: str, status: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = list((await self.db.scalars(select(MemoryAssociation).where(MemoryAssociation.owner_id == owner_id,
            MemoryAssociation.status == status.upper()).order_by(MemoryAssociation.created_at.desc()).offset(max(0, offset))
            .limit(min(max(1, limit), MAX_LIMIT)))).all())
        results = []
        for row in rows:
            source_refs = await self._active_memory_sources(owner_id, row.source_memory_id, 10)
            target_refs = await self._active_memory_sources(owner_id, row.target_memory_id, 10)
            results.append({"association": row, "supporting_sources": source_refs + target_refs,
                "evidence_current": bool(source_refs and target_refs)})
        return results

    async def list_contradictions(self, owner_id: str, status: str | None = None,
                                  limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        stmt = select(MemoryContradiction).where(MemoryContradiction.owner_id == owner_id)
        if status: stmt = stmt.where(MemoryContradiction.status == status.upper())
        rows = list((await self.db.scalars(stmt.order_by(MemoryContradiction.created_at.desc()).offset(max(0, offset))
            .limit(min(max(1, limit), MAX_LIMIT)))).all())
        return [await self._contradiction_detail(owner_id, row) for row in rows]

    async def neighborhood(self, owner_id: str, memory_id: str, depth: int = 2) -> dict[str, Any]:
        memory = await self.db.scalar(select(MemoryRecord).where(MemoryRecord.owner_id == owner_id, MemoryRecord.id == memory_id))
        if memory is None: raise MemoryValidationError("Unknown memory")
        refs = list((await self.db.scalars(select(MemoryGraphReference).where(MemoryGraphReference.memory_id == memory_id).limit(20))).all())
        node_ids = list(dict.fromkeys(r.graph_node_id for r in refs if r.graph_node_id))
        graph_result = {"nodes": [], "relationships": [], "evidence": []}
        if node_ids:
            graph_result = await self.graph.neighborhood(owner_id, node_ids[0], depth=min(max(depth, 1), 3), limit=50)
        associations = list((await self.db.scalars(select(MemoryAssociation).where(MemoryAssociation.owner_id == owner_id,
            or_(MemoryAssociation.source_memory_id == memory_id, MemoryAssociation.target_memory_id == memory_id),
            MemoryAssociation.status.in_(["CONFIRMED_ASSOCIATION", "CANDIDATE", "REVIEW_REQUIRED"])).limit(50))).all())
        return {"memory_id": memory_id, "graph_neighborhood": graph_result,
            "associations": [{"id": a.id, "source_memory_id": a.source_memory_id, "target_memory_id": a.target_memory_id,
                "category": a.category, "status": a.status, "explanation": a.explanation,
                "score": a.score, "score_components": a.score_components} for a in associations]}

    async def feedback(self, owner_id: str, target_type: str, target_id: str, action: str,
                       details: dict, actor_id: str) -> MemoryReviewEvent:
        allowed = {"RELEVANT", "NOT_RELEVANT", "USEFUL_CONNECTION", "INCORRECT_ASSOCIATION", "OUTDATED_EVIDENCE", "INCORRECT_SOURCE", "CONTRADICTION_RESOLVED", "GAP_RESOLVED"}
        if action not in allowed: raise MemoryValidationError("Unsupported feedback action")
        table = {"MEMORY": MemoryRecord, "ASSOCIATION": MemoryAssociation,
                 "GAP": MemoryResearchGap, "CONTRADICTION": MemoryContradiction}.get(target_type.upper())
        if table is None or not await self.db.scalar(select(table.id).where(table.owner_id == owner_id, table.id == target_id)):
            raise MemoryValidationError("Unknown feedback target")
        event = MemoryReviewEvent(owner_id=owner_id, target_type=target_type, target_id=target_id,
            action=action, actor_id=actor_id, details=details)
        self.db.add(event)
        return event

    async def set_session_opt_in(self, owner_id: str, conversation_id: str, enabled: bool) -> MemorySessionOptIn:
        conversation = await self.db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == owner_id))
        if conversation is None: raise MemoryValidationError("Conversation not found")
        row = await self.db.scalar(select(MemorySessionOptIn).where(MemorySessionOptIn.owner_id == owner_id,
            MemorySessionOptIn.conversation_id == conversation_id))
        if row is None:
            row = MemorySessionOptIn(owner_id=owner_id, conversation_id=conversation_id, enabled=enabled,
                enabled_at=utcnow() if enabled else None)
            self.db.add(row)
        else:
            row.enabled = enabled
            row.enabled_at = utcnow() if enabled else None
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="SESSION", target_id=conversation_id,
            action="CAPTURE_ENABLED" if enabled else "CAPTURE_DISABLED", actor_id=owner_id, details={"enabled": enabled}))
        return row

    async def capture_session_observation(self, owner_id: str, conversation_id: str, query: str,
                                         evidence_ids: list[str]) -> MemoryRecord:
        opt_in = await self.db.scalar(select(MemorySessionOptIn).where(MemorySessionOptIn.owner_id == owner_id,
            MemorySessionOptIn.conversation_id == conversation_id, MemorySessionOptIn.enabled.is_(True)))
        if opt_in is None: raise MemoryValidationError("Explicit session memory opt-in is required")
        if not query.strip() or len(query) > 2000: raise MemoryValidationError("Query must contain 1 to 2000 characters")
        valid = []
        for ev in list((await self.db.scalars(select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id,
                KGGraphEvidence.id.in_(set(evidence_ids)), KGGraphEvidence.review_status == "approved").limit(50))).all()):
            if not ev.private_source and await self._evidence_is_active(owner_id, ev): valid.append(ev)
        memory = MemoryRecord(owner_id=owner_id, memory_type="EPISODIC", title=query[:500],
            content={"query": query, "conversation_id": conversation_id}, status="OBSERVATION", privacy_classification="SESSION")
        self.db.add(memory); await self.db.flush()
        for ev in valid: await self._add_source(owner_id, memory, ev)
        self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=memory.id, event_type="SESSION_RESEARCH_OBSERVATION",
            actor_type="USER", actor_id=owner_id, details={"conversation_id": conversation_id,
            "source_evidence_ids": [e.id for e in valid]}, idempotency_key=f"session:{conversation_id}:{_json_identity({'q': query, 'e': sorted(e.id for e in valid)})}"))
        return memory

    async def delete_session_memory(self, owner_id: str, memory_id: str, actor_id: str) -> dict[str, Any]:
        memory = await self.db.scalar(select(MemoryRecord).where(MemoryRecord.owner_id == owner_id,
            MemoryRecord.id == memory_id, MemoryRecord.privacy_classification == "SESSION"))
        if memory is None: raise MemoryValidationError("User-created session memory not found")
        snapshot = {"memory_type": memory.memory_type, "deleted_at": utcnow().isoformat(),
                    "deleted_content_hash": _json_identity({"title": memory.title, "content": memory.content})}
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="SESSION_MEMORY", target_id=memory.id,
            action="DELETED", actor_id=actor_id, details=snapshot))
        await self.db.flush()
        await self.db.delete(memory)
        return {"deleted": True, "memory_id": memory_id, "audit_retained": True}

    async def history(self, owner_id: str, memory_id: str, limit: int = 100) -> list[MemoryObservationEvent]:
        if not await self.db.scalar(select(MemoryRecord.id).where(MemoryRecord.owner_id == owner_id, MemoryRecord.id == memory_id)):
            raise MemoryValidationError("Unknown memory")
        return list((await self.db.scalars(select(MemoryObservationEvent).where(MemoryObservationEvent.owner_id == owner_id,
            MemoryObservationEvent.memory_id == memory_id).order_by(MemoryObservationEvent.occurred_at).limit(min(max(limit,1),MAX_LIMIT)))).all())

    async def resolve_gap(self, owner_id: str, gap_id: str, status: str, resolution_memory_id: str | None, actor_id: str) -> MemoryResearchGap:
        if status not in {"RESOLVED", "REOPENED"}: raise MemoryValidationError("Gap status must be RESOLVED or REOPENED")
        gap = await self.db.scalar(select(MemoryResearchGap).where(MemoryResearchGap.owner_id == owner_id, MemoryResearchGap.id == gap_id))
        if gap is None: raise MemoryValidationError("Unknown research gap")
        if resolution_memory_id and not await self.db.scalar(select(MemoryRecord.id).where(MemoryRecord.owner_id == owner_id, MemoryRecord.id == resolution_memory_id)):
            raise MemoryValidationError("Resolution memory is not owned by this user")
        old = gap.status; gap.status = status; gap.resolution_memory_id = resolution_memory_id if status == "RESOLVED" else None
        if gap.memory_id:
            gap_memory = await self.db.get(MemoryRecord, gap.memory_id)
            if gap_memory: gap_memory.status = status
        self.db.add(MemoryObservationEvent(owner_id=owner_id, memory_id=gap.memory_id, event_type="GAP_" + status,
            actor_type="USER", actor_id=actor_id, details={"gap_id": gap.id, "old_status": old,
            "resolution_memory_id": resolution_memory_id}))
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="GAP", target_id=gap.id, action=status,
            actor_id=actor_id, details={"old_status": old, "resolution_memory_id": resolution_memory_id}))
        return gap

    async def resolve_contradiction(self, owner_id: str, contradiction_id: str, outcome: str, context: dict, actor_id: str) -> MemoryContradiction:
        if outcome not in {"TRUE_CONFLICT", "CONTEXTUAL_DIFFERENCE", "NOT_A_CONTRADICTION", "UNRESOLVED"}:
            raise MemoryValidationError("Invalid contradiction outcome")
        row = await self.db.scalar(select(MemoryContradiction).where(MemoryContradiction.owner_id == owner_id,
            MemoryContradiction.id == contradiction_id))
        if row is None: raise MemoryValidationError("Unknown contradiction candidate")
        old = row.status; row.status = outcome; row.experimental_context = {**(row.experimental_context or {}), **context}
        row.resolution, row.resolved_at = outcome, utcnow()
        for assertion_id in [row.assertion_a_id, row.assertion_b_id]:
            assertion = await self.db.scalar(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
                KGRelationship.id == assertion_id))
            if assertion and outcome == "TRUE_CONFLICT":
                old_assertion_status = assertion.assertion_status
                assertion.assertion_status = "disputed"
                from backend.app.models.knowledge_graph import KGReviewEvent
                self.db.add(KGReviewEvent(owner_id=owner_id, target_type="relationship", target_id=assertion.id,
                    action="status", reviewer=actor_id, old_value={"assertion_status": old_assertion_status},
                    new_value={"assertion_status": "disputed", "reason": "reviewed memory contradiction", "candidate_id": row.id}))
        memory = await self.db.scalar(select(MemoryRecord).where(MemoryRecord.owner_id == owner_id,
            MemoryRecord.memory_type == "CONTRADICTION", MemoryRecord.content["candidate_id"].as_string() == row.id))
        if memory: memory.status = outcome
        self.db.add(MemoryReviewEvent(owner_id=owner_id, target_type="CONTRADICTION", target_id=row.id,
            action=outcome, actor_id=actor_id, details={"old_status": old, "context": context,
            "assertions": [row.assertion_a_id, row.assertion_b_id]}))
        return row

    async def audit(self, owner_id: str) -> dict[str, Any]:
        issues, issue_count = [], 0
        evs = await self.db.stream_scalars(select(MemorySourceEvidence).join(MemoryRecord).where(MemoryRecord.owner_id == owner_id).execution_options(yield_per=100))
        checked = 0
        async for ev in evs:
            checked += 1
            ge = await self.db.get(KGGraphEvidence, ev.graph_evidence_id) if ev.graph_evidence_id else None
            if ge is None or not await self._evidence_is_active(owner_id, ge):
                issue_count += 1
                if len(issues) < 500:
                    issues.append({"kind": "stale_or_missing_source", "evidence_id": ev.id})
        return {"source_evidence_checked": checked, "issue_count": issue_count, "issues": issues,
                "issues_truncated": issue_count > len(issues), "read_only": True}

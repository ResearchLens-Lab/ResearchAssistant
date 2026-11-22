from __future__ import annotations

import re
from collections import deque
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from sqlalchemy import cast, exists, func, or_, select, String
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document
from backend.app.models.knowledge_graph import (
    KGGraphCandidate, KGGraphEvidence, KGIdentityDecision,
    KGImportRun, KGNode, KGNodeAlias, KGRelationship, KGReviewEvent,
)
from backend.app.models.paper import Paper
from rag.document_intelligence.models import DocumentIntelligence, KnowledgeRecord
from rag.document_intelligence.store import ExtractionStore


NODE_TYPES = {
    "PAPER", "DOCUMENT", "PERSON", "ORGANIZATION", "INSTITUTION", "RESEARCH_GROUP",
    "CONCEPT", "DEFINITION", "METHOD", "ALGORITHM", "MODEL", "DATASET", "METRIC",
    "TASK", "PROBLEM", "TOOL", "SOFTWARE", "VENUE", "CLAIM", "FINDING", "EQUATION", "REFERENCE_MENTION",
}

RELATIONSHIP_TYPES: dict[str, tuple[set[str], set[str]]] = {
    "AUTHORED_BY": ({"PAPER"}, {"PERSON"}),
    "AFFILIATED_WITH": ({"PERSON", "RESEARCH_GROUP"}, {"INSTITUTION", "ORGANIZATION"}),
    "MEMBER_OF": ({"PERSON"}, {"RESEARCH_GROUP", "INSTITUTION", "ORGANIZATION"}),
    "PROPOSES": ({"PAPER"}, {"METHOD", "ALGORITHM", "MODEL"}),
    "INTRODUCES": ({"PAPER"}, {"CONCEPT", "METHOD", "ALGORITHM", "MODEL", "DATASET"}),
    "USES_METHOD": ({"PAPER"}, {"METHOD", "ALGORITHM", "MODEL", "TOOL", "SOFTWARE"}),
    "USES_DATASET": ({"PAPER"}, {"DATASET"}),
    "EVALUATED_ON": ({"PAPER", "METHOD", "MODEL"}, {"DATASET", "TASK"}),
    "REPORTS_METRIC": ({"PAPER", "FINDING", "CLAIM"}, {"METRIC"}),
    "ADDRESSES_PROBLEM": ({"PAPER", "METHOD", "ALGORITHM", "MODEL"}, {"PROBLEM"}),
    "DEFINES": ({"PAPER", "PERSON"}, {"DEFINITION", "CONCEPT"}),
    "RELATED_TO": (NODE_TYPES, NODE_TYPES),
    "COMPARED_WITH": ({"METHOD", "ALGORITHM", "MODEL", "DATASET", "METRIC"}, {"METHOD", "ALGORITHM", "MODEL", "DATASET", "METRIC"}),
    "DERIVED_FROM": ({"CONCEPT", "METHOD", "ALGORITHM", "MODEL", "DATASET"}, {"CONCEPT", "METHOD", "ALGORITHM", "MODEL", "DATASET"}),
    "CITES": ({"PAPER"}, {"REFERENCE_MENTION"}),
    "SUPPORTS": ({"PAPER", "FINDING"}, {"CLAIM", "FINDING", "PROBLEM"}),
    "CONTRADICTS": ({"PAPER", "FINDING", "CLAIM"}, {"CLAIM", "FINDING"}),
    "EXTENDS": ({"PAPER", "METHOD", "ALGORITHM", "MODEL"}, {"METHOD", "ALGORITHM", "MODEL"}),
    "IMPLEMENTS": ({"TOOL", "SOFTWARE"}, {"METHOD", "ALGORITHM", "MODEL"}),
}
CONFLICTING_RELATIONSHIPS = {frozenset({"SUPPORTS", "CONTRADICTS"})}
MAX_DEPTH = 4
MAX_RESULTS = 200


class GraphValidationError(ValueError):
    pass


def normalize_identity(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))


def validate_relationship(source_type: str, relation_type: str, target_type: str,
                          custom: dict[str, tuple[set[str], set[str]]] | None = None) -> None:
    relation_type = relation_type.upper()
    endpoints = (custom or {}).get(relation_type) or RELATIONSHIP_TYPES.get(relation_type)
    if endpoints is None:
        raise GraphValidationError(f"Unknown relationship type: {relation_type}")
    if source_type not in endpoints[0] or target_type not in endpoints[1]:
        raise GraphValidationError(f"{relation_type} does not allow {source_type} -> {target_type}")


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession, evidence_store: ExtractionStore | None = None,
                 custom_relationships: dict[str, tuple[set[str], set[str]]] | None = None,
                 custom_node_types: set[str] | None = None):
        self.db = session
        self.evidence_store = evidence_store or ExtractionStore()
        self.custom_relationships = custom_relationships or {}
        self.custom_node_types = custom_node_types or set()
        self._source_snapshot_cache: dict[tuple[str, str, str], tuple[tuple[int, int], DocumentIntelligence]] = {}

    async def _owned_document(self, owner_id: str, document_id: str) -> tuple[Document, Paper]:
        row = await self.db.execute(select(Document, Paper).join(Paper, Document.paper_id == Paper.id)
                                    .where(Document.id == document_id, Paper.owner_id == owner_id))
        item = row.first()
        if item is None:
            raise GraphValidationError("Source document does not exist in this owner's library")
        return item[0], item[1]

    def load_source(self, document_id: str, run_id: str) -> DocumentIntelligence:
        try:
            snapshot = self.evidence_store.get(document_id, run_id)
        except (OSError, ValueError, KeyError) as exc:
            raise GraphValidationError(f"Phase 4 extraction run could not be read: {type(exc).__name__}") from exc
        if snapshot.document_id != document_id or snapshot.run_id != run_id:
            raise GraphValidationError("Phase 4 source identity mismatch")
        return snapshot

    async def import_plan(self, owner_id: str, document_id: str, run_id: str,
                          allow_private: bool = False) -> dict[str, Any]:
        _, paper = await self._owned_document(owner_id, document_id)
        snapshot = self.load_source(document_id, run_id)
        try: latest = self.evidence_store.get(document_id)
        except Exception as exc: raise GraphValidationError("Current Phase 4 extraction could not be resolved") from exc
        if latest.run_id != run_id:
            raise GraphValidationError("Only the current successful Phase 4 run can be imported; older runs may be superseded")
        if snapshot.private_source and not allow_private:
            raise GraphValidationError("Private source import requires explicit --allow-private")
        valid: list[KnowledgeRecord] = []
        excluded: list[dict[str, str]] = []
        page_map = {p["page_number"]: p["text"] for p in snapshot.pages}
        for record in snapshot.knowledge_records:
            if record.review_status != "approved":
                excluded.append({"record_id": record.record_id, "reason": record.review_status})
                continue
            page = page_map.get(record.page_number)
            if (record.document_id != document_id or not record.block_id or page is None or
                    record.char_start < 0 or record.char_end <= record.char_start or
                    record.char_end > len(page) or page[record.char_start:record.char_end] != record.exact_text):
                excluded.append({"record_id": record.record_id, "reason": "invalid_source_provenance"})
                continue
            valid.append(record)
        existing = await self.db.scalar(select(KGImportRun).where(
            KGImportRun.owner_id == owner_id, KGImportRun.document_id == document_id,
            KGImportRun.extraction_run_id == run_id))
        return {"owner_id": owner_id, "document_id": document_id, "paper_id": paper.id,
                "extraction_run_id": run_id, "extraction_version": snapshot.extraction_version,
                "content_hash": snapshot.content_hash, "private_source": snapshot.private_source,
                "approved_valid_records": [r.model_dump(mode="json") for r in valid],
                "excluded_records": excluded, "already_imported": existing is not None,
                "candidate_count": len(valid), "status": "dry_run"}

    async def import_approved(self, owner_id: str, document_id: str, run_id: str,
                              allow_private: bool = False) -> dict[str, Any]:
        plan = await self.import_plan(owner_id, document_id, run_id, allow_private)
        if plan["already_imported"]:
            prior = await self.db.scalar(select(KGImportRun).where(
                KGImportRun.owner_id == owner_id, KGImportRun.document_id == document_id,
                KGImportRun.extraction_run_id == run_id))
            return {"import_run_id": prior.id, "candidate_count": prior.candidate_count, "idempotent": True}
        import_run = KGImportRun(owner_id=owner_id, document_id=document_id, paper_id=plan["paper_id"],
                                 extraction_run_id=run_id, extraction_version=plan["extraction_version"],
                                 content_hash=plan["content_hash"], candidate_count=plan["candidate_count"],
                                 status="completed", synthetic=False)
        self.db.add(import_run)
        await self.db.flush()
        for raw in plan["approved_valid_records"]:
            record = KnowledgeRecord.model_validate(raw)
            candidate = KGGraphCandidate(
                import_run_id=import_run.id, owner_id=owner_id, document_id=document_id, paper_id=plan["paper_id"],
                extraction_run_id=run_id, extraction_version=plan["extraction_version"], record_id=record.record_id,
                block_id=record.block_id, category=record.category, exact_text=record.exact_text,
                page_number=record.page_number, section_id=record.section_id,
                char_start=record.char_start, char_end=record.char_end, extraction_method=record.extraction_method,
                confidence=record.confidence, private_source=plan["private_source"], source_snapshot=raw, status="pending")
            self.db.add(candidate)
        await self.db.flush()
        return {"import_run_id": import_run.id, "candidate_count": import_run.candidate_count,
                "excluded_records": plan["excluded_records"], "idempotent": False}

    async def list_candidates(self, owner_id: str, status: str = "pending", limit: int = 100,
                              offset: int = 0, allow_private: bool = False) -> list[KGGraphCandidate]:
        limit = min(max(limit, 1), MAX_RESULTS)
        stmt = select(KGGraphCandidate).where(KGGraphCandidate.owner_id == owner_id, KGGraphCandidate.status == status)
        if not allow_private: stmt = stmt.where(KGGraphCandidate.private_source.is_(False))
        result = await self.db.execute(stmt
            .order_by(KGGraphCandidate.created_at, KGGraphCandidate.id).offset(max(0, offset)).limit(limit))
        return list(result.scalars().all())

    async def get_candidate(self, owner_id: str, candidate_id: str) -> KGGraphCandidate:
        candidate = await self.db.scalar(select(KGGraphCandidate).where(
            KGGraphCandidate.owner_id == owner_id, KGGraphCandidate.id == candidate_id))
        if candidate is None: raise GraphValidationError("Unknown graph candidate")
        return candidate

    async def _revalidate_candidate(self, owner_id: str, candidate: KGGraphCandidate, allow_private: bool) -> DocumentIntelligence:
        await self._owned_document(owner_id, candidate.document_id)
        if candidate.private_source and not allow_private:
            raise GraphValidationError("Private evidence requires explicit --allow-private")
        snapshot = self.load_source(candidate.document_id, candidate.extraction_run_id)
        try: latest = self.evidence_store.get(candidate.document_id)
        except Exception as exc: raise GraphValidationError("Current Phase 4 extraction could not be resolved") from exc
        if latest.run_id != candidate.extraction_run_id:
            raise GraphValidationError("Phase 4 source run has been superseded; import the current successful run")
        record = next((r for r in snapshot.knowledge_records if r.record_id == candidate.record_id), None)
        if record is None or record.review_status != "approved":
            raise GraphValidationError("Phase 4 record is no longer approved; graph action refused")
        frozen = candidate.source_snapshot
        if any(getattr(record, key) != frozen.get(key) for key in (
            "record_id", "category", "exact_text", "document_id", "page_number", "section_id", "block_id",
            "char_start", "char_end", "extraction_method", "extraction_version")):
            raise GraphValidationError("Phase 4 record changed after import; re-import the corrected run")
        page = next((p["text"] for p in snapshot.pages if p["page_number"] == record.page_number), None)
        if page is None or page[record.char_start:record.char_end] != record.exact_text:
            raise GraphValidationError("Phase 4 evidence no longer matches its source offsets")
        return snapshot

    async def review_candidate(self, owner_id: str, candidate_id: str, action: str, reviewer: str,
                              node_type: str | None = None, canonical_name: str | None = None,
                              existing_node_id: str | None = None, allow_private: bool = False) -> dict[str, Any]:
        candidate = await self.get_candidate(owner_id, candidate_id)
        if action not in {"approve_node", "reject"}:
            raise GraphValidationError("Candidate action must be approve_node or reject")
        if candidate.status != "pending": raise GraphValidationError("Candidate is no longer pending")
        await self._revalidate_candidate(owner_id, candidate, allow_private)
        before = {"status": candidate.status, "node_type": node_type, "canonical_name": canonical_name}
        if action == "reject":
            candidate.status = "rejected"
            node = None
        else:
            if existing_node_id:
                if not node_type:
                    raise GraphValidationError("Assigning an existing node requires its node type")
                node_type = node_type.upper()
                node = await self.node_detail(owner_id, existing_node_id)
                if node.node_type != node_type: raise GraphValidationError("Assigned node has an incompatible type")
                node.last_confirmed_at = datetime.utcnow(); node.version += 1
            else:
                node_type = (node_type or "").upper()
                canonical_name = (canonical_name or "").strip()
                if node_type not in NODE_TYPES | self.custom_node_types or not canonical_name:
                    raise GraphValidationError("Approval requires a valid node type and canonical name")
                key = normalize_identity(canonical_name)
                node = KGNode(owner_id=owner_id, node_type=node_type, canonical_name=canonical_name,
                    identity_key=key, identifiers={}, metadata_json={"candidate_category": candidate.category},
                    first_document_id=candidate.document_id, first_extraction_run_id=candidate.extraction_run_id,
                    review_status="approved", last_confirmed_at=datetime.utcnow())
                self.db.add(node)
                await self.db.flush()
            candidate.status = "approved"
            self.db.add(self._evidence_for_node(owner_id, node.id, candidate, reviewer))
            await self.db.flush()
        candidate.reviewer = reviewer
        candidate.reviewed_at = datetime.utcnow()
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="candidate", target_id=candidate.id,
            action=action, reviewer=reviewer, old_value={"status": "pending"},
            new_value={**before, "status": candidate.status, "node_id": node.id if node else None},
            source_document_id=candidate.document_id, source_extraction_run_id=candidate.extraction_run_id))
        await self.db.flush()
        return {"candidate_id": candidate.id, "status": candidate.status, "node_id": node.id if node else None}

    def _evidence_for_node(self, owner_id: str, node_id: str, candidate: KGGraphCandidate, reviewer: str) -> KGGraphEvidence:
        return KGGraphEvidence(owner_id=owner_id, node_id=node_id,
            source_document_id=candidate.document_id, source_paper_id=candidate.paper_id,
            extraction_run_id=candidate.extraction_run_id, record_id=candidate.record_id,
            source_block_id=candidate.block_id, page_number=candidate.page_number, section_id=candidate.section_id,
            exact_text=candidate.exact_text, char_start=candidate.char_start, char_end=candidate.char_end,
            extraction_method=candidate.extraction_method, extraction_version=candidate.extraction_version,
            review_status="approved", reviewer=reviewer, reviewed_at=datetime.utcnow(), private_source=candidate.private_source)

    async def add_relationship(self, owner_id: str, candidate_id: str, source_node_id: str,
                               relation_type: str, target_node_id: str, reviewer: str,
                               allow_private: bool = False) -> KGRelationship:
        candidate = await self.get_candidate(owner_id, candidate_id)
        if candidate.status == "rejected": raise GraphValidationError("Rejected candidate cannot support an edge")
        await self._revalidate_candidate(owner_id, candidate, allow_private)
        source = await self.node_detail(owner_id, source_node_id)
        target = await self.node_detail(owner_id, target_node_id)
        relation_type = relation_type.upper()
        validate_relationship(source.node_type, relation_type, target.node_type, self.custom_relationships)
        if source.id == target.id: raise GraphValidationError("Self-referential relationships are not allowed")
        edge = KGRelationship(owner_id=owner_id, source_node_id=source.id, target_node_id=target.id,
            relationship_type=relation_type, direction="directed", assertion_status="current", review_status="approved",
            confidence=candidate.confidence, first_document_id=candidate.document_id,
            first_extraction_run_id=candidate.extraction_run_id, last_confirmed_at=datetime.utcnow())
        prior = await self.db.scalar(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.source_node_id == source.id, KGRelationship.target_node_id == target.id,
            KGRelationship.relationship_type == relation_type, KGRelationship.review_status == "approved",
            KGRelationship.assertion_status == "current").order_by(KGRelationship.id).limit(1))
        if prior is not None:
            same_evidence = await self.db.scalar(select(KGGraphEvidence.id).where(
                KGGraphEvidence.relationship_id == prior.id, KGGraphEvidence.source_document_id == candidate.document_id,
                KGGraphEvidence.extraction_run_id == candidate.extraction_run_id, KGGraphEvidence.record_id == candidate.record_id))
            if same_evidence: return prior
            edge = prior
            edge.last_confirmed_at = datetime.utcnow(); edge.version += 1
        else:
            self.db.add(edge)
            await self.db.flush()
        self.db.add(KGGraphEvidence(owner_id=owner_id, relationship_id=edge.id,
            source_document_id=candidate.document_id, source_paper_id=candidate.paper_id,
            extraction_run_id=candidate.extraction_run_id, record_id=candidate.record_id, source_block_id=candidate.block_id,
            page_number=candidate.page_number, section_id=candidate.section_id, exact_text=candidate.exact_text,
            char_start=candidate.char_start, char_end=candidate.char_end, extraction_method=candidate.extraction_method,
            extraction_version=candidate.extraction_version, review_status="approved", reviewer=reviewer,
            reviewed_at=datetime.utcnow(), private_source=candidate.private_source))
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="relationship", target_id=edge.id,
            action="approve_relationship", reviewer=reviewer, old_value={}, new_value={"source": source.id,
                "type": relation_type, "target": target.id, "candidate_id": candidate.id},
            source_document_id=candidate.document_id, source_extraction_run_id=candidate.extraction_run_id))
        await self.db.flush()
        return edge

    async def search_nodes(self, owner_id: str, query: str = "", node_type: str | None = None,
                           identifiers: str | None = None, limit: int = 50, offset: int = 0,
                           paper_id: str | None = None) -> list[KGNode]:
        await self.sync_offline_concepts_if_empty(owner_id)
        limit = min(max(limit, 1), MAX_RESULTS)
        stmt = select(KGNode).where(KGNode.owner_id == owner_id, KGNode.review_status == "approved", KGNode.merged_into_id.is_(None))
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(KGNode.canonical_name.ilike(like), KGNode.identity_key.ilike(like)))
        if node_type: stmt = stmt.where(KGNode.node_type == node_type.upper())
        if identifiers: stmt = stmt.where(cast(KGNode.identifiers, String).ilike(f"%{identifiers}%"))
        if paper_id and paper_id != "all":
            doc_subq = select(Document.id).where(Document.paper_id == paper_id)
            ev_subq = select(KGGraphEvidence.node_id).where(
                KGGraphEvidence.owner_id == owner_id,
                or_(
                    KGGraphEvidence.source_paper_id == paper_id,
                    KGGraphEvidence.source_document_id.in_(doc_subq),
                )
            )
            stmt = stmt.where(or_(
                KGNode.id.in_(ev_subq),
                KGNode.first_document_id.in_(doc_subq),
            ))
        result = await self.db.execute(stmt.order_by(KGNode.canonical_name, KGNode.id).offset(max(0, offset)).limit(limit))
        rows = list(result.scalars().all())
        visible = []
        for node in rows:
            try: visible.append(await self.node_detail(owner_id, node.id))
            except GraphValidationError: continue
        return visible

    async def sync_offline_concepts_if_empty(self, owner_id: str) -> int:
        from sqlalchemy import func
        count = await self.db.scalar(select(func.count(KGNode.id)).where(KGNode.owner_id == owner_id))
        if count and count > 0:
            return count

        import os
        from pathlib import Path
        import sqlite3
        from rag.config.settings import settings
        from rag.intelligence.concept_graph_extractor import ConceptGraphExtractor

        db_bind = self.db.bind
        db_url = str(db_bind.url if db_bind else "")
        db_path = None
        if "sqlite" in db_url:
            db_path = Path(db_url.split("///")[-1].replace("/", os.sep))
        if not db_path or not db_path.exists():
            db_path = Path(os.environ.get("LOCALAPPDATA", "")) / "ResearchLens" / "Library" / "library.sqlite3"

        lex_candidates = [
            (db_path.parent / "indexes" / "researchlens_lexical.sqlite3") if db_path else None,
            Path(os.environ.get("CHROMA_PERSIST_DIR", "")) / "researchlens_lexical.sqlite3",
            Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3",
            Path(os.environ.get("LOCALAPPDATA", "")) / "ResearchLens" / "Library" / "indexes" / "researchlens_lexical.sqlite3",
            Path(".chroma") / "researchlens_lexical.sqlite3",
        ]
        lex_path = next((p for p in lex_candidates if p and p.is_file()), None)
        if not lex_path:
            return 0

        class SimpleChunk:
            def __init__(self, text, section, page_start):
                self.text = text
                self.name = section
                self.page_start = page_start

        try:
            conn = sqlite3.connect(str(lex_path))
            cur = conn.cursor()
            cur.execute(
                "SELECT chunk_id, owner_id, paper_id, document_id, section, page_start, text FROM lexical_chunks"
            )
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return 0

            grouped: dict[tuple, list] = {}
            for r in rows:
                key = (r[1] or owner_id, r[2] or "", r[3] or "")
                grouped.setdefault(key, []).append(SimpleChunk(r[6], r[4], r[5]))

            if db_path and db_path.exists():
                extractor = ConceptGraphExtractor(db_path=db_path)
                for (doc_owner, paper_id, doc_id), chunk_list in grouped.items():
                    extractor.ingest_document_kg(
                        owner_id=owner_id,
                        paper_id=paper_id,
                        document_id=doc_id,
                        chunks_or_sections=chunk_list,
                        db_path=db_path,
                    )
        except Exception as exc:
            logger.debug("Failed to auto-sync concepts: %s", exc)
        return await self.db.scalar(select(func.count(KGNode.id)).where(KGNode.owner_id == owner_id)) or 0

    async def node_detail(self, owner_id: str, node_id: str) -> KGNode:
        node = await self.db.scalar(select(KGNode).where(KGNode.owner_id == owner_id, KGNode.id == node_id,
            KGNode.review_status == "approved", KGNode.merged_into_id.is_(None)))
        if node is None: raise GraphValidationError("Unknown active graph node")
        evidence_rows = await self.db.execute(select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id,
            KGGraphEvidence.node_id == node_id, KGGraphEvidence.review_status == "approved").limit(200))
        if not any([await self._evidence_current_for_owner(owner_id, row) for row in evidence_rows.scalars().all()]):
            raise GraphValidationError("Unknown active graph node")
        return node

    async def node_evidence(self, owner_id: str, node_id: str, allow_private: bool = False) -> list[KGGraphEvidence]:
        await self.node_detail(owner_id, node_id)
        stmt = select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id, KGGraphEvidence.node_id == node_id,
                                            KGGraphEvidence.review_status == "approved")
        if not allow_private: stmt = stmt.where(KGGraphEvidence.private_source.is_(False))
        result = await self.db.execute(stmt.order_by(KGGraphEvidence.created_at, KGGraphEvidence.id).limit(MAX_RESULTS))
        visible = []
        for row in result.scalars().all():
            if await self._evidence_current_for_owner(owner_id, row): visible.append(row)
        return visible

    async def node_relationships(self, owner_id: str, node_id: str, allow_private: bool = False) -> list[dict[str, Any]]:
        await self.node_detail(owner_id, node_id)
        result = await self.db.execute(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.review_status == "approved", KGRelationship.assertion_status == "current",
            or_(KGRelationship.source_node_id == node_id, KGRelationship.target_node_id == node_id))
            .order_by(KGRelationship.relationship_type, KGRelationship.id).limit(MAX_RESULTS))
        output = []
        for edge in result.scalars().all():
            evidence = await self.edge_evidence(owner_id, edge.id, allow_private)
            output.append({"relationship": edge, "evidence": evidence or []})
        return output

    async def edge_evidence(self, owner_id: str, edge_id: str, allow_private: bool = False) -> list[KGGraphEvidence]:
        stmt = select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id,
            KGGraphEvidence.relationship_id == edge_id, KGGraphEvidence.review_status == "approved")
        if not allow_private: stmt = stmt.where(KGGraphEvidence.private_source.is_(False))
        result = await self.db.execute(stmt.order_by(KGGraphEvidence.created_at, KGGraphEvidence.id).limit(50))
        visible = []
        for row in result.scalars().all():
            if await self._evidence_current_for_owner(owner_id, row): visible.append(row)
        return visible

    async def _evidence_current_for_owner(self, owner_id: str, evidence: KGGraphEvidence) -> bool:
        try:
            await self._owned_document(owner_id, evidence.source_document_id)
        except GraphValidationError:
            return False
        if (
            evidence.extraction_method == "regex_offline"
            or getattr(evidence, "extraction_run_id", "").startswith("run_offline")
        ):
            return True
        return self._evidence_current(evidence)

    def _evidence_current(self, evidence: KGGraphEvidence, store: ExtractionStore | None = None) -> bool:
        """Confirm that Phase 4 has not since rejected or changed this exact record."""
        try:
            evidence_store = store or self.evidence_store
            latest = evidence_store.get(evidence.source_document_id)
            if latest.run_id != evidence.extraction_run_id: return False
            cache_key = (str(evidence_store.root), evidence.source_document_id, evidence.extraction_run_id)
            history_path = evidence_store.root / evidence.source_document_id / "review_history.jsonl"
            try:
                stat = history_path.stat()
                fingerprint = (stat.st_mtime_ns, stat.st_size)
            except FileNotFoundError:
                fingerprint = (0, 0)
            cached = self._source_snapshot_cache.get(cache_key)
            if cached is not None and cached[0] == fingerprint:
                snapshot = cached[1]
            else:
                snapshot = evidence_store.get(evidence.source_document_id, evidence.extraction_run_id)
                if snapshot.document_id != evidence.source_document_id or snapshot.run_id != evidence.extraction_run_id:
                    return False
                self._source_snapshot_cache[cache_key] = (fingerprint, snapshot)
            record = next((r for r in snapshot.knowledge_records if r.record_id == evidence.record_id), None)
            if record is None or record.review_status != "approved": return False
            page = next((p["text"] for p in snapshot.pages if p["page_number"] == record.page_number), None)
            return bool(page is not None and page[record.char_start:record.char_end] == record.exact_text == evidence.exact_text
                and record.document_id == evidence.source_document_id and record.block_id == evidence.source_block_id
                and record.section_id == evidence.section_id and record.char_start == evidence.char_start
                and record.char_end == evidence.char_end and snapshot.private_source == evidence.private_source)
        except Exception:
            return False

    async def _active_edges(self, owner_id: str, node_ids: list[str], relation_types: set[str] | None,
                            limit: int, allow_private: bool = False) -> list[KGRelationship]:
        if not node_ids: return []
        stmt = select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.review_status == "approved", KGRelationship.assertion_status == "current",
            or_(KGRelationship.source_node_id.in_(node_ids), KGRelationship.target_node_id.in_(node_ids)))
        if relation_types: stmt = stmt.where(KGRelationship.relationship_type.in_(relation_types))
        if not allow_private:
            stmt = stmt.where(exists(select(KGGraphEvidence.id).where(
                KGGraphEvidence.relationship_id == KGRelationship.id,
                KGGraphEvidence.review_status == "approved", KGGraphEvidence.private_source.is_(False))))
        result = await self.db.execute(stmt.order_by(KGRelationship.id).limit(limit))
        return list(result.scalars().all())

    async def neighborhood(self, owner_id: str, node_id: str, depth: int = 1,
                           relation_types: set[str] | None = None, node_types: set[str] | None = None,
                           max_results: int = 100, allow_private: bool = False) -> dict[str, Any]:
        depth = min(max(depth, 1), MAX_DEPTH); max_results = min(max(max_results, 1), MAX_RESULTS)
        await self.node_detail(owner_id, node_id)
        seen = {node_id}; frontier = {node_id}; nodes = []; edges = []
        for _ in range(depth):
            layer_edges = await self._active_edges(owner_id, sorted(frontier), relation_types, max_results, allow_private)
            next_ids: set[str] = set()
            for edge in layer_edges:
                other = edge.target_node_id if edge.source_node_id in frontier else edge.source_node_id
                edge_evs = await self.edge_evidence(owner_id, edge.id, allow_private)
                if not edge_evs: continue
                if other not in seen:
                    candidate = await self.db.scalar(select(KGNode).where(KGNode.id == other, KGNode.owner_id == owner_id,
                        KGNode.review_status == "approved", KGNode.merged_into_id.is_(None)))
                    if candidate is None: continue
                    try: candidate = await self.node_detail(owner_id, candidate.id)
                    except GraphValidationError: continue
                    if node_types and candidate.node_type not in node_types: continue
                    if len(nodes) >= max_results: break
                    nodes.append(candidate); next_ids.add(other); seen.add(other)
                if edge.id not in {item["relationship"].id for item in edges} and len(edges) < max_results:
                    edges.append({"relationship": edge, "evidence": edge_evs})
            frontier = next_ids
            if not frontier or len(nodes) >= max_results: break
        return {"root_node_id": node_id, "depth": depth, "nodes": nodes, "edges": edges,
                "truncated": len(nodes) >= max_results}

    async def find_path(self, owner_id: str, source_id: str, target_id: str, max_depth: int = 4,
                        relation_types: set[str] | None = None, allow_private: bool = False,
                        node_types: set[str] | None = None) -> dict[str, Any] | None:
        max_depth = min(max(max_depth, 1), MAX_DEPTH)
        await self.node_detail(owner_id, source_id); await self.node_detail(owner_id, target_id)
        queue = deque([(source_id, [])]); visited = {source_id}
        while queue:
            node_id, path = queue.popleft()
            if len(path) >= max_depth: continue
            edges = await self._active_edges(owner_id, [node_id], relation_types, MAX_RESULTS, allow_private)
            edges.sort(key=lambda e: (e.relationship_type, e.id))
            for edge in edges:
                other = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
                if other in visited: continue
                evidence = await self.edge_evidence(owner_id, edge.id, allow_private)
                if not evidence: continue
                candidate = await self.db.scalar(select(KGNode).where(KGNode.id == other, KGNode.owner_id == owner_id,
                    KGNode.review_status == "approved", KGNode.merged_into_id.is_(None)))
                if candidate is None or (node_types and candidate.node_type not in node_types): continue
                try: await self.node_detail(owner_id, candidate.id)
                except GraphValidationError: continue
                next_path = path + [edge]
                if other == target_id:
                    steps = []
                    for item in next_path:
                        item_evidence = await self.edge_evidence(owner_id, item.id, allow_private)
                        if not item_evidence: break
                        steps.append({"relationship": item, "evidence": item_evidence})
                    if len(steps) != len(next_path): continue
                    return {"source_node_id": source_id, "target_node_id": target_id, "steps": steps}
                visited.add(other); queue.append((other, next_path))
        return None

    async def identity_suggestions(self, owner_id: str, node_id: str, threshold: float = .84, limit: int = 30) -> list[dict[str, Any]]:
        node = await self.node_detail(owner_id, node_id)
        rows = await self.db.execute(select(KGNode).where(KGNode.owner_id == owner_id, KGNode.id != node_id,
            KGNode.node_type == node.node_type, KGNode.review_status == "approved", KGNode.merged_into_id.is_(None))
            .order_by(KGNode.canonical_name).limit(MAX_RESULTS))
        suggestions = []
        for other in rows.scalars().all():
            score = SequenceMatcher(None, node.identity_key, other.identity_key).ratio()
            shared_identifier = any(key in (other.identifiers or {}) and value is not None and
                                    (other.identifiers or {}).get(key) == value
                                    for key, value in (node.identifiers or {}).items())
            alias = await self.db.scalar(select(KGNodeAlias.id).where(KGNodeAlias.owner_id == owner_id,
                KGNodeAlias.node_id == other.id, KGNodeAlias.identity_key == node.identity_key, KGNodeAlias.status == "approved"))
            if score >= threshold or alias or shared_identifier:
                suggestions.append({"node_id": other.id, "name": other.canonical_name,
                    "similarity": 1.0 if shared_identifier else round(score, 3),
                    "match_basis": "verified_identifier" if shared_identifier else ("approved_alias" if alias else "name_similarity"),
                    "automatic_merge": False})
        return sorted(suggestions, key=lambda item: (-item["similarity"], item["node_id"]))[:max(1, min(limit, 100))]

    async def add_alias(self, owner_id: str, node_id: str, alias: str, reviewer: str) -> KGNodeAlias:
        node = await self.node_detail(owner_id, node_id)
        alias = alias.strip()
        if not alias or len(alias) > 500: raise GraphValidationError("Alias must contain 1-500 characters")
        row = KGNodeAlias(owner_id=owner_id, node_id=node.id, node_type=node.node_type, alias=alias,
                          identity_key=normalize_identity(alias), status="approved", reviewer=reviewer)
        self.db.add(row)
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="node_alias", target_id=row.id,
            action="add_alias", reviewer=reviewer, old_value={}, new_value={"node_id": node.id, "alias": alias}))
        await self.db.flush()
        return row

    async def correct_node(self, owner_id: str, node_id: str, canonical_name: str,
                           node_type: str, reviewer: str, identifiers: dict[str, Any] | None = None) -> KGNode:
        node = await self.node_detail(owner_id, node_id)
        canonical_name = canonical_name.strip(); node_type = node_type.upper()
        if not canonical_name or len(canonical_name) > 500 or node_type not in NODE_TYPES | self.custom_node_types:
            raise GraphValidationError("A valid canonical name and node type are required")
        edges = await self.db.execute(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.review_status == "approved", or_(KGRelationship.source_node_id == node.id,
            KGRelationship.target_node_id == node.id)))
        for edge in edges.scalars().all():
            source_type = node_type if edge.source_node_id == node.id else (await self.db.get(KGNode, edge.source_node_id)).node_type
            target_type = node_type if edge.target_node_id == node.id else (await self.db.get(KGNode, edge.target_node_id)).node_type
            validate_relationship(source_type, edge.relationship_type, target_type, self.custom_relationships)
        old = {"canonical_name": node.canonical_name, "node_type": node.node_type,
               "identity_key": node.identity_key, "identifiers": node.identifiers}
        node.canonical_name = canonical_name; node.node_type = node_type; node.identity_key = normalize_identity(canonical_name)
        if identifiers is not None: node.identifiers = {**(node.identifiers or {}), **identifiers}
        node.version += 1
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="node", target_id=node.id, action="correct",
            reviewer=reviewer, old_value=old, new_value={"canonical_name": canonical_name,
                "node_type": node_type, "identity_key": node.identity_key, "identifiers": node.identifiers},
            source_document_id=node.first_document_id, source_extraction_run_id=node.first_extraction_run_id))
        await self.db.flush()
        return node

    async def set_relationship_status(self, owner_id: str, relationship_id: str, status: str,
                                     reviewer: str, reason: str) -> KGRelationship:
        status = status.lower()
        if status not in {"current", "disputed", "superseded", "retracted"}:
            raise GraphValidationError("Status must be current, disputed, superseded, or retracted")
        edge = await self.db.scalar(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.id == relationship_id, KGRelationship.review_status == "approved"))
        if edge is None: raise GraphValidationError("Unknown approved relationship")
        old = {"assertion_status": edge.assertion_status, "version": edge.version}
        edge.assertion_status = status; edge.version += 1
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="relationship", target_id=edge.id,
            action="set_assertion_status", reviewer=reviewer, old_value=old,
            new_value={"assertion_status": status, "reason": reason}, source_document_id=edge.first_document_id,
            source_extraction_run_id=edge.first_extraction_run_id))
        await self.db.flush()
        return edge

    async def correct_relationship(self, owner_id: str, relationship_id: str, source_node_id: str,
                                   relation_type: str, target_node_id: str,
                                   reviewer: str) -> KGRelationship:
        edge = await self.db.scalar(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.id == relationship_id, KGRelationship.review_status == "approved"))
        if edge is None: raise GraphValidationError("Unknown approved relationship")
        source = await self.node_detail(owner_id, source_node_id)
        target = await self.node_detail(owner_id, target_node_id)
        relation_type = relation_type.upper()
        validate_relationship(source.node_type, relation_type, target.node_type, self.custom_relationships)
        if source.id == target.id: raise GraphValidationError("Self-referential relationships are not allowed")
        evidence_count = await self.db.scalar(select(func.count()).select_from(KGGraphEvidence).where(
            KGGraphEvidence.relationship_id == edge.id, KGGraphEvidence.review_status == "approved")) or 0
        if not evidence_count: raise GraphValidationError("Relationship correction requires retained approved evidence")
        old = {"source_node_id": edge.source_node_id, "relationship_type": edge.relationship_type,
               "target_node_id": edge.target_node_id, "version": edge.version}
        edge.source_node_id = source.id; edge.relationship_type = relation_type; edge.target_node_id = target.id
        edge.version += 1
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="relationship", target_id=edge.id,
            action="correct", reviewer=reviewer, old_value=old, new_value={"source_node_id": source.id,
                "relationship_type": relation_type, "target_node_id": target.id},
            source_document_id=edge.first_document_id, source_extraction_run_id=edge.first_extraction_run_id))
        await self.db.flush()
        return edge

    async def reject_identity_suggestion(self, owner_id: str, source_id: str, target_id: str,
                                         reviewer: str, reason: str) -> KGIdentityDecision:
        source = await self.node_detail(owner_id, source_id); target = await self.node_detail(owner_id, target_id)
        if source.node_type != target.node_type or source.id == target.id:
            raise GraphValidationError("Identity suggestions must be distinct nodes with compatible types")
        decision = KGIdentityDecision(owner_id=owner_id, source_node_id=source.id, target_node_id=target.id,
            decision="rejected_match", reviewer=reviewer, reason=reason, relationship_snapshot={})
        self.db.add(decision)
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="identity", target_id=decision.id,
            action="reject_match", reviewer=reviewer, old_value={}, new_value={"source": source.id,
                "target": target.id, "reason": reason}))
        await self.db.flush()
        return decision

    async def rollback_import(self, owner_id: str, import_run_id: str, reviewer: str, reason: str) -> dict[str, Any]:
        run = await self.db.scalar(select(KGImportRun).where(KGImportRun.id == import_run_id, KGImportRun.owner_id == owner_id))
        if run is None: raise GraphValidationError("Unknown import run")
        if run.status == "rolled_back": return {"import_run_id": run.id, "status": "rolled_back", "idempotent": True}
        candidates = await self.db.execute(select(KGGraphCandidate).where(
            KGGraphCandidate.import_run_id == run.id, KGGraphCandidate.owner_id == owner_id))
        rows = list(candidates.scalars().all())
        if any(candidate.status != "pending" for candidate in rows):
            raise GraphValidationError("Rollback is allowed only before any candidate has been reviewed into the graph")
        run.status = "rolled_back"
        for candidate in rows:
            candidate.status = "rolled_back"; candidate.reviewer = reviewer; candidate.reviewed_at = datetime.utcnow()
            self.db.add(KGReviewEvent(owner_id=owner_id, target_type="candidate", target_id=candidate.id,
                action="rollback_import", reviewer=reviewer, old_value={"status": "pending"},
                new_value={"status": "rolled_back", "reason": reason}, source_document_id=candidate.document_id,
                source_extraction_run_id=candidate.extraction_run_id))
        await self.db.flush()
        return {"import_run_id": run.id, "status": run.status, "candidate_count": len(rows), "idempotent": False}

    async def merge_nodes(self, owner_id: str, primary_id: str, duplicate_id: str, reviewer: str, reason: str) -> KGIdentityDecision:
        primary = await self.node_detail(owner_id, primary_id); duplicate = await self.node_detail(owner_id, duplicate_id)
        if primary.id == duplicate.id or primary.node_type != duplicate.node_type:
            raise GraphValidationError("Merge requires two distinct nodes of the same type")
        edges_result = await self.db.execute(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            or_(KGRelationship.source_node_id == duplicate.id, KGRelationship.target_node_id == duplicate.id)))
        edge_snapshot = []
        for edge in edges_result.scalars().all():
            old_src, old_tgt = edge.source_node_id, edge.target_node_id
            new_src = primary.id if old_src == duplicate.id else old_src
            new_tgt = primary.id if old_tgt == duplicate.id else old_tgt
            if new_src == new_tgt: raise GraphValidationError("Merge would create a self-relationship; resolve that edge first")
            src = primary if new_src == primary.id else await self.db.get(KGNode, new_src)
            tgt = primary if new_tgt == primary.id else await self.db.get(KGNode, new_tgt)
            validate_relationship(src.node_type, edge.relationship_type, tgt.node_type, self.custom_relationships)
            edge_snapshot.append({"id": edge.id, "source_node_id": old_src, "target_node_id": old_tgt})
        ev_result = await self.db.execute(select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id, KGGraphEvidence.node_id == duplicate.id))
        evidence_snapshot = [{"id": e.id, "node_id": e.node_id} for e in ev_result.scalars().all()]
        aliases_result = await self.db.execute(select(KGNodeAlias).where(KGNodeAlias.owner_id == owner_id, KGNodeAlias.node_id == duplicate.id))
        alias_snapshot = [{"id": a.id, "node_id": a.node_id} for a in aliases_result.scalars().all()]
        for item in edge_snapshot:
            edge = await self.db.get(KGRelationship, item["id"])
            if edge.source_node_id == duplicate.id: edge.source_node_id = primary.id
            if edge.target_node_id == duplicate.id: edge.target_node_id = primary.id
        for item in evidence_snapshot: (await self.db.get(KGGraphEvidence, item["id"])).node_id = primary.id
        for item in alias_snapshot: (await self.db.get(KGNodeAlias, item["id"])).node_id = primary.id
        duplicate.review_status = "merged"; duplicate.merged_into_id = primary.id; duplicate.version += 1
        primary.last_confirmed_at = datetime.utcnow(); primary.version += 1
        snapshot = {"relationships": edge_snapshot, "evidence": evidence_snapshot, "aliases": alias_snapshot}
        decision = KGIdentityDecision(owner_id=owner_id, source_node_id=duplicate.id, target_node_id=primary.id,
            decision="merge", reviewer=reviewer, reason=reason, relationship_snapshot=snapshot)
        self.db.add(decision)
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="node", target_id=duplicate.id, action="merge",
            reviewer=reviewer, old_value={"node_id": duplicate.id, "status": "approved"},
            new_value={"merged_into": primary.id, "reason": reason}))
        await self.db.flush()
        return decision

    async def undo_merge(self, owner_id: str, decision_id: str, reviewer: str, reason: str) -> KGIdentityDecision:
        original = await self.db.scalar(select(KGIdentityDecision).where(KGIdentityDecision.owner_id == owner_id,
            KGIdentityDecision.id == decision_id, KGIdentityDecision.decision == "merge"))
        if original is None: raise GraphValidationError("Merge decision not found")
        duplicate = await self.db.get(KGNode, original.source_node_id)
        primary = await self.db.get(KGNode, original.target_node_id)
        if duplicate is None or primary is None or duplicate.merged_into_id != primary.id:
            raise GraphValidationError("Merge is no longer in an undoable state")
        for item in original.relationship_snapshot.get("relationships", []):
            edge = await self.db.get(KGRelationship, item["id"])
            if edge is None: raise GraphValidationError("A merged relationship is missing; refusing partial undo")
            old_source = await self.db.get(KGNode, item["source_node_id"])
            old_target = await self.db.get(KGNode, item["target_node_id"])
            validate_relationship(old_source.node_type, edge.relationship_type, old_target.node_type, self.custom_relationships)
            edge.source_node_id = item["source_node_id"]; edge.target_node_id = item["target_node_id"]
        for item in original.relationship_snapshot.get("evidence", []):
            evidence = await self.db.get(KGGraphEvidence, item["id"])
            if evidence is not None: evidence.node_id = item["node_id"]
        for item in original.relationship_snapshot.get("aliases", []):
            alias = await self.db.get(KGNodeAlias, item["id"])
            if alias is not None: alias.node_id = item["node_id"]
        duplicate.review_status = "approved"; duplicate.merged_into_id = None; duplicate.version += 1
        event = KGIdentityDecision(owner_id=owner_id, source_node_id=duplicate.id, target_node_id=primary.id,
            decision="undo_merge", reviewer=reviewer, reason=reason, relationship_snapshot={"undo_of": original.id})
        self.db.add(event)
        self.db.add(KGReviewEvent(owner_id=owner_id, target_type="node", target_id=duplicate.id, action="undo_merge",
            reviewer=reviewer, old_value={"merged_into": primary.id}, new_value={"status": "approved", "reason": reason}))
        await self.db.flush()
        return event

    async def audit(self, owner_id: str, evidence_store: ExtractionStore | None = None) -> dict[str, Any]:
        nodes = dict((kind, int(count)) for kind, count in (await self.db.execute(select(KGNode.node_type, func.count()).where(
            KGNode.owner_id == owner_id, KGNode.review_status == "approved", KGNode.merged_into_id.is_(None)).group_by(KGNode.node_type))).all())
        edges = dict((kind, int(count)) for kind, count in (await self.db.execute(select(KGRelationship.relationship_type, func.count()).where(
            KGRelationship.owner_id == owner_id, KGRelationship.review_status == "approved").group_by(KGRelationship.relationship_type))).all())
        evidence_count = await self.db.scalar(select(func.count()).select_from(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id)) or 0
        pending = await self.db.scalar(select(func.count()).select_from(KGGraphCandidate).where(KGGraphCandidate.owner_id == owner_id, KGGraphCandidate.status == "pending")) or 0
        accepted = await self.db.scalar(select(func.count()).select_from(KGGraphCandidate).where(KGGraphCandidate.owner_id == owner_id, KGGraphCandidate.status == "approved")) or 0
        rejected = await self.db.scalar(select(func.count()).select_from(KGGraphCandidate).where(KGGraphCandidate.owner_id == owner_id, KGGraphCandidate.status == "rejected")) or 0
        issues: list[dict[str, Any]] = []
        dup_rows = await self.db.execute(select(KGNode.node_type, KGNode.identity_key, func.count()).where(
            KGNode.owner_id == owner_id, KGNode.merged_into_id.is_(None), KGNode.review_status == "approved")
            .group_by(KGNode.node_type, KGNode.identity_key).having(func.count() > 1))
        duplicate_groups = [{"node_type": t, "identity_key": key, "count": int(count)} for t, key, count in dup_rows.all()]
        edge_rows = await self.db.stream_scalars(select(KGRelationship).where(KGRelationship.owner_id == owner_id,
            KGRelationship.review_status == "approved").execution_options(yield_per=100))
        accepted_edge_ids: set[str] = set()
        async for edge in edge_rows:
            accepted_edge_ids.add(edge.id)
            src = await self.db.get(KGNode, edge.source_node_id); tgt = await self.db.get(KGNode, edge.target_node_id)
            if src is None or tgt is None:
                issues.append({"kind": "orphan_edge", "relationship_id": edge.id}); continue
            try: validate_relationship(src.node_type, edge.relationship_type, tgt.node_type, self.custom_relationships)
            except GraphValidationError as exc: issues.append({"kind": "invalid_endpoint_types", "relationship_id": edge.id, "detail": str(exc)})
            count = await self.db.scalar(select(func.count()).select_from(KGGraphEvidence).where(
                KGGraphEvidence.relationship_id == edge.id, KGGraphEvidence.review_status == "approved")) or 0
            if not count: issues.append({"kind": "accepted_edge_without_approved_evidence", "relationship_id": edge.id})
            if edge.source_node_id == edge.target_node_id: issues.append({"kind": "self_relationship", "relationship_id": edge.id})
        node_rows = await self.db.stream_scalars(select(KGNode).where(KGNode.owner_id == owner_id,
            KGNode.merged_into_id.is_(None), KGNode.review_status == "approved").execution_options(yield_per=100))
        assertion_count = sum(nodes.values()) + sum(edges.values())
        accepted_node_ids: set[str] = set()
        async for node in node_rows:
            accepted_node_ids.add(node.id)
            count = await self.db.scalar(select(func.count()).select_from(KGGraphEvidence).where(
                KGGraphEvidence.owner_id == owner_id, KGGraphEvidence.node_id == node.id,
                KGGraphEvidence.review_status == "approved")) or 0
            if not count: issues.append({"kind": "accepted_node_without_approved_evidence", "node_id": node.id})
        accepted_edge_rows = await self.db.stream_scalars(select(KGRelationship).where(
            KGRelationship.owner_id == owner_id, KGRelationship.review_status == "approved").execution_options(yield_per=100))
        async for edge in accepted_edge_rows:
            count = await self.db.scalar(select(func.count()).select_from(KGGraphEvidence).where(
                KGGraphEvidence.relationship_id == edge.id, KGGraphEvidence.review_status == "approved")) or 0
        ev_rows = await self.db.stream_scalars(select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id)
            .order_by(KGGraphEvidence.id).execution_options(yield_per=100))
        store = evidence_store or self.evidence_store
        live_node_ids: set[str] = set()
        live_edge_ids: set[str] = set()
        async for evidence in ev_rows:
            try:
                await self._owned_document(owner_id, evidence.source_document_id)
                snapshot = store.get(evidence.source_document_id, evidence.extraction_run_id)
                page = next((p["text"] for p in snapshot.pages if p["page_number"] == evidence.page_number), None)
                if (page is None or evidence.char_start < 0 or evidence.char_end <= evidence.char_start or
                    evidence.char_end > len(page) or page[evidence.char_start:evidence.char_end] != evidence.exact_text):
                    issues.append({"kind": "invalid_evidence_offsets", "evidence_id": evidence.id})
                if evidence.private_source != snapshot.private_source:
                    issues.append({"kind": "privacy_classification_mismatch", "evidence_id": evidence.id})
                if not self._evidence_current(evidence, store):
                    issues.append({"kind": "stale_phase4_review_or_provenance", "evidence_id": evidence.id})
                elif evidence.review_status == "approved":
                    if evidence.node_id: live_node_ids.add(evidence.node_id)
                    if evidence.relationship_id: live_edge_ids.add(evidence.relationship_id)
            except Exception:
                issues.append({"kind": "broken_source_reference", "evidence_id": evidence.id})
        supported_count = len(live_node_ids) + len(live_edge_ids)
        for node_id in accepted_node_ids - live_node_ids:
            issues.append({"kind": "accepted_node_without_current_approved_evidence", "node_id": node_id})
        for edge_id in accepted_edge_ids - live_edge_ids:
            issues.append({"kind": "accepted_edge_without_current_approved_evidence", "relationship_id": edge_id})
        aliases = await self.db.execute(select(KGNodeAlias).where(KGNodeAlias.owner_id == owner_id))
        for alias in aliases.scalars().all():
            node = await self.db.get(KGNode, alias.node_id)
            if node is None or node.node_type != alias.node_type or alias.identity_key != normalize_identity(alias.alias):
                issues.append({"kind": "invalid_alias", "alias_id": alias.id})
        alias_groups = await self.db.execute(select(KGNodeAlias.owner_id, KGNodeAlias.node_type,
            KGNodeAlias.identity_key, func.count()).where(KGNodeAlias.owner_id == owner_id,
            KGNodeAlias.status == "approved").group_by(KGNodeAlias.owner_id, KGNodeAlias.node_type,
            KGNodeAlias.identity_key).having(func.count() > 1))
        for _, node_type, key, count in alias_groups.all():
            issues.append({"kind": "duplicate_alias", "node_type": node_type, "identity_key": key, "count": int(count)})
        imports = await self.db.execute(select(KGImportRun).where(KGImportRun.owner_id == owner_id).order_by(KGImportRun.imported_at))
        import_history = [{"id": r.id, "document_id": r.document_id, "extraction_run_id": r.extraction_run_id,
                           "candidate_count": r.candidate_count, "status": r.status, "synthetic": r.synthetic}
                          for r in imports.scalars().all()]
        conflicts = await self._conflicts(owner_id)
        return {"node_counts_by_type": nodes, "edge_counts_by_type": edges, "evidence_count": int(evidence_count),
                "pending_candidates": int(pending), "approved_candidates": int(accepted),
                "rejected_candidates": int(rejected),
                "duplicate_identity_groups": duplicate_groups, "conflicts": conflicts,
                "integrity_issues": issues, "provenance_coverage": 1.0 if not assertion_count else round(supported_count / assertion_count, 4),
                "import_history": import_history}

    async def _conflicts(self, owner_id: str) -> list[dict[str, Any]]:
        supporting = aliased(KGRelationship)
        contradicting = aliased(KGRelationship)
        stmt = select(supporting.source_node_id, supporting.target_node_id, supporting.id, contradicting.id).where(
            supporting.owner_id == owner_id, contradicting.owner_id == owner_id,
            supporting.source_node_id == contradicting.source_node_id,
            supporting.target_node_id == contradicting.target_node_id,
            supporting.relationship_type == "SUPPORTS", contradicting.relationship_type == "CONTRADICTS",
            supporting.review_status == "approved", contradicting.review_status == "approved",
            supporting.assertion_status == "current", contradicting.assertion_status == "current")
        rows = await self.db.execute(stmt.order_by(supporting.source_node_id, supporting.target_node_id).limit(MAX_RESULTS))
        return [{"source_node_id": source, "target_node_id": target,
                 "relationship_ids": [supports_id, contradicts_id], "types": ["SUPPORTS", "CONTRADICTS"]}
                for source, target, supports_id, contradicts_id in rows.all()]

    async def stats(self, owner_id: str) -> dict[str, Any]:
        return await self.audit(owner_id)

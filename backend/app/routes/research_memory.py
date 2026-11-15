from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.models.research_memory import MemoryRecord, MemorySourceEvidence, MemoryAssociation, MemoryResearchGap, MemoryContradiction
from backend.app.models.knowledge_graph import KGGraphEvidence
from backend.app.schemas.research_memory import (
    MemoryAssociationReview, MemoryContradictionResolution, MemoryFeedbackRequest,
    MemoryFormationRequest, MemoryGapCreate, MemoryGapResolution, MemorySearchRequest,
    SessionMemoryCaptureRequest, SessionMemoryOptInRequest,
)
from backend.app.services.research_memory_service import MemoryValidationError, ResearchMemoryService

router = APIRouter(prefix="/research-memory", tags=["research-memory"])


def _dump(value):
    if hasattr(value, "__table__"):
        return {column.name: _dump(getattr(value, column.key)) for column in value.__table__.columns}
    if isinstance(value, dict): return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, list): return [_dump(v) for v in value]
    if hasattr(value, "isoformat"): return value.isoformat()
    return value


async def _run(db, awaitable, commit=False):
    try:
        result = await awaitable
        if commit: await db.commit()
        return _dump(result)
    except MemoryValidationError as exc:
        if commit: await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        if commit: await db.rollback()
        raise


@router.get("/status")
async def status(current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).status(current_user.id))


@router.post("/formation/preview")
async def formation_preview(payload: MemoryFormationRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).formation_preview(current_user.id, payload.node_ids,
        payload.relationship_ids, payload.allow_private))


@router.post("/formation")
async def form_memories(payload: MemoryFormationRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).form(current_user.id, payload.node_ids,
        payload.relationship_ids, payload.allow_private), commit=True)


@router.post("/search")
async def search_memories(payload: MemorySearchRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).search(current_user.id, payload.query, scope_id=payload.scope_id,
        document_ids=payload.document_ids, memory_types=payload.memory_types, limit=payload.limit))


@router.get("")
async def list_memories(current_user: CurrentUser, db: DBSession,
                        memory_type: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    stmt = select(MemoryRecord).where(MemoryRecord.owner_id == current_user.id)
    if memory_type: stmt = stmt.where(MemoryRecord.memory_type == memory_type.upper())
    rows = list((await db.scalars(stmt.order_by(MemoryRecord.updated_at.desc()).offset(offset).limit(limit))).all())
    return [_dump(row) for row in rows]


@router.get("/items/{memory_id}")
async def memory_detail(memory_id: str, current_user: CurrentUser, db: DBSession):
    memory = await db.scalar(select(MemoryRecord).where(MemoryRecord.id == memory_id, MemoryRecord.owner_id == current_user.id))
    if memory is None: raise HTTPException(status_code=404, detail="Memory not found")
    evidence = list((await db.scalars(select(MemorySourceEvidence).where(MemorySourceEvidence.memory_id == memory_id).order_by(MemorySourceEvidence.observed_at).limit(100))).all())
    graph = ResearchMemoryService(db).graph
    for item in evidence:
        ge = await db.get(KGGraphEvidence, item.graph_evidence_id) if item.graph_evidence_id else None
        if ge is None or not await graph._evidence_current_for_owner(current_user.id, ge):
            item.evidence_status = "STALE"
    links = list((await db.scalars(select(MemoryAssociation).where(MemoryAssociation.owner_id == current_user.id,
        (MemoryAssociation.source_memory_id == memory_id) | (MemoryAssociation.target_memory_id == memory_id)).limit(100))).all())
    return {"memory": _dump(memory), "sources": [_dump(e) for e in evidence], "associations": [_dump(a) for a in links]}


@router.get("/items/{memory_id}/neighborhood")
async def memory_neighborhood(memory_id: str, current_user: CurrentUser, db: DBSession,
                              depth: int = Query(2, ge=1, le=3)):
    return await _run(db, ResearchMemoryService(db).neighborhood(current_user.id, memory_id, depth))


@router.get("/items/{memory_id}/history")
async def memory_history(memory_id: str, current_user: CurrentUser, db: DBSession, limit: int = Query(100, ge=1, le=100)):
    return await _run(db, ResearchMemoryService(db).history(current_user.id, memory_id, limit))


@router.get("/associations/candidates")
async def association_candidates(current_user: CurrentUser, db: DBSession,
                                 status: str = "CANDIDATE", limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = await ResearchMemoryService(db).list_associations(current_user.id, status, limit, offset)
    return [{"association": _dump(row["association"]), "supporting_sources": row["supporting_sources"],
             "evidence_current": row["evidence_current"]} for row in rows]


@router.post("/associations/{association_id}/review")
async def association_review(association_id: str, payload: MemoryAssociationReview, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).review_association(current_user.id, association_id, payload.action, current_user.id), commit=True)


@router.get("/contradictions")
async def contradictions(current_user: CurrentUser, db: DBSession, status: str | None = None,
                        limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await _run(db, ResearchMemoryService(db).list_contradictions(current_user.id, status, limit, offset))


@router.post("/contradictions/{contradiction_id}/resolve")
async def contradiction_resolve(contradiction_id: str, payload: MemoryContradictionResolution, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).resolve_contradiction(current_user.id, contradiction_id,
        payload.outcome, payload.context, current_user.id), commit=True)


@router.get("/gaps")
async def gaps(current_user: CurrentUser, db: DBSession, status: str | None = "OPEN",
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    stmt = select(MemoryResearchGap).where(MemoryResearchGap.owner_id == current_user.id)
    if status: stmt = stmt.where(MemoryResearchGap.status == status.upper())
    return [_dump(r) for r in (await db.scalars(stmt.order_by(MemoryResearchGap.discovered_at.desc()).offset(offset).limit(limit))).all()]


@router.post("/gaps")
async def gap_create(payload: MemoryGapCreate, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).create_gap(current_user.id, payload.question, payload.gap_type.upper(),
        payload.scope, payload.reason, payload.inspected_sources, current_user.id), commit=True)


@router.post("/gaps/{gap_id}/resolve")
async def gap_resolve(gap_id: str, payload: MemoryGapResolution, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).resolve_gap(current_user.id, gap_id, payload.status.upper(),
        payload.resolution_memory_id, current_user.id), commit=True)


@router.post("/feedback")
async def feedback(payload: MemoryFeedbackRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).feedback(current_user.id, payload.target_type.upper(), payload.target_id,
        payload.action.upper(), payload.details, current_user.id), commit=True)


@router.post("/sessions/{conversation_id}/opt-in")
async def session_opt_in(conversation_id: str, payload: SessionMemoryOptInRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).set_session_opt_in(current_user.id, conversation_id, payload.enabled), commit=True)


@router.post("/sessions/{conversation_id}/capture")
async def session_capture(conversation_id: str, payload: SessionMemoryCaptureRequest, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).capture_session_observation(current_user.id, conversation_id,
        payload.query, payload.evidence_ids), commit=True)


@router.get("/sessions/memories")
async def session_memories(current_user: CurrentUser, db: DBSession, limit: int = Query(100, ge=1, le=100)):
    rows = list((await db.scalars(select(MemoryRecord).where(MemoryRecord.owner_id == current_user.id,
        MemoryRecord.privacy_classification == "SESSION").order_by(MemoryRecord.created_at.desc()).limit(limit))).all())
    return [_dump(r) for r in rows]


@router.delete("/sessions/memories/{memory_id}")
async def delete_session_memory(memory_id: str, current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).delete_session_memory(current_user.id, memory_id, current_user.id), commit=True)


@router.get("/audit")
async def audit(current_user: CurrentUser, db: DBSession):
    return await _run(db, ResearchMemoryService(db).audit(current_user.id))

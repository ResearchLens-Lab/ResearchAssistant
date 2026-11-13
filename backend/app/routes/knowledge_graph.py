from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.schemas.knowledge_graph import (
    AliasCreateRequest, CandidateReviewRequest, GraphImportConfirmRequest, GraphImportRequest, GraphRollbackRequest,
    IdentityDecisionRequest, MergeRequest, NodeCorrectionRequest, RelationshipCorrectionRequest,
    RelationshipCreateRequest, RelationshipStatusRequest, UndoMergeRequest,
)
from backend.app.services.knowledge_graph_service import GraphValidationError, KnowledgeGraphService

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


def _dump(value):
    if hasattr(value, "__table__"):
        return {column.name: _dump(getattr(value, column.key)) for column in value.__table__.columns}
    if isinstance(value, dict): return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, list): return [_dump(v) for v in value]
    if hasattr(value, "isoformat"): return value.isoformat()
    return value


async def _call(awaitable):
    try: return await awaitable
    except GraphValidationError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _mutate(db, awaitable):
    try:
        result = await awaitable
        await db.commit()
        return result
    except GraphValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await db.rollback()
        raise


def _service(db, user):
    return KnowledgeGraphService(db), user.id


@router.get("/status", summary="Read graph statistics and integrity audit")
async def graph_status(current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return await _call(service.audit(owner))


@router.post("/imports/dry-run", summary="Preview approved Phase 4 records for graph import")
async def import_dry_run(payload: GraphImportRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return await _call(service.import_plan(owner, payload.document_id, payload.extraction_run_id, payload.allow_private))


@router.post("/imports", summary="Explicitly import approved records into pending graph review")
async def import_records(payload: GraphImportConfirmRequest, current_user: CurrentUser, db: DBSession):
    if payload.confirm is not True: raise HTTPException(status_code=400, detail="confirm=true is required")
    service, owner = _service(db, current_user)
    return await _mutate(db, service.import_approved(owner, payload.document_id, payload.extraction_run_id, payload.allow_private))


@router.get("/imports", summary="List this user's graph import history")
async def import_history(current_user: CurrentUser, db: DBSession):
    return (await graph_status(current_user, db))["import_history"]


@router.post("/imports/{import_run_id}/rollback", summary="Roll back an unreviewed graph import")
async def rollback_import(import_run_id: str, payload: GraphRollbackRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return await _mutate(db, service.rollback_import(owner, import_run_id, current_user.id, payload.reason))


@router.get("/candidates", summary="List graph candidates awaiting review")
async def candidates(current_user: CurrentUser, db: DBSession,
                     status: str = Query("pending", pattern="^(pending|approved|rejected|rolled_back)$"),
                     limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
    service, owner = _service(db, current_user)
    rows = await service.list_candidates(owner, status, limit, offset, allow_private=True)
    return [_dump(row) for row in rows]


@router.get("/candidates/{candidate_id}", summary="Inspect an imported candidate with exact source evidence")
async def candidate(candidate_id: str, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    try: return _dump(await service.get_candidate(owner, candidate_id))
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/review", summary="Approve as a canonical node or reject a candidate")
async def review_candidate(candidate_id: str, payload: CandidateReviewRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return await _mutate(db, service.review_candidate(owner, candidate_id, payload.action.replace("-", "_"),
        current_user.id, payload.node_type, payload.canonical_name, payload.existing_node_id, payload.allow_private))


@router.post("/relationships", summary="Create an explicitly reviewed, evidence-backed directed relationship")
async def create_relationship(payload: RelationshipCreateRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.add_relationship(owner, payload.candidate_id, payload.source_node_id,
        payload.relationship_type, payload.target_node_id, current_user.id, payload.allow_private)))


@router.get("/nodes", summary="Search this user's canonical graph nodes")
async def search_nodes(current_user: CurrentUser, db: DBSession,
                       q: str = "", node_type: str | None = None, identifier: str | None = None,
                       limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    service, owner = _service(db, current_user)
    return [_dump(row) for row in await service.search_nodes(owner, q, node_type, identifier, limit, offset)]


@router.get("/nodes/{node_id}", summary="Read an owned canonical graph node")
async def node(node_id: str, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    try: return _dump(await service.node_detail(owner, node_id))
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/nodes/{node_id}", summary="Correct a canonical node with an audit event")
async def correct_node(node_id: str, payload: NodeCorrectionRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.correct_node(owner, node_id, payload.canonical_name,
        payload.node_type, current_user.id, payload.identifiers)))


@router.get("/nodes/{node_id}/evidence", summary="Read source evidence for an owned node")
async def node_evidence(node_id: str, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    try: return [_dump(row) for row in await service.node_evidence(owner, node_id, allow_private=True)]
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/relationships", summary="Read supported relationships and evidence")
async def node_relationships(node_id: str, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    try: return _dump(await service.node_relationships(owner, node_id, allow_private=True))
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/neighborhood", summary="Retrieve a bounded, provenance-aware neighborhood")
async def neighborhood(node_id: str, current_user: CurrentUser, db: DBSession,
                       depth: int = Query(1, ge=1, le=4), relationship_types: str | None = None,
                       node_types: str | None = None, limit: int = Query(100, ge=1, le=200)):
    service, owner = _service(db, current_user)
    rels = {v.strip().upper() for v in relationship_types.split(",")} if relationship_types else None
    types = {v.strip().upper() for v in node_types.split(",")} if node_types else None
    try: return _dump(await service.neighborhood(owner, node_id, depth, rels, types, limit, allow_private=True))
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/paths", summary="Find a bounded path between owned graph nodes")
async def graph_path(source_id: str, target_id: str, current_user: CurrentUser, db: DBSession,
                     max_depth: int = Query(4, ge=1, le=4), relationship_types: str | None = None,
                     node_types: str | None = None):
    service, owner = _service(db, current_user)
    rels = {v.strip().upper() for v in relationship_types.split(",")} if relationship_types else None
    types = {v.strip().upper() for v in node_types.split(",")} if node_types else None
    try: return _dump(await service.find_path(owner, source_id, target_id, max_depth, rels, allow_private=True, node_types=types))
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/identity-suggestions", summary="Suggest possible duplicates for human review")
async def identity_suggestions(node_id: str, current_user: CurrentUser, db: DBSession,
                               threshold: float = Query(.84, ge=.5, le=1)):
    service, owner = _service(db, current_user)
    try: return await service.identity_suggestions(owner, node_id, threshold)
    except GraphValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/nodes/{node_id}/aliases", summary="Add a manually approved alias")
async def add_alias(node_id: str, payload: AliasCreateRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.add_alias(owner, node_id, payload.alias, current_user.id)))


@router.post("/identity/reject-match", summary="Record an explicit duplicate-match rejection")
async def reject_match(payload: IdentityDecisionRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.reject_identity_suggestion(owner, payload.source_node_id,
        payload.target_node_id, current_user.id, payload.reason)))


@router.post("/identity/merge", summary="Explicitly merge nodes while preserving and snapshotting provenance")
async def merge_nodes(payload: MergeRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.merge_nodes(owner, payload.primary_node_id,
        payload.duplicate_node_id, current_user.id, payload.reason)))


@router.post("/identity/merge/{decision_id}/undo", summary="Undo an audited node merge")
async def undo_merge(decision_id: str, payload: UndoMergeRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.undo_merge(owner, decision_id, current_user.id, payload.reason)))


@router.patch("/relationships/{relationship_id}", summary="Correct relationship endpoints or type")
async def correct_relationship(relationship_id: str, payload: RelationshipCorrectionRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.correct_relationship(owner, relationship_id,
        payload.source_node_id, payload.relationship_type, payload.target_node_id, current_user.id)))


@router.patch("/relationships/{relationship_id}/status", summary="Mark an assertion current, disputed, superseded, or retracted")
async def relationship_status(relationship_id: str, payload: RelationshipStatusRequest, current_user: CurrentUser, db: DBSession):
    service, owner = _service(db, current_user)
    return _dump(await _mutate(db, service.set_relationship_status(owner, relationship_id,
        payload.status, current_user.id, payload.reason)))


@router.get("/history", summary="Read graph correction and identity decision history")
async def graph_history(current_user: CurrentUser, db: DBSession, target_id: str | None = None):
    from sqlalchemy import select
    from backend.app.models.knowledge_graph import KGReviewEvent
    stmt = select(KGReviewEvent).where(KGReviewEvent.owner_id == current_user.id)
    if target_id: stmt = stmt.where(KGReviewEvent.target_id == target_id)
    rows = await db.execute(stmt.order_by(KGReviewEvent.created_at, KGReviewEvent.id).limit(200))
    return [_dump(row) for row in rows.scalars().all()]

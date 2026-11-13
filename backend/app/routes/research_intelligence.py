from fastapi import APIRouter, HTTPException, Query

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.schemas.research_intelligence import (
    ClaimRequest, CompareRequest, EvidenceRequest, ExternalLookupRequest,
    QuestionRequest, QualityReviewRequest,
)
from backend.app.services.research_intelligence import ResearchIntelligenceError, ResearchIntelligenceService

router = APIRouter(prefix="/research-intelligence", tags=["research-intelligence"])


async def _call(awaitable):
    try:
        return await awaitable
    except ResearchIntelligenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/readiness")
async def readiness(current_user: CurrentUser, db: DBSession):
    # A cheap account-scoped count, not a corpus scan.
    from sqlalchemy import func, select
    from backend.app.models.document import Document
    from backend.app.models.paper import Paper
    count = await db.scalar(select(func.count(Document.id)).join(Paper, Paper.id == Document.paper_id).where(
        Paper.owner_id == current_user.id, Document.processing_status == "indexed"))
    return {"indexed_documents": count or 0, "external_lookup": "explicit_action_only",
        "phase1_local_retrieval": "available_when_local_index_exists", "llm_required": False}


@router.post("/questions/analyze")
async def analyze(payload: QuestionRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).analyze_question(current_user.id, payload.question))


@router.post("/evidence/synthesize")
async def synthesize(payload: EvidenceRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).synthesize(current_user.id, payload.question,
        payload.paper_ids or None, payload.document_ids or None, payload.result_limit))


@router.post("/claims/assess")
async def assess(payload: ClaimRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).assess_claim(current_user.id, payload.question,
        payload.paper_ids or None, payload.document_ids or None))


@router.post("/papers/compare")
async def compare(payload: CompareRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).compare(current_user.id, payload.paper_ids))


@router.post("/contradictions/analyze")
async def contradictions(current_user: CurrentUser, db: DBSession,
                         document_ids: list[str] | None = None, result_limit: int = Query(default=50, ge=1, le=100)):
    return await _call(ResearchIntelligenceService(db).analyze_contradictions(current_user.id, document_ids, result_limit))


@router.post("/papers/{paper_id}/verify-source")
async def verify_source(paper_id: str, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).verify_source(current_user.id, paper_id))


@router.post("/external/lookup")
async def external_lookup(payload: ExternalLookupRequest, current_user: CurrentUser, db: DBSession):
    if not payload.doi and not payload.title:
        raise HTTPException(status_code=422, detail="Provide a DOI or an explicitly approved public title query")
    return await _call(ResearchIntelligenceService(db).external_lookup(current_user.id,
        payload.doi, payload.title, payload.authors, payload.year))


@router.post("/gaps/analyze")
async def gaps(payload: EvidenceRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).gaps(current_user.id, payload.question,
        payload.paper_ids or None, payload.document_ids or None))


@router.post("/papers/{paper_id}/quality-review")
async def quality_review(paper_id: str, payload: QualityReviewRequest, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).quality_review(current_user.id, paper_id,
        payload.profile, payload.evidence_ids, str(current_user.id)))


@router.get("/runs")
async def list_runs(current_user: CurrentUser, db: DBSession,
                    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return await ResearchIntelligenceService(db).history(current_user.id, limit, offset)


@router.get("/runs/{run_id}")
async def inspect_run(run_id: str, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).inspect(current_user.id, run_id))


@router.get("/evidence/{evidence_id}")
async def inspect_evidence(evidence_id: str, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).inspect_evidence(current_user.id, evidence_id))


@router.get("/runs/{run_id}/evidence/{evidence_id}")
async def inspect_run_evidence(run_id: str, evidence_id: str, current_user: CurrentUser, db: DBSession):
    return await _call(ResearchIntelligenceService(db).inspect_run_evidence(current_user.id, run_id, evidence_id))

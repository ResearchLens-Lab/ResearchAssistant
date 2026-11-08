import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, func

from backend.app.core.config import get_settings
from backend.app.core.dependencies import DBSession
from backend.app.models.document import Document, DocumentStatus
from rag.config.settings import settings as rag_settings

logger = logging.getLogger("backend.health")

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}


@router.get("/health/ready", summary="Readiness probe (verifies the database)")
async def readiness(db: DBSession):
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("database readiness check failed")
        checks["database"] = "unavailable"

    payload = {
        "status": "ready" if all(v == "ok" for v in checks.values()) else "degraded",
        "checks": checks,
    }
    if payload["status"] != "ready":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/system/overview", summary="System overview and live RAG status")
async def system_overview(db: DBSession) -> dict:
    settings = get_settings()
    total_docs = 0
    completed_jobs = 0
    failed_jobs = 0
    total_chunks = 0
    try:
        total_docs_res = await db.execute(select(func.count(Document.id)))
        total_docs = total_docs_res.scalar() or 0

        completed_res = await db.execute(
            select(func.count(Document.id)).where(Document.processing_status == DocumentStatus.INDEXED.value)
        )
        completed_jobs = completed_res.scalar() or 0

        failed_res = await db.execute(
            select(func.count(Document.id)).where(Document.processing_status == DocumentStatus.FAILED.value)
        )
        failed_jobs = failed_res.scalar() or 0

        chunks_res = await db.execute(
            select(func.coalesce(func.sum(Document.chunk_count), 0))
        )
        total_chunks = chunks_res.scalar() or 0
    except Exception as exc:
        logger.warning("Could not query system document metrics: %s", exc)

    return {
        "status": "online",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "metrics": {
            "total_documents": total_docs,
            "completed_ingestion_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "total_indexed_chunks": total_chunks,
        },
        "rag": {
            "mode": getattr(settings, "rag_mode", "local"),
            "retrieval_mode": getattr(rag_settings, "retrieval_mode", "hybrid"),
            "embedding_provider": rag_settings.embedding_provider,
            "embedding_model": rag_settings.embedding_model,
            "embedding_dimension": rag_settings.embedding_dimension,
            "llm_enabled": getattr(rag_settings, "llm_enabled", False),
            "llm_provider": rag_settings.llm_provider,
            "llm_model": rag_settings.llm_model,
            "collection_name": rag_settings.chroma_collection_name,
        },
        "limits": {
            "max_upload_file_bytes": settings.max_upload_size_bytes,
            "max_upload_batch_bytes": settings.max_upload_batch_size_bytes,
            "max_upload_file_mb": settings.effective_max_upload_size_mb,
            "max_upload_batch_mb": settings.effective_max_upload_batch_size_mb,
        }
    }

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.core.config import get_settings
from backend.app.core.dependencies import DBSession

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

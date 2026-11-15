"""FastAPI application entrypoint.

Run from the repository root (so the in-process `rag` package resolves):

    uvicorn backend.app.main:app --reload
"""

import asyncio
import logging
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.middleware.error_handler import register_error_handlers
from backend.app.middleware.request_id import RequestIDMiddleware
from backend.app.routes import api_router, health_router


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().upload_path.mkdir(parents=True, exist_ok=True)
    try:
        from backend.app.database.base import Base
        from backend.app.database.session import get_engine
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logging.getLogger("backend").warning("Auto schema creation skipped/deferred: %s", exc)

    # Resume incomplete background ingestions from prior sessions upon application startup
    async def _resume_pending_ingestions():
        await asyncio.sleep(1.0)
        try:
            from pathlib import Path
            from sqlalchemy import select
            from backend.app.database.session import get_session_factory
            from backend.app.models.document import Document, DocumentStatus
            from backend.app.models.paper import Paper
            from backend.app.services.document_service import launch_background_ingest

            async with get_session_factory()() as db:
                result = await db.execute(
                    select(Document, Paper.owner_id)
                    .join(Paper, Document.paper_id == Paper.id)
                    .where(Document.processing_status == DocumentStatus.PROCESSING.value)
                )
                pending = result.all()
                for doc, owner_id in pending:
                    if Path(doc.storage_path).is_file():
                        logging.getLogger("backend").info("Resuming pending ingestion for document_id=%s", doc.id)
                        launch_background_ingest(doc.id, doc.paper_id, owner_id)
                    else:
                        doc.processing_status = DocumentStatus.FAILED.value
                        doc.processing_error = "Source file missing after application restart."
                        await db.commit()
        except Exception as exc:
            logging.getLogger("backend").warning("Pending ingestion resumption notice: %s", exc)

    asyncio.create_task(_resume_pending_ingestions())

    yield
    try:
        from backend.app.database.session import get_engine
        from sqlalchemy import text
        engine = get_engine()
        if str(engine.url).startswith("sqlite"):
            async with engine.begin() as conn:
                await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        await engine.dispose()
    except Exception as exc:
        logging.getLogger("backend").warning("Shutdown WAL checkpoint/engine cleanup notice: %s", exc)


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Backend API for ResearchAssistant: authentication, papers, "
            "document upload, grounded chat, and the integration boundaries "
            "for RAG and research intelligence."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Added after RequestID so CORS is the outermost layer.
    app.add_middleware(RequestIDMiddleware)
    # Compress larger JSON API payloads. GZipMiddleware leaves event streams
    # unbuffered, so incremental chat responses retain their timing.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def reject_oversized_upload_request(request: Request, call_next):
        if settings.desktop_runtime:
            expected_origin = settings.desktop_ui_origin
            supplied_origin = request.headers.get("origin", "")
            host_name = request.url.hostname
            remote_host = request.client.host if request.client else ""
            if (
                not settings.desktop_request_key
                or host_name != "127.0.0.1"
                or remote_host not in ("127.0.0.1", "::1")
                or (supplied_origin and supplied_origin != expected_origin)
            ):
                return JSONResponse(status_code=403, content={"detail": "Desktop request origin rejected."})
            if request.method != "OPTIONS" and not hmac.compare_digest(
                request.headers.get("x-researchlens-desktop-key", ""),
                settings.desktop_request_key,
            ):
                return JSONResponse(status_code=401, content={"detail": "Desktop request key required."})
            # The showcase build is strictly offline. These API actions contact
            # public scholarly registries, so reject them even if called directly.
            if request.url.path.startswith((
                "/api/v1/research-intelligence/external",
                "/api/v1/research-intelligence/verify",
            )):
                return JSONResponse(status_code=403, content={"detail": "External scholarly lookup is disabled in this desktop build."})

        if request.method == "POST" and request.url.path.endswith(("/documents/upload", "/documents/upload/batch")):
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit():
                # Allow multipart headers and boundaries around the configured file payload.
                request_limit = settings.max_upload_batch_size_bytes + 2 * 1024 * 1024
                if int(content_length) > request_limit:
                    return JSONResponse(
                        status_code=413,
                        content={"error": {"code": "UPLOAD_TOO_LARGE", "message": f"Upload request exceeds the {settings.max_upload_batch_size_mb} MB total batch limit."}},
                    )
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()

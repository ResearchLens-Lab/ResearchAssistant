"""FastAPI application entrypoint.

Run from the repository root (so the in-process `rag` package resolves):

    uvicorn backend.app.main:app --reload
"""

import logging
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
    yield


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

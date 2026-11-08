"""Route registration. All application APIs are versioned under /api/v1."""

from fastapi import APIRouter

from backend.app.routes import (
    auth,
    chat,
    documents,
    health,
    papers,
    research,
    search,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(papers.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(search.router)
api_router.include_router(research.router)
api_router.include_router(health.router)

health_router = health.router

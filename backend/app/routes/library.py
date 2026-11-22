"""Library and index management routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from backend.app.core.dependencies import CurrentUser
from backend.app.services.library_service import LibraryService

router = APIRouter(prefix="/library", tags=["library"])


class ReindexResponse(BaseModel):
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


@router.post("/reindex", response_model=ReindexResponse, summary="Rebuild library search index")
async def trigger_reindex(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
):
    current_status = LibraryService.get_status()
    if current_status.get("status") == "running":
        return ReindexResponse(
            status="running",
            message="Reindexing is already in progress",
            details=current_status,
        )

    service = LibraryService()
    # Trigger background async task
    background_tasks.add_task(service.execute_reindex_async)

    return ReindexResponse(
        status="running",
        message="Library reindex initiated",
        details=LibraryService.get_status(),
    )


@router.get("/reindex/status", response_model=Dict[str, Any], summary="Get reindex progress")
async def get_reindex_status(current_user: CurrentUser):
    return LibraryService.get_status()

"""Helper functions for document lifecycle management - Milestone 1."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document, DocumentWorkerLease, DocumentStatus, CleanupStatus, OperationType

logger = logging.getLogger("backend.documents")


def compute_file_hash_streaming(file_path: Path) -> str:
    """Compute SHA-256 hash without loading entire file into memory."""
    hasher = hashlib.sha256()
    with file_path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


async def find_existing_document_by_hash(
    db: AsyncSession, 
    paper_id: str, 
    file_hash: str, 
    file_size: int
) -> Optional[Document]:
    """Find existing document with same hash in same paper."""
    result = await db.execute(
        select(Document)
        .where(
            and_(
                Document.paper_id == paper_id,
                Document.file_hash_sha256 == file_hash,
                Document.file_size == file_size
            )
        )
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def check_duplicate_and_classify(
    db: AsyncSession,
    paper_id: str,
    file_hash: str,
    file_size: int
) -> Tuple[Optional[Document], str, Optional[str]]:
    """
    Check for duplicate and return (document, outcome, message).
    
    Outcomes:
    - stored_new: No duplicate, proceed with new upload
    - already_indexed: Document already successfully indexed
    - existing_job: Active processing job exists
    - retry_available: Previous failed/cancelled, safe to retry
    - cleanup_in_progress: Cleanup still running
    - cleanup_failed: Cleanup failed, needs resolution
    """
    existing = await find_existing_document_by_hash(db, paper_id, file_hash, file_size)
    
    if not existing:
        return None, "stored_new", None
    
    status = existing.processing_status
    
    # Already indexed successfully
    if status in [DocumentStatus.INDEXED.value, DocumentStatus.PARTIAL.value, DocumentStatus.NEEDS_REVIEW.value]:
        return existing, "already_indexed", "This file is already indexed in this project."
    
    # Currently processing or queued
    if status in [DocumentStatus.QUEUED.value, DocumentStatus.PROCESSING.value, 
                  DocumentStatus.EXTRACTING.value, DocumentStatus.OCR_PROCESSING.value,
                  DocumentStatus.STRUCTURING.value, DocumentStatus.CHUNKING.value, 
                  DocumentStatus.INDEXING.value]:
        # Check if there's an active worker lease
        has_active_lease = await has_active_worker_lease(db, existing.id)
        if has_active_lease:
            return existing, "existing_job", f"This file is currently being processed (job {existing.id})."
        else:
            # Stale processing status without active lease - safe to retry
            return existing, "retry_available", "Previous job appears stale. Retry is available."
    
    # Cancellation in progress
    if status in [DocumentStatus.CANCEL_REQUESTED.value, DocumentStatus.CANCELLING_CLEANUP.value]:
        return existing, "cleanup_in_progress", "Cancellation cleanup is in progress. Please wait."
    
    # Failed or cancelled - check cleanup status
    if status in [DocumentStatus.FAILED.value, DocumentStatus.CANCELLED.value]:
        if existing.cleanup_status == CleanupStatus.FAILED.value:
            return existing, "cleanup_failed", "Previous cleanup failed. Manual resolution required."
        
        # Check if worker lease is still active (shouldn't be, but safety check)
        has_active_lease = await has_active_worker_lease(db, existing.id)
        if has_active_lease:
            return existing, "cleanup_in_progress", "Worker cleanup is still in progress."
        
        return existing, "retry_available", f"Previous attempt {status}. Retry is available."
    
    # Unknown status - treat as retry available
    return existing, "retry_available", f"Document status: {status}. Retry available."


async def has_active_worker_lease(db: AsyncSession, document_id: str) -> bool:
    """Check if document has an active worker lease."""
    result = await db.execute(
        select(DocumentWorkerLease)
        .where(
            and_(
                DocumentWorkerLease.document_id == document_id,
                DocumentWorkerLease.status == "active"
            )
        )
        .order_by(DocumentWorkerLease.started_at.desc())
        .limit(1)
    )
    lease = result.scalars().first()
    
    if not lease:
        return False
    
    # Check if lease is stale (no heartbeat for 5 minutes)
    heartbeat = getattr(lease, "heartbeat_at", None)
    if heartbeat and isinstance(heartbeat, datetime):
        age = datetime.utcnow() - heartbeat
        if age > timedelta(minutes=5):
            logger.warning(
                "Stale worker lease detected document_id=%s lease_id=%s age_minutes=%.1f",
                document_id, getattr(lease, "id", "unknown"), age.total_seconds() / 60
            )
            # Mark as abandoned but don't auto-release yet - let retry flow handle it
            return False
    
    return True


async def acquire_worker_lease(
    db: AsyncSession,
    document_id: str,
    worker_id: Optional[str] = None
) -> DocumentWorkerLease:
    """Acquire exclusive worker lease for document."""
    if not worker_id:
        worker_id = f"worker-{uuid.uuid4().hex[:12]}"
    
    now = datetime.utcnow()
    lease = DocumentWorkerLease(
        document_id=document_id,
        worker_id=worker_id,
        status="active",
        started_at=now,
        heartbeat_at=now
    )
    db.add(lease)
    await db.commit()
    await db.refresh(lease)
    
    logger.info(
        "Worker lease acquired document_id=%s lease_id=%s worker_id=%s",
        document_id, lease.id, worker_id
    )
    
    return lease


async def release_worker_lease(
    db: AsyncSession,
    lease_id: str
) -> None:
    """Release worker lease."""
    result = await db.execute(
        select(DocumentWorkerLease).where(DocumentWorkerLease.id == lease_id)
    )
    lease = result.scalars().first()
    
    if lease and lease.status == "active":
        lease.status = "released"
        lease.released_at = datetime.utcnow()
        await db.commit()
        logger.info(
            "Worker lease released document_id=%s lease_id=%s worker_id=%s",
            lease.document_id, lease_id, lease.worker_id
        )


async def update_worker_heartbeat(
    db: AsyncSession,
    lease_id: str
) -> None:
    """Update worker lease heartbeat."""
    result = await db.execute(
        select(DocumentWorkerLease).where(DocumentWorkerLease.id == lease_id)
    )
    lease = result.scalars().first()
    
    if lease and lease.status == "active":
        lease.heartbeat_at = datetime.utcnow()
        await db.commit()

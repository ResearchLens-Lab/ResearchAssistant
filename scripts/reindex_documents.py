"""Safely re-embed explicitly selected stored documents into the active collection.

Dry-run is the default. Applying requires ``--apply`` and either one or more
``--document-id`` values or the explicit ``--all`` selector. Interrupted
processing rows are excluded unless ``--resume-stale`` is supplied; that option
only selects rows whose heartbeat is older than the configured stale interval.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select

from backend.app.database.session import get_session_factory
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.paper import Paper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--document-id", action="append", dest="document_ids", help="Select one document (repeatable).")
    selection.add_argument("--all", action="store_true", help="Select every indexed or failed document. Review dry-run before applying.")
    parser.add_argument("--resume-stale", action="store_true", help="Also select stale processing rows (requires --all or --document-id).")
    parser.add_argument("--stale-after-seconds", type=int, default=900, help="Heartbeat age required for --resume-stale (default: 900).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Perform reindexing. Without this flag, only print the selected rows.")
    mode.add_argument("--dry-run", action="store_true", help="Explicitly list the selected rows without changing database or index data (default).")
    return parser


def build_selection(document_ids: list[str] | None, include_all: bool, resume_stale: bool,
                    stale_after_seconds: int, now: datetime | None = None):
    """Return a SQL predicate and cutoff for a caller-selected, bounded scope."""
    if stale_after_seconds < 60:
        raise ValueError("stale-after-seconds must be at least 60.")
    statuses = [DocumentStatus.INDEXED.value, DocumentStatus.FAILED.value, DocumentStatus.PARTIAL.value]
    if resume_stale:
        statuses.append(DocumentStatus.PROCESSING.value)
    clauses = []
    if document_ids:
        clauses.append(Document.id.in_(list(dict.fromkeys(document_ids))))
    if include_all:
        clauses.append(Document.processing_status.in_(statuses))
    if resume_stale:
        cutoff = (now or datetime.utcnow()) - timedelta(seconds=stale_after_seconds)
        stale = or_(Document.processing_heartbeat_at <= cutoff,
                    Document.processing_heartbeat_at.is_(None) & (Document.updated_at <= cutoff))
        clauses.append(or_(Document.processing_status != DocumentStatus.PROCESSING.value, stale))
    else:
        cutoff = None
        clauses.append(Document.processing_status.in_(statuses))
    return clauses, cutoff


async def reindex_documents(document_ids: list[str] | None, include_all: bool,
                            resume_stale: bool = False, stale_after_seconds: int = 900,
                            apply: bool = False) -> tuple[int, int]:
    session_factory = get_session_factory()
    clauses, cutoff = build_selection(document_ids, include_all, resume_stale, stale_after_seconds)
    rag = RAGGateway() if apply else None
    async with session_factory() as session:
        rows = await session.execute(
            select(Document, Paper)
            .join(Paper, Document.paper_id == Paper.id)
            .where(*clauses)
            .order_by(Document.created_at, Document.id)
        )
        items = list(rows.all())

    if not apply:
        mode = "dry-run"
        print(f"{mode}: {len(items)} document(s) selected; no database or index changes made.")
        for document, _paper in items:
            print(f"{document.id}\t{document.processing_status}\t{document.filename}")
        return 0, 0

    succeeded = failed = 0
    loop = asyncio.get_running_loop()
    for detached_document, paper in items:
        async with session_factory() as session:
            row = await session.execute(
                select(Document).where(Document.id == detached_document.id).with_for_update()
            )
            document = row.scalar_one_or_none()
            if document is None:
                continue
            if document.processing_status == DocumentStatus.PROCESSING.value:
                cutoff_now = datetime.utcnow() - timedelta(seconds=stale_after_seconds)
                heartbeat = document.processing_heartbeat_at or document.updated_at
                if not resume_stale or (heartbeat and heartbeat > cutoff_now):
                    print(f"Skipped active processing document: {document.id}")
                    continue
            elif document.processing_status not in {DocumentStatus.INDEXED.value, DocumentStatus.FAILED.value, DocumentStatus.PARTIAL.value}:
                print(f"Skipped ineligible document: {document.id}")
                continue
            if not Path(document.storage_path).is_file():
                document.processing_status = DocumentStatus.FAILED.value
                document.processing_stage = "failed"
                document.processing_error = "Stored original source file is missing; reindex was not started."
                failed += 1
                await session.commit()
                print(f"{document.filename}: failed (stored original file missing)")
                continue

            document.processing_status = DocumentStatus.PROCESSING.value
            document.processing_stage = "extracting_text"
            document.processing_started_at = datetime.utcnow()
            document.processing_heartbeat_at = document.processing_started_at
            document.processing_error = None
            # The prior count describes the old index and must not survive a
            # reindex attempt that clears or replaces those records.
            document.chunk_count = 0
            await session.commit()

            async def persist_stage(stage: str) -> None:
                current = await session.get(Document, document.id)
                if current and current.processing_status == DocumentStatus.PROCESSING.value:
                    current.processing_stage = stage
                    current.processing_heartbeat_at = datetime.utcnow()
                    await session.commit()

            def progress_callback(event: dict) -> None:
                stage = str(event.get("stage", ""))
                if stage:
                    asyncio.run_coroutine_threadsafe(persist_stage(stage), loop).result(timeout=15)

            metadata = {
                "document_id": document.id,
                "filename": document.filename,
                "title": paper.title,
                "authors": ", ".join(paper.authors or []),
                "year": paper.publication_year,
                "owner_id": paper.owner_id,
            }
            try:
                result = await rag.ingest_document(
                    file_path=document.storage_path,
                    paper_id=document.paper_id,
                    metadata=metadata,
                    progress_callback=progress_callback,
                )
                reported_count = int(result.get("chunk_count") or 0)
                index_state = await rag.get_document_index_counts(document.id)
                if index_state.get("storage_mode") == "sqlite_fts5_only":
                    consistent = (
                        index_state.get("ids_match") is True
                        and index_state.get("fts_count") == reported_count
                    )
                else:
                    consistent = (
                        index_state.get("ids_match") is True
                        and index_state.get("chroma_count") == reported_count
                        and index_state.get("fts_count") == reported_count
                    )
                reported_status = str(result.get("status") or "")
                if result.get("success") and reported_status in {"indexed", "partial", "needs_review"} and reported_count > 0 and consistent:
                    document.processing_status = DocumentStatus.INDEXED.value if reported_status == "indexed" else (DocumentStatus.PARTIAL.value if reported_status == "partial" else DocumentStatus.NEEDS_REVIEW.value)
                    document.processing_stage = "ready"
                    document.chunk_count = reported_count
                    document.processing_error = None
                    succeeded += 1
                else:
                    failure_message = str(result.get("error") or "Re-indexing did not complete.")
                    if result.get("success") and reported_status in {"indexed", "partial", "needs_review"}:
                        failure_message = (
                            "Re-indexing completed but stored indexes are inconsistent: "
                            f"reported={reported_count}, Chroma={index_state.get('chroma_count')}, "
                            f"FTS5={index_state.get('fts_count')}, ids_match={index_state.get('ids_match')}."
                        )
                    # A failed attempt must not leave stale/searchable partial
                    # entries in the active namespace. Verify cleanup before
                    # recording the failed terminal state.
                    try:
                        await rag.delete_document_chunks(document.id)
                        cleaned = await rag.get_document_index_counts(document.id)
                    except Exception as cleanup_exc:
                        cleaned = {}
                        failure_message += (
                            f" Index cleanup failed ({type(cleanup_exc).__name__}): "
                            f"{str(cleanup_exc).replace(document.storage_path, document.filename)}"
                        )
                    document.processing_status = DocumentStatus.FAILED.value
                    document.processing_stage = "failed"
                    document.chunk_count = 0
                    if cleaned and (cleaned.get("chroma_count") != 0 or cleaned.get("fts_count") != 0 or cleaned.get("ids_match") is not True):
                        failure_message += (
                            " Index cleanup could not be verified: "
                            f"Chroma={cleaned.get('chroma_count')}, FTS5={cleaned.get('fts_count')}, "
                            f"ids_match={cleaned.get('ids_match')}."
                        )
                    document.processing_error = failure_message.replace(document.storage_path, document.filename)
                    failed += 1
            except Exception as exc:
                document.processing_status = DocumentStatus.FAILED.value
                document.processing_stage = "failed"
                document.chunk_count = 0
                failure_message = str(exc).replace(document.storage_path, document.filename)
                try:
                    await rag.delete_document_chunks(document.id)
                    cleaned = await rag.get_document_index_counts(document.id)
                    if cleaned.get("chroma_count") != 0 or cleaned.get("fts_count") != 0 or cleaned.get("ids_match") is not True:
                        failure_message += (
                            " Index cleanup could not be verified: "
                            f"Chroma={cleaned.get('chroma_count')}, FTS5={cleaned.get('fts_count')}, "
                            f"ids_match={cleaned.get('ids_match')}."
                        )
                except Exception as cleanup_exc:
                    failure_message += (
                        f" Index cleanup failed ({type(cleanup_exc).__name__}): "
                        f"{str(cleanup_exc).replace(document.storage_path, document.filename)}"
                    )
                document.processing_error = failure_message
                failed += 1
            await session.commit()
            print(f"{document.filename}: {document.processing_status}")

    return succeeded, failed


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    if args.stale_after_seconds < 60:
        parser.error("--stale-after-seconds must be at least 60.")
    logging.basicConfig(level=logging.INFO)
    success_count, failure_count = asyncio.run(reindex_documents(
        document_ids=args.document_ids,
        include_all=args.all,
        resume_stale=args.resume_stale,
        stale_after_seconds=args.stale_after_seconds,
        apply=args.apply,
    ))
    if args.apply:
        print(f"Re-indexing complete: {success_count} ready, {failure_count} failed.")

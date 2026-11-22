# Deferred annotations: the `list` method below must not shadow builtin
# `list` in signature annotations.
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import DocumentNotFoundError, PaperNotFoundError, RequestValidationAppError
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.paper import Paper, ComparisonRecord
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.user import User
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.repositories.paper_repository import PaperRepository
from backend.app.schemas.paper import PaperCompareRequest, PaperCreate, PaperUpdate
from backend.app.utils.pagination import PageParams, page_payload

logger = logging.getLogger("backend.papers")


def get_personal_research_dir(paper_title: str = "") -> Path:
    base = Path.home() / "Documents" / "Personal Research"
    if paper_title:
        clean_name = re.sub(r'[<>:"/\\|?*]', "_", paper_title).strip() or "Untitled Project"
        folder = base / clean_name
    else:
        folder = base
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class PaperService:
    def __init__(self, db: AsyncSession, rag: Optional[RAGGateway] = None):
        self.db = db
        self.papers = PaperRepository(db)
        self.rag = rag

    async def create(self, user: User, payload: PaperCreate) -> Paper:
        paper = await self.papers.create(owner_id=user.id, data=payload.model_dump())
        await self.db.commit()
        logger.info("paper created paper_id=%s user_id=%s", paper.id, user.id)
        return paper

    async def get_owned(self, user: User, paper_id: str) -> Paper:
        """Ownership is enforced on every paper lookup; papers belonging to
        other users are indistinguishable from missing ones (no UUID probing)."""
        paper = await self.papers.get_by_id(paper_id)
        if paper is None or paper.owner_id != user.id:
            raise PaperNotFoundError()
        return paper

    async def open_folder(self, user: User, paper_id: str) -> dict[str, str]:
        paper = await self.get_owned(user, paper_id)
        folder = get_personal_research_dir(paper.title)

        result = await self.db.execute(select(Document).where(Document.paper_id == paper.id))
        docs = result.scalars().all()
        for doc in docs:
            if doc.storage_path and Path(doc.storage_path).is_file():
                dest = folder / doc.filename
                if not dest.exists():
                    try:
                        shutil.copy2(doc.storage_path, dest)
                    except Exception as copy_err:
                        logger.debug("Failed copying doc to project folder: %s", copy_err)

        from backend.app.services.document_service import DocumentService
        doc_service = DocumentService(self.db, self.rag)
        await doc_service.scan_and_ingest_local_folder(user, paper, folder)

        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            logger.warning("Could not open folder %s: %s", folder, e)

        return {"folder_path": str(folder), "status": "opened"}

    async def export_summary(self, user: User, paper_id: str) -> dict[str, Any]:
        paper = await self.get_owned(user, paper_id)
        folder = get_personal_research_dir(paper.title)

        summary = paper.summary_json
        if not summary or not summary.get("answer"):
            summary = await self.summarize(user, paper_id)

        clean_name = re.sub(r'[<>:"/\\|?*]', '_', paper.title).strip() or f"Project_{paper.id[:8]}"
        filename = f"Grounded Summary - {clean_name}.md"
        dest_path = folder / filename
        tmp_path = folder / f".{filename}.tmp"

        sources = summary.get("sources", [])
        answer = summary.get("answer", "")
        exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        content_lines = [
            "<!-- researchlens:generated-summary version=1.0 -->",
            f"# Grounded Research Summary: {paper.title}",
            "",
            f"- **Project:** {paper.title}",
            f"- **Exported:** {exported_at}",
            f"- **Total Citations:** {len(sources)}",
            "",
            "---",
            "",
            "## Summary Synthesis",
            "",
            answer,
            "",
            "---",
            "",
            "## Evidence & Citations Audit Trail",
            "",
        ]

        if not sources:
            content_lines.append("*No citations attached to this summary.*")
        else:
            for s in sources:
                sid = s.get("source_id") or s.get("citation_key") or "S?"
                sec = s.get("section") or "Section"
                fn = s.get("filename") or s.get("title") or "Source Document"
                loc = s.get("locator") or f"Page {s.get('page', 1)}"
                txt = (s.get("text") or s.get("quote") or "").strip()

                content_lines.extend([
                    f"### [{sid}] {sec}",
                    f"- **Document:** {fn}",
                    f"- **Locator:** {loc}",
                    f"- **Passage Excerpt:**",
                    f"> \"{txt}\"",
                    "",
                ])

        content = "\n".join(content_lines).strip() + "\n"

        # Atomic write
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(dest_path)

        logger.info("Exported summary for paper_id=%s to %s", paper_id, dest_path)
        return {
            "status": "success",
            "filename": filename,
            "path": str(dest_path),
            "folder": str(folder),
        }

    async def list(self, user: User, params: PageParams) -> dict[str, Any]:
        items, total = await self.papers.list_by_owner(
            user.id, params.offset, params.page_size
        )
        return page_payload(items, total, params)

    async def search(
        self,
        user: User,
        q: Optional[str],
        author: Optional[str],
        year: Optional[int],
        params: PageParams,
    ) -> dict[str, Any]:
        items, total = await self.papers.search(
            user.id, q, author, year, params.offset, params.page_size
        )
        return page_payload(items, total, params)

    async def update(self, user: User, paper_id: str, payload: PaperUpdate) -> Paper:
        paper = await self.get_owned(user, paper_id)
        paper = await self.papers.update(paper, payload.model_dump(exclude_unset=True))
        await self.db.commit()
        return paper

    async def delete(self, user: User, paper_id: str) -> None:
        paper = await self.get_owned(user, paper_id)
        documents = await DocumentRepository(self.db).list_by_paper(paper.id)
        storage_paths = [doc.storage_path for doc in documents if doc.storage_path]
        # Do not remove the DB row or original files when index cleanup fails.
        # RAGClient also rejects deletion while a local ingestion is active.
        if self.rag is not None:
            await self.rag.delete_paper(paper_id)
        await self.papers.delete(paper)
        await self.db.commit()

        # Originals are removed only after vector/lexical cleanup and DB delete.
        for path in storage_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                logger.warning("could not remove stored paper file")

    async def validate_owned_papers(
        self, user: User, paper_ids: list[str]
    ) -> list[Paper]:
        return [
            await self.get_owned(user, paper_id)
            for paper_id in dict.fromkeys(paper_ids)
        ]

    async def summarize(self, user: User, paper_id: str) -> dict[str, Any]:
        """
        Generate paper summary with authenticated user context.
        
        SEC-001: user_id is passed to ensure only owned papers can be summarized.
        Ownership is already validated via get_owned(), but RAG layer also enforces
        isolation to prevent any vector/lexical leaks.
        """
        paper = await self.get_owned(user, paper_id)
        try:
            result = await self.rag.summarize_paper(
                paper_id=paper_id,
                user_id=str(user.id),  # SEC-001: Pass authenticated user ID
            )
            summary_payload = {
                "paper_id": paper_id,
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_stale": False,
            }
        except Exception as exc:
            logger.warning("RAG gateway summarize_paper failed; using deterministic summarizer fallback: %s", exc)
            from rag.intelligence.summarizer import build_paper_summary
            from rag.citations.citation_mapper import SourceCitation
            summary_dict = build_paper_summary(paper_id=paper_id, user_id=str(user.id))
            sources = []
            for s in summary_dict.get("sources", []):
                sources.append({
                    "source_id": s.get("source_id", ""),
                    "paper_id": paper_id,
                    "document_id": s.get("document_id", paper_id),
                    "chunk_id": s.get("chunk_id", ""),
                    "page_start": s.get("page", 1),
                    "page_end": s.get("page", 1),
                    "locator": s.get("locator", f"p. {s.get('page', 1)}"),
                    "section": s.get("section", "Main Content"),
                    "text": s.get("text", ""),
                    "title": s.get("title", ""),
                    "filename": s.get("filename", ""),
                    "paper_title": s.get("title", ""),
                    "citation_label": f"[{s.get('source_id', '')}]",
                })
            summary_payload = {
                "paper_id": paper_id,
                "answer": summary_dict.get("answer", ""),
                "sources": sources,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_stale": False,
            }

        paper.summary_json = summary_payload
        await self.db.commit()
        return summary_payload

    async def compare(self, user: User, payload: PaperCompareRequest) -> dict[str, Any]:
        """
        Compare multiple papers with authenticated user context.
        
        SEC-001: user_id is passed to ensure only owned papers can be compared.
        Ownership is validated for all paper_ids, and RAG layer enforces vector/lexical
        isolation to prevent cross-user data leaks.
        """
        document_ids = list(dict.fromkeys(payload.document_ids or []))
        document_labels = {}
        if document_ids:
            rows = await self.db.execute(
                select(Document, Paper)
                .join(Paper, Paper.id == Document.paper_id)
                .where(Document.id.in_(document_ids), Paper.owner_id == user.id)
            )
            document_rows = list(rows.all())
            if {document.id for document, _paper in document_rows} != set(document_ids):
                raise DocumentNotFoundError()
            if any(
                document.processing_status != DocumentStatus.INDEXED.value
                and not (document.processing_status in (DocumentStatus.NEEDS_REVIEW.value, DocumentStatus.PARTIAL.value) and (document.chunk_count or 0) > 0)
                for document, _paper in document_rows
            ):
                raise RequestValidationAppError("Every selected source must be indexed before it can be compared.")
            paper_ids = list(dict.fromkeys(paper.id for _document, paper in document_rows))
            documents_by_id = {document.id: (document, paper) for document, paper in document_rows}
            document_labels = {
                document_id: f"{documents_by_id[document_id][1].title} · {documents_by_id[document_id][0].filename}"
                for document_id in document_ids
            }
        else:
            # Keep the old project-scoped request shape working for existing clients.
            # The current Compare & Reports UI always sends individual document IDs.
            papers = await self.validate_owned_papers(user, payload.paper_ids or [])
            paper_ids = [paper.id for paper in papers]
            documents_by_id = {}

        compare_kwargs = {}
        if document_ids:
            compare_kwargs = {
                "document_ids": document_ids,
                "document_labels": document_labels,
                "output_format": payload.output_format,
            }
        result = await self.rag.compare_papers(
            paper_ids=paper_ids,
            user_id=str(user.id),  # SEC-001: Pass authenticated user ID
            focus_area=payload.focus_area,
            **compare_kwargs,
        )
        metadata = result.get("metadata", {}) or {}
        if document_ids:
            contributed_ids = {source.get("document_id") for source in result.get("sources", []) if source.get("document_id")}
            metadata["comparison_scope"] = [
                {
                    "document_id": document_id,
                    "paper_id": documents_by_id[document_id][1].id,
                    "project_title": documents_by_id[document_id][1].title,
                    "filename": documents_by_id[document_id][0].filename,
                    "authors": documents_by_id[document_id][1].authors or [],
                    "publication_year": documents_by_id[document_id][1].publication_year,
                    "contributed_evidence": document_id in contributed_ids,
                    "coverage": "evidence found" if document_id in contributed_ids else "no relevant passage retrieved",
                }
                for document_id in document_ids
            ]

        final_response = {
            "paper_ids": paper_ids,
            "document_ids": document_ids,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "metadata": metadata,
        }

        # Persist user-scoped comparison record
        try:
            record = ComparisonRecord(
                owner_id=user.id,
                focus_area=payload.focus_area,
                output_format=payload.output_format or "table",
                document_ids=document_ids,
                paper_ids=paper_ids,
                result_json=final_response,
            )
            self.db.add(record)
            await self.db.commit()
            final_response["comparison_id"] = record.id
        except Exception as exc:
            logger.warning("Could not persist comparison record: %s", exc)
            await self.db.rollback()

        return final_response

    async def list_comparison_history(self, user: User, limit: int = 20) -> list[dict]:
        stmt = (
            select(ComparisonRecord)
            .where(ComparisonRecord.owner_id == user.id)
            .order_by(ComparisonRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "focus_area": r.focus_area,
                "output_format": r.output_format,
                "document_ids": r.document_ids or [],
                "paper_ids": r.paper_ids or [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "result": r.result_json,
            }
            for r in records
        ]

    async def get_comparison_history(self, user: User, comparison_id: str) -> dict:
        stmt = select(ComparisonRecord).where(
            ComparisonRecord.id == comparison_id,
            ComparisonRecord.owner_id == user.id,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise RequestValidationAppError("Comparison history entry not found.")
        return {
            "id": record.id,
            "focus_area": record.focus_area,
            "output_format": record.output_format,
            "document_ids": record.document_ids or [],
            "paper_ids": record.paper_ids or [],
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "result": record.result_json,
        }

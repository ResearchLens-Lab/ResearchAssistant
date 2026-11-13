"""
Citation formatter and high-level RAGResult data container.
Produces standardized JSON responses for FastAPI backend / Next.js frontend
and clean markdown tables for CLI / debugging.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from rag.citations.citation_mapper import SourceCitation


class RAGResult(BaseModel):
    """
    Standard result returned by the RAG query pipeline.
    """
    answer: str = Field(..., description="Grounded, evidence-backed answer")
    sources: List[SourceCitation] = Field(default_factory=list, description="Verified supporting sources")
    paper_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Converts result into backend/frontend API contract schema with full citation provenance.
        """
        return {
            "answer": self.answer,
            "sources": [
                {
                    "source_id": s.source_id,
                    "paper_id": s.paper_id,
                    "document_id": s.document_id,
                    "chunk_id": s.chunk_id,
                    "page": s.page_start,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "section": s.section,
                    "text": s.text,
                    "score": s.score,
                    "title": s.title,
                    "filename": s.filename,
                    "locator": s.locator,
                    "citation_label": s.citation_label,
                    "author_metadata": s.author_metadata,
                    "paper_title": s.paper_title or s.title,
                    "publication_year": s.publication_year,
                    "original_page_number": s.original_page_number or s.page_start,
                    "section_label": s.section_label or s.section,
                    "evidence_excerpt": s.evidence_excerpt or s.text,
                    "text_offset_start": s.text_offset_start,
                    "text_offset_end": s.text_offset_end or (len(s.text) if s.text else 0),
                }
                for s in self.sources
            ],
            "paper_ids": self.paper_ids,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """
        Formats answer and source references as human-readable markdown.
        """
        lines = [self.answer, "", "### Supporting Citations & Evidence:"]
        if not self.sources:
            lines.append("_No citations available._")
        else:
            for s in self.sources:
                title_str = f" - '{s.title}'" if s.title else ""
                label_str = f" ({s.citation_label})" if s.citation_label else ""
                lines.append(
                    f"- **[{s.source_id}]{label_str} Paper {s.paper_id}**{title_str} ({s.page_display}, Section: *{s.section}*)\n"
                    f"  > \"{s.text.strip()[:200]}...\""
                )
        return "\n".join(lines)


class CitationFormatter:
    """
    Formatting utilities for citations.
    """

    @staticmethod
    def format_sources_summary(sources: List[SourceCitation]) -> str:
        if not sources:
            return "No sources available."
        return ", ".join(
            f"[{s.source_id}: {s.citation_label or f'Paper {s.paper_id}'} p.{s.page_start}]"
            for s in sources
        )

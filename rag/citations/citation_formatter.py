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
                    "source_id": getattr(s, "source_id", ""),
                    "paper_id": getattr(s, "paper_id", ""),
                    "document_id": getattr(s, "document_id", ""),
                    "chunk_id": getattr(s, "chunk_id", ""),
                    "page": getattr(s, "page_start", 1) or 1,
                    "page_start": getattr(s, "page_start", 1) or 1,
                    "page_end": getattr(s, "page_end", 1) or 1,
                    "section": getattr(s, "section", "Main Content"),
                    "text": getattr(s, "text", ""),
                    "score": getattr(s, "score", 0.0),
                    "title": getattr(s, "title", ""),
                    "filename": getattr(s, "filename", ""),
                    "locator": getattr(s, "locator", ""),
                    "citation_label": getattr(s, "citation_label", None),
                    "author_metadata": getattr(s, "author_metadata", None),
                    "paper_title": getattr(s, "paper_title", None) or getattr(s, "title", ""),
                    "publication_year": getattr(s, "publication_year", None),
                    "original_page_number": getattr(s, "original_page_number", None) or getattr(s, "page_start", 1),
                    "section_label": getattr(s, "section_label", None) or getattr(s, "section", ""),
                    "evidence_excerpt": getattr(s, "evidence_excerpt", None) or getattr(s, "text", ""),
                    "text_offset_start": getattr(s, "text_offset_start", 0),
                    "text_offset_end": getattr(s, "text_offset_end", None) or (len(getattr(s, "text", "") or "")),
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

"""
Citation mapper linking generated text citations ([S1], [S2]) to actual retrieved evidence.
Eliminates hallucinated references by validating against real source chunks.
Formats authoritative academic citations [Author et al., Year, p. X].
"""

import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource
from rag.citations.source_tracker import SourceTracker


def format_citation_label(
    authors: Optional[List[str]] = None,
    year: Optional[Any] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    title: Optional[str] = None,
    source_id: Optional[str] = None,
) -> str:
    """Format academic citation label: [Author et al., Year, p. X] or [Title, p. X]."""
    # 1. Author string
    author_str = ""
    if authors:
        last_names = []
        for a in authors:
            if not a:
                continue
            a_clean = str(a).strip()
            if "," in a_clean:
                last_name = a_clean.split(",")[0].strip()
            else:
                parts = a_clean.split()
                last_name = parts[-1] if parts else a_clean
            if last_name:
                last_names.append(last_name)
        if len(last_names) == 1:
            author_str = last_names[0]
        elif len(last_names) == 2:
            author_str = f"{last_names[0]} & {last_names[1]}"
        elif len(last_names) >= 3:
            author_str = f"{last_names[0]} et al."

    # 2. Year string
    year_str = str(year) if year else ""

    # 3. Page string
    page_str = ""
    if page_start is not None and page_end is not None and page_start != page_end:
        page_str = f"pp. {page_start}-{page_end}"
    elif page_start is not None:
        page_str = f"p. {page_start}"

    # 4. Assemble standard academic citation label
    if author_str:
        elements = [author_str]
        if year_str:
            elements.append(year_str)
        if page_str:
            elements.append(page_str)
        return f"[{', '.join(elements)}]"
    elif title:
        short_title = title if len(title) <= 28 else title[:25] + "..."
        elements = [f'"{short_title}"']
        if year_str:
            elements.append(year_str)
        if page_str:
            elements.append(page_str)
        return f"[{', '.join(elements)}]"
    elif source_id:
        if page_str:
            return f"[{source_id}, {page_str}]"
        return f"[{source_id}]"
    return "[Source]"


class SourceCitation(BaseModel):
    source_id: str
    paper_id: str
    document_id: str
    chunk_id: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: str = "Main Content"
    text: str
    score: float = 0.0
    title: Optional[str] = None
    filename: Optional[str] = None
    locator: Optional[str] = None
    citation_label: Optional[str] = None
    author_metadata: Optional[List[str]] = None
    paper_title: Optional[str] = None
    publication_year: Optional[int] = None
    original_page_number: Optional[int] = None
    section_label: Optional[str] = None
    evidence_excerpt: Optional[str] = None
    text_offset_start: Optional[int] = 0
    text_offset_end: Optional[int] = None

    @property
    def page_display(self) -> str:
        if self.page_start is None:
            return self.locator or "Source passage"
        if self.page_start == self.page_end:
            return f"Page {self.page_start}"
        return f"Pages {self.page_start}-{self.page_end}"


class CitationMapper:
    """
    Validates cited source IDs and maps them to concrete SourceCitation objects
    with academic citation metadata.
    """

    def __init__(self, tracker: SourceTracker, paper_metadata: Optional[Dict[str, Any]] = None):
        self.tracker = tracker
        self.paper_metadata = paper_metadata or {}

    def _build_citation(self, source: RetrievedSource) -> SourceCitation:
        pm = self.paper_metadata.get(source.paper_id, {})
        authors = pm.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        year = pm.get("year") or pm.get("publication_year")
        paper_title = pm.get("title") or source.title

        label = format_citation_label(
            authors=authors,
            year=year,
            page_start=source.page_start,
            page_end=source.page_end,
            title=paper_title,
            source_id=source.source_id,
        )

        return SourceCitation(
            source_id=source.source_id,
            paper_id=source.paper_id,
            document_id=source.document_id,
            chunk_id=source.chunk_id,
            page_start=source.page_start,
            page_end=source.page_end,
            section=source.section or "Main Content",
            text=source.text,
            score=source.score,
            title=paper_title,
            filename=source.filename,
            locator=source.locator,
            citation_label=label,
            author_metadata=authors,
            paper_title=paper_title,
            publication_year=int(year) if year and str(year).isdigit() else None,
            original_page_number=source.page_start,
            section_label=source.section or "Main Content",
            evidence_excerpt=source.text,
            text_offset_start=0,
            text_offset_end=len(source.text) if source.text else 0,
        )

    def map_citations(
        self,
        cited_source_ids: List[str],
        fallback_all_retrieved: bool = True,
    ) -> List[SourceCitation]:
        """
        Maps extracted citation tags (e.g. ['S1', 'S2']) to concrete SourceCitation records.
        If no citations were explicitly parsed and fallback is enabled, returns all retrieved sources.
        """
        mapped: List[SourceCitation] = []
        seen_chunk_ids = set()

        for sid in cited_source_ids:
            source = self.tracker.get_by_source_id(sid)
            if source and source.chunk_id not in seen_chunk_ids:
                mapped.append(self._build_citation(source))
                seen_chunk_ids.add(source.chunk_id)

        # If cited nothing explicitly but sources were retrieved, include retrieved sources
        if not mapped and fallback_all_retrieved:
            for source in self.tracker.all_sources():
                if source.chunk_id not in seen_chunk_ids:
                    mapped.append(self._build_citation(source))
                    seen_chunk_ids.add(source.chunk_id)

        return mapped

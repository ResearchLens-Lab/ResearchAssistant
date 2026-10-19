"""
Citation mapper linking generated text citations ([S1], [S2]) to actual retrieved evidence.
Eliminates hallucinated references by validating against real source chunks.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource
from rag.citations.source_tracker import SourceTracker


class SourceCitation(BaseModel):
    source_id: str
    paper_id: str
    document_id: str
    chunk_id: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: str
    text: str
    score: float = 0.0
    title: Optional[str] = None
    filename: Optional[str] = None
    locator: Optional[str] = None

    @property
    def page_display(self) -> str:
        if self.page_start is None:
            return self.locator or "Source passage"
        if self.page_start == self.page_end:
            return f"Page {self.page_start}"
        return f"Pages {self.page_start}-{self.page_end}"


class CitationMapper:
    """
    Validates cited source IDs and maps them to concrete SourceCitation objects.
    """

    def __init__(self, tracker: SourceTracker):
        self.tracker = tracker

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
                mapped.append(
                    SourceCitation(
                        source_id=source.source_id,
                        paper_id=source.paper_id,
                        document_id=source.document_id,
                        chunk_id=source.chunk_id,
                        page_start=source.page_start,
                        page_end=source.page_end,
                        section=source.section,
                        text=source.text,
                        score=source.score,
                        title=source.title,
                        filename=source.filename,
                        locator=source.locator,
                    )
                )
                seen_chunk_ids.add(source.chunk_id)

        # If LLM cited nothing explicitly but sources were retrieved, include retrieved sources
        if not mapped and fallback_all_retrieved:
            for source in self.tracker.all_sources():
                if source.chunk_id not in seen_chunk_ids:
                    mapped.append(
                        SourceCitation(
                            source_id=source.source_id,
                            paper_id=source.paper_id,
                            document_id=source.document_id,
                            chunk_id=source.chunk_id,
                            page_start=source.page_start,
                            page_end=source.page_end,
                            section=source.section,
                            text=source.text,
                            score=source.score,
                            title=source.title,
                            filename=source.filename,
                            locator=source.locator,
                        )
                    )
                    seen_chunk_ids.add(source.chunk_id)

        return mapped

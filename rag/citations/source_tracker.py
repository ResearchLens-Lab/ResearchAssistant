"""
Source tracker maintaining full provenance throughout the RAG pipeline.
"""

from typing import List, Dict, Optional
from rag.retrieval.query import RetrievedSource


class SourceTracker:
    """
    Maintains a registry of retrieved sources indexed by source_id (S1, S2, ...)
    and chunk_id.
    """

    def __init__(self, sources: Optional[List[RetrievedSource]] = None):
        self._sources_by_id: Dict[str, RetrievedSource] = {}
        self._sources_by_chunk: Dict[str, RetrievedSource] = {}
        if sources:
            self.register_sources(sources)

    def register_sources(self, sources: List[RetrievedSource]) -> None:
        for s in sources:
            self._sources_by_id[s.source_id.upper()] = s
            self._sources_by_chunk[s.chunk_id] = s

    def get_by_source_id(self, source_id: str) -> Optional[RetrievedSource]:
        return self._sources_by_id.get(source_id.upper())

    def get_by_chunk_id(self, chunk_id: str) -> Optional[RetrievedSource]:
        return self._sources_by_chunk.get(chunk_id)

    def all_sources(self) -> List[RetrievedSource]:
        return list(self._sources_by_id.values())

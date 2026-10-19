"""
Context selection, deduplication, and multi-paper source balancing.
"""

from typing import List, Set
from rag.retrieval.query import RetrievedSource


class ContextSelector:
    """
    Selects, filters, and deduplicates retrieved sources.
    """

    @staticmethod
    def deduplicate(sources: List[RetrievedSource]) -> List[RetrievedSource]:
        """
        Deduplicates chunks based on chunk_id or identical text prefix.
        """
        seen_ids: Set[str] = set()
        seen_texts: Set[tuple[str, str]] = set()
        deduped: List[RetrievedSource] = []

        for src in sources:
            if src.chunk_id in seen_ids:
                continue
            text_key = (src.document_id, " ".join(src.text.split()).casefold())
            if text_key in seen_texts:
                continue

            seen_ids.add(src.chunk_id)
            seen_texts.add(text_key)
            deduped.append(src)

        return deduped

    @staticmethod
    def balance_multi_paper(
        sources: List[RetrievedSource],
        target_paper_ids: List[str],
        max_sources_per_paper: int = 4,
    ) -> List[RetrievedSource]:
        """
        Ensures balanced representation across multiple papers during comparative RAG.
        """
        if not target_paper_ids or len(target_paper_ids) <= 1:
            return sources

        paper_counts = {pid: 0 for pid in target_paper_ids}
        balanced: List[RetrievedSource] = []

        for src in sources:
            if src.paper_id in paper_counts:
                if paper_counts[src.paper_id] < max_sources_per_paper:
                    balanced.append(src)
                    paper_counts[src.paper_id] += 1
            else:
                balanced.append(src)

        return balanced

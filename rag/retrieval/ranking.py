"""
Vector result ranking and relevance score normalization.
"""

from typing import List
from rag.vectorstore.vector_repository import VectorRecord


class ResultRanker:
    """
    Ranks retrieved vector records by relevance similarity and applies score cutoffs.
    """

    @staticmethod
    def rank(
        records: List[VectorRecord],
        min_score: float = 0.0,
        top_k: int = 5,
    ) -> List[VectorRecord]:
        if not records:
            return []

        # Sort descending by similarity score
        sorted_records = sorted(
            records,
            key=lambda r: r.similarity_score if r.similarity_score is not None else 0.0,
            reverse=True,
        )

        # Filter by threshold
        filtered = [
            r for r in sorted_records
            if (r.similarity_score is not None and r.similarity_score >= min_score)
        ]

        return filtered[:top_k]

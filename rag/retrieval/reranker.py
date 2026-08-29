"""
Reranking interface and pass-through implementation.
Extensible for future neural cross-encoder rerankers without changing client callers.
"""

from abc import ABC, abstractmethod
from typing import List
from rag.retrieval.query import RetrievedSource


class BaseReranker(ABC):
    """
    Abstract reranker interface.
    """

    @abstractmethod
    def rerank(self, query: str, sources: List[RetrievedSource], top_k: int) -> List[RetrievedSource]:
        """
        Reranks a list of candidate RetrievedSource objects against the query.
        """
        pass


class IdentityReranker(BaseReranker):
    """
    Default pass-through reranker preserving initial vector similarity order.
    """

    def rerank(self, query: str, sources: List[RetrievedSource], top_k: int) -> List[RetrievedSource]:
        return sources[:top_k]

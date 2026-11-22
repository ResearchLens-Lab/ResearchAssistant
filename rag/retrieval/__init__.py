"""Retrieval module exports with lazy loading for model-backed components."""

from rag.retrieval.query import QueryRequest, QueryFilters, RetrievedSource
from rag.retrieval.filters import FilterBuilder

__all__ = [
    "QueryRequest",
    "QueryFilters",
    "RetrievedSource",
    "FilterBuilder",
    "ResultRanker",
    "BaseReranker",
    "IdentityReranker",
    "ResearchRetriever",
]


def __getattr__(name: str):
    if name == "ResultRanker":
        from rag.retrieval.ranking import ResultRanker
        return ResultRanker
    elif name in ("BaseReranker", "IdentityReranker"):
        from rag.retrieval.reranker import BaseReranker, IdentityReranker
        return {"BaseReranker": BaseReranker, "IdentityReranker": IdentityReranker}[name]
    elif name == "ResearchRetriever":
        from rag.retrieval.retriever import ResearchRetriever
        return ResearchRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

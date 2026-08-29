"""
Main retrieval engine for ResearchLens RAG.
Orchestrates query embedding, vector search, metadata filtering, ranking, and provenance mapping.
"""

import logging
from typing import List, Optional

from rag.config.settings import settings
from rag.embeddings.embedder import BaseEmbedder
from rag.embeddings.model_registry import EmbeddingModelRegistry
from rag.vectorstore.vector_repository import VectorRepository
from rag.retrieval.query import QueryRequest, RetrievedSource, QueryFilters
from rag.retrieval.filters import FilterBuilder
from rag.retrieval.ranking import ResultRanker
from rag.retrieval.reranker import BaseReranker, IdentityReranker

logger = logging.getLogger(__name__)


class ResearchRetriever:
    """
    Retrieves and ranks relevant research passages from ChromaDB.
    """

    def __init__(
        self,
        embedder: Optional[BaseEmbedder] = None,
        vector_repo: Optional[VectorRepository] = None,
        reranker: Optional[BaseReranker] = None,
    ):
        self.embedder = embedder or EmbeddingModelRegistry.get_embedder()
        self.vector_repo = vector_repo or VectorRepository()
        self.reranker = reranker or IdentityReranker()

    def retrieve(self, request: QueryRequest) -> List[RetrievedSource]:
        """
        Executes end-to-end retrieval for a QueryRequest.
        """
        logger.info(
            "Retrieving sources for query='%s' (paper_ids=%s, top_k=%d)",
            request.question[:50],
            request.paper_ids,
            request.top_k,
        )

        # 1. Embed query
        query_embedding = self.embedder.embed_query(request.question)

        # 2. Build metadata filter
        where_filter = FilterBuilder.build_where_filter(
            paper_ids=request.paper_ids,
            filters=request.filters,
        )

        # 3. Retrieve candidates (fetch slightly more than top_k for ranking headroom)
        fetch_limit = min(50, max(request.top_k * 2, 10))
        vector_records = self.vector_repo.query_vectors(
            query_embedding=query_embedding,
            top_k=fetch_limit,
            where=where_filter,
        )

        if not vector_records:
            logger.info("No vector records found matching query and filters.")
            return []

        # 4. Rank & filter by score threshold
        ranked_records = ResultRanker.rank(
            records=vector_records,
            min_score=request.min_score,
            top_k=fetch_limit,
        )

        # 5. Convert to RetrievedSource objects with deterministic S1, S2 IDs
        candidate_sources: List[RetrievedSource] = []
        for idx, rec in enumerate(ranked_records, start=1):
            source = RetrievedSource(
                source_id=f"S{idx}",
                chunk_id=rec.metadata.chunk_id,
                paper_id=rec.metadata.paper_id,
                document_id=rec.metadata.document_id,
                page_start=rec.metadata.page_start,
                page_end=rec.metadata.page_end,
                section=rec.metadata.section,
                text=rec.text,
                score=round(rec.similarity_score or 0.0, 4),
                title=rec.metadata.title,
            )
            candidate_sources.append(source)

        # 6. Apply Reranking
        final_sources = self.reranker.rerank(
            query=request.question,
            sources=candidate_sources,
            top_k=request.top_k,
        )

        # Re-index source_ids cleanly after final selection
        for idx, s in enumerate(final_sources, start=1):
            s.source_id = f"S{idx}"

        logger.info("Retrieved %d relevant sources", len(final_sources))
        return final_sources

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
from rag.retrieval.reranker import BaseReranker, IdentityReranker, IntentAwareReranker

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
        self.reranker = reranker or IntentAwareReranker()

    def retrieve(self, request: QueryRequest, owner_id: str) -> List[RetrievedSource]:
        """
        Executes end-to-end retrieval for a QueryRequest.
        
        Args:
            request: Query request with question, filters, and options
            owner_id: REQUIRED user ID for multi-tenant isolation (SEC-001)
            
        Returns:
            List of retrieved sources owned by the specified user
            
        Raises:
            ValueError: If owner_id is not provided
        """
        if not owner_id:
            raise ValueError("owner_id is required for secure retrieval (SEC-001 compliance)")
            
        logger.info(
            "Retrieving sources owner_id=%s query_chars=%d (paper_ids=%s, top_k=%d)",
            owner_id,
            len(request.question),
            request.paper_ids,
            request.top_k,
        )

        # 1. Embed query
        query_embedding = self.embedder.embed_query(request.question)

        # 2. Build metadata filter with MANDATORY owner_id (SEC-001 fix)
        where_filter = FilterBuilder.build_where_filter(
            owner_id=owner_id,  # CRITICAL: Enforces tenant isolation
            paper_ids=request.paper_ids,
            filters=request.filters,
        )

        # 3. Retrieve candidates (fetch slightly more than top_k for ranking headroom)
        fetch_limit = min(80, max(request.top_k * 4, 30))
        vector_records = self.vector_repo.query_vectors(
            query_embedding=query_embedding,
            top_k=fetch_limit,
            where=where_filter,
        )

        # 4. Rank & filter by score threshold
        ranked_records = ResultRanker.rank(
            records=vector_records,
            min_score=request.min_score,
            top_k=fetch_limit,
        )

        # Fuse dense and lexical rankings. Lexical lookup runs only within an
        # explicit paper scope, keeping the scan bounded to the user's selection.
        lexical_records = self.vector_repo.query_lexical(request.question, where=where_filter, limit=1000)
        if not ranked_records and not lexical_records:
            logger.info("No dense or lexical records found matching query and filters.")
            return []
        if lexical_records:
            fused = {}
            records_by_id = {}
            for ranked_list in (ranked_records, lexical_records):
                for rank, rec in enumerate(ranked_list, start=1):
                    fused[rec.id] = fused.get(rec.id, 0.0) + 1.0 / (60 + rank)
                    records_by_id.setdefault(rec.id, rec)
            ranked_records = [records_by_id[key] for key in sorted(fused, key=fused.get, reverse=True)[:fetch_limit]]

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
                filename=rec.metadata.filename,
                locator=rec.metadata.locator,
            )
            candidate_sources.append(source)

        # 6. Apply Reranking
        final_sources = self.reranker.rerank(
            query=request.question,
            sources=candidate_sources,
            top_k=request.top_k,
            intent=request.intent,
        )

        # For comparison queries, preserve the best genuinely matching passage
        # from each selected paper before filling remaining slots by relevance.
        selected_ids = list(dict.fromkeys(request.paper_ids or []))
        if len(selected_ids) > 1 and final_sources:
            by_id = {source.paper_id: source for source in candidate_sources if source.paper_id in selected_ids}
            balanced = [by_id[pid] for pid in selected_ids if pid in by_id]
            chosen = {source.chunk_id for source in balanced}
            balanced.extend(source for source in candidate_sources if source.chunk_id not in chosen)
            final_sources = balanced[:request.top_k]

        # Re-index source_ids cleanly after final selection
        for idx, s in enumerate(final_sources, start=1):
            s.source_id = f"S{idx}"

        logger.info("Retrieved %d relevant sources", len(final_sources))
        return final_sources

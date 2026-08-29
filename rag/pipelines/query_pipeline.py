"""
Query Pipeline for ResearchLens RAG.
Orchestrates: Question -> Retrieval -> Context Construction -> Grounded Generation -> Citation Mapping -> RAGResult.
"""

import time
import logging
from typing import Optional, List, Dict, Any

from rag.config.settings import settings
from rag.retrieval.query import QueryRequest, QueryFilters, RetrievedSource
from rag.retrieval.retriever import ResearchRetriever
from rag.context.context_builder import ContextBuilder, AssembledContext
from rag.generation.generator import GroundedGenerator, GenerationResult
from rag.citations.source_tracker import SourceTracker
from rag.citations.citation_mapper import CitationMapper, SourceCitation
from rag.citations.citation_formatter import RAGResult

logger = logging.getLogger(__name__)


class QueryPipeline:
    """
    High-level query engine executing grounded research Q&A, summarization, and multi-paper comparison.
    """

    def __init__(
        self,
        retriever: Optional[ResearchRetriever] = None,
        context_builder: Optional[ContextBuilder] = None,
        generator: Optional[GroundedGenerator] = None,
    ):
        self.retriever = retriever or ResearchRetriever()
        self.context_builder = context_builder or ContextBuilder()
        self.generator = generator or GroundedGenerator()

    def answer_question(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        filters: Optional[QueryFilters] = None,
        top_k: Optional[int] = None,
    ) -> RAGResult:
        """
        Answers a research question grounded in indexed papers with verified citations.
        """
        start_time = time.time()
        k = top_k or settings.retrieval_top_k

        # 1. Structured Query Request
        query_req = QueryRequest(
            question=question,
            paper_ids=paper_ids,
            filters=filters,
            top_k=k,
            min_score=settings.retrieval_min_score,
        )

        # 2. Vector Retrieval & Ranking
        retrieved_sources = self.retriever.retrieve(query_req)

        # 3. Provenance Tracking & Context Assembly
        tracker = SourceTracker(retrieved_sources)
        assembled_context: AssembledContext = self.context_builder.build_context(
            sources=retrieved_sources,
            target_paper_ids=paper_ids,
        )

        # 4. Grounded Generation
        gen_result: GenerationResult = self.generator.generate_answer(
            question=question,
            context=assembled_context,
        )

        # 5. Citation Mapping
        mapper = CitationMapper(tracker)
        citations: List[SourceCitation] = mapper.map_citations(
            cited_source_ids=gen_result.parsed.cited_source_ids,
            fallback_all_retrieved=True,
        )

        elapsed = time.time() - start_time
        resolved_paper_ids = paper_ids or list(dict.fromkeys(s.paper_id for s in retrieved_sources))

        return RAGResult(
            answer=gen_result.answer,
            sources=citations,
            paper_ids=resolved_paper_ids,
            metadata={
                "execution_time_seconds": round(elapsed, 3),
                "total_retrieved": len(retrieved_sources),
                "total_context_sources": assembled_context.total_sources,
                "cited_sources_count": len(citations),
                "llm_provider": settings.llm_provider,
                "embedding_provider": settings.embedding_provider,
            },
        )

    def summarize_paper(
        self,
        paper_id: str,
        top_k: int = 8,
    ) -> RAGResult:
        """
        Generates a comprehensive, structured summary for an indexed research paper.
        """
        start_time = time.time()

        # Query broad terms to capture abstract, methodology, results, and conclusion
        summary_query = f"overview methodology experiments results conclusion limitations of {paper_id}"
        query_req = QueryRequest(
            question=summary_query,
            paper_ids=[paper_id],
            top_k=top_k,
        )

        retrieved_sources = self.retriever.retrieve(query_req)
        tracker = SourceTracker(retrieved_sources)
        assembled_context = self.context_builder.build_context(
            sources=retrieved_sources,
            target_paper_ids=[paper_id],
        )

        gen_result = self.generator.generate_summary(context=assembled_context)

        mapper = CitationMapper(tracker)
        citations = mapper.map_citations(
            cited_source_ids=gen_result.parsed.cited_source_ids,
            fallback_all_retrieved=True,
        )

        elapsed = time.time() - start_time
        return RAGResult(
            answer=gen_result.answer,
            sources=citations,
            paper_ids=[paper_id],
            metadata={
                "task": "summarize",
                "paper_id": paper_id,
                "execution_time_seconds": round(elapsed, 3),
                "total_retrieved": len(retrieved_sources),
            },
        )

    def compare_papers(
        self,
        paper_ids: List[str],
        focus_area: Optional[str] = None,
        top_k: int = 10,
    ) -> RAGResult:
        """
        Generates structured multi-paper comparison between two or more research papers.
        """
        start_time = time.time()
        focus = focus_area or "Compare methodologies, datasets, architectures, and key findings."

        query_req = QueryRequest(
            question=focus,
            paper_ids=paper_ids,
            top_k=top_k,
        )

        retrieved_sources = self.retriever.retrieve(query_req)
        tracker = SourceTracker(retrieved_sources)
        assembled_context = self.context_builder.build_context(
            sources=retrieved_sources,
            target_paper_ids=paper_ids,
        )

        gen_result = self.generator.generate_comparison(
            focus_area=focus,
            context=assembled_context,
        )

        mapper = CitationMapper(tracker)
        citations = mapper.map_citations(
            cited_source_ids=gen_result.parsed.cited_source_ids,
            fallback_all_retrieved=True,
        )

        elapsed = time.time() - start_time
        return RAGResult(
            answer=gen_result.answer,
            sources=citations,
            paper_ids=paper_ids,
            metadata={
                "task": "compare",
                "paper_ids": paper_ids,
                "focus_area": focus,
                "execution_time_seconds": round(elapsed, 3),
                "total_retrieved": len(retrieved_sources),
            },
        )

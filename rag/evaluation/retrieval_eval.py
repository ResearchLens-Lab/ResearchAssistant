"""
Retrieval evaluation harness.
"""

from typing import List, Dict, Any
from rag.retrieval.retriever import ResearchRetriever
from rag.retrieval.query import QueryRequest, RetrievedSource
from rag.evaluation.metrics import EvaluationMetrics
from rag.pipelines.query_pipeline import QueryPipeline


class RetrievalEvaluator:
    """
    Evaluates vector retrieval performance against golden test cases.
    """

    def __init__(self, retriever: ResearchRetriever, query_pipeline: QueryPipeline | None = None):
        self.retriever = retriever
        self.query_pipeline = query_pipeline

    def evaluate_item(self, item: Dict[str, Any], top_k: int = 5) -> Dict[str, float]:
        question = item["question"]
        paper_ids = item.get("paper_ids") or ([item["paper_id"]] if item.get("paper_id") else None)
        expected_section = item.get("expected_section")
        expected_keywords = item.get("expected_keywords")

        if self.query_pipeline:
            result = self.query_pipeline.answer_question(
                question=question, paper_ids=paper_ids, top_k=top_k,
                conversation_context=item.get("conversation_context"),
            )
            sources = [RetrievedSource(
                source_id=s.source_id, chunk_id=s.chunk_id, paper_id=s.paper_id,
                document_id=s.document_id, page_start=s.page_start, page_end=s.page_end,
                section=s.section, text=s.text, score=s.score, title=s.title,
                filename=s.filename, locator=s.locator,
            ) for s in result.sources]
        else:
            req = QueryRequest(question=question, paper_ids=paper_ids, top_k=top_k)
            sources = self.retriever.retrieve(req)

        hit = EvaluationMetrics.compute_hit_at_k(
            sources=sources,
            expected_section=expected_section,
            expected_keywords=expected_keywords,
        )
        relevance = EvaluationMetrics.compute_source_relevance(
            sources=sources,
            expected_keywords=expected_keywords,
        )
        expected_sources = item.get("expected_source_papers") or []
        source_coverage = (len(set(expected_sources) & {s.paper_id for s in sources}) / len(expected_sources)) if expected_sources else None
        expected = [kw.casefold() for kw in (expected_keywords or [])]
        first_relevant_rank = next((i for i, src in enumerate(sources, 1)
                                    if any(term in src.text.casefold() for term in expected)), None)

        return {
            "hit_at_k": hit,
            "source_relevance": relevance,
            "retrieved_count": len(sources),
            "source_coverage": round(source_coverage, 4) if source_coverage is not None else None,
            "reciprocal_rank": (round(1 / first_relevant_rank, 4) if first_relevant_rank else 0.0) if expected else None,
        }

"""
Retrieval evaluation harness.
"""

from typing import List, Dict, Any
from rag.retrieval.retriever import ResearchRetriever
from rag.retrieval.query import QueryRequest
from rag.evaluation.metrics import EvaluationMetrics


class RetrievalEvaluator:
    """
    Evaluates vector retrieval performance against golden test cases.
    """

    def __init__(self, retriever: ResearchRetriever):
        self.retriever = retriever

    def evaluate_item(self, item: Dict[str, Any], top_k: int = 5) -> Dict[str, float]:
        question = item["question"]
        paper_id = item.get("paper_id")
        expected_section = item.get("expected_section")
        expected_keywords = item.get("expected_keywords")

        req = QueryRequest(
            question=question,
            paper_ids=[paper_id] if paper_id else None,
            top_k=top_k,
        )
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

        return {
            "hit_at_k": hit,
            "source_relevance": relevance,
            "retrieved_count": len(sources),
        }

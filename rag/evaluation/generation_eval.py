"""
Generation evaluation harness.
"""

from typing import Dict, Any
from rag.pipelines.query_pipeline import QueryPipeline
from rag.citations.citation_formatter import RAGResult
from rag.retrieval.query import RetrievedSource
from rag.evaluation.metrics import EvaluationMetrics


class GenerationEvaluator:
    """
    Evaluates grounded generation and citation correctness.
    """

    def __init__(self, query_pipeline: QueryPipeline):
        self.query_pipeline = query_pipeline

    def evaluate_item(self, item: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
        question = item["question"]
        paper_id = item.get("paper_id")
        expected_points = item.get("expected_answer_points")

        rag_result: RAGResult = self.query_pipeline.answer_question(
            question=question,
            paper_ids=[paper_id] if paper_id else None,
            top_k=top_k,
        )

        # Convert citations back to RetrievedSource structure for metric computation
        retrieved_sources = [
            RetrievedSource(
                source_id=s.source_id,
                chunk_id=s.chunk_id,
                paper_id=s.paper_id,
                document_id=s.document_id,
                page_start=s.page_start,
                page_end=s.page_end,
                section=s.section,
                text=s.text,
                score=s.score,
                title=s.title,
            )
            for s in rag_result.sources
        ]

        grounding = EvaluationMetrics.compute_answer_grounding(
            answer=rag_result.answer,
            sources=retrieved_sources,
            expected_points=expected_points,
        )
        citation_correct = EvaluationMetrics.compute_citation_correctness(rag_result)

        return {
            "answer": rag_result.answer,
            "answer_grounding": grounding,
            "citation_correctness": citation_correct,
            "cited_count": len(rag_result.sources),
        }

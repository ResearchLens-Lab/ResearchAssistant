"""
Generation evaluation harness.
"""

from typing import Dict, Any
import re
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
        paper_ids = item.get("paper_ids") or ([item["paper_id"]] if item.get("paper_id") else None)
        expected_points = item.get("expected_answer_points")

        rag_result: RAGResult = self.query_pipeline.answer_question(
            question=question,
            paper_ids=paper_ids,
            top_k=top_k,
            conversation_context=item.get("conversation_context"),
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
                locator=s.locator,
            )
            for s in rag_result.sources
        ]

        grounding = EvaluationMetrics.compute_answer_grounding(
            answer=rag_result.answer,
            sources=retrieved_sources,
            expected_points=expected_points,
        )
        citation_correct = EvaluationMetrics.compute_citation_correctness(rag_result)
        research = rag_result.metadata.get("research", {})
        claim_items = research.get("claim_verification", {}).get("items", [])
        claim_statuses = [claim.get("status") for claim in claim_items]
        checkable = [s for s in claim_statuses if s in {"supported", "partial", "contradicted", "unsupported", "invalid_reference"}]
        nums = list(dict.fromkeys(re.findall(r"\d+(?:\.\d+)?", " ".join(expected_points or []))))
        numerical_correctness = (sum(number in rag_result.answer for number in nums) / len(nums)) if nums else None
        points = expected_points or []
        expected_fact_coverage = (sum(any(word.lower() in rag_result.answer.lower() for word in point.split() if len(word) > 4) for point in points) / len(points)) if points else None
        locator_validity = (sum(bool(src.document_id and src.chunk_id and src.text.strip() and (src.page_start or src.locator)) for src in retrieved_sources) / len(retrieved_sources)) if retrieved_sources else (1.0 if not rag_result.sources else 0.0)
        expected_unanswerable = item.get("expected_unanswerable")
        missing_evidence_detection = (float("insufficient evidence" in rag_result.answer.lower()) == float(bool(expected_unanswerable))) if expected_unanswerable is not None else None
        expected_contradiction = item.get("expected_contradiction", item.get("id") == "contradiction")
        contradiction_handling = (float(research.get("sufficiency", {}).get("status") == "conflicting" and "differ" in rag_result.answer.lower()) if expected_contradiction else None)

        return {
            "answer": rag_result.answer,
            "answer_grounding": grounding,
            "citation_correctness": citation_correct,
            "cited_count": len(rag_result.sources),
            "unsupported_handling": float(
                (rag_result.metadata.get("research", {}).get("sufficiency", {}).get("status") == "insufficient")
                == bool(item.get("expected_unanswerable"))
            ) if item.get("expected_unanswerable") is not None else None,
            "execution_time_seconds": rag_result.metadata.get("execution_time_seconds", 0.0),
            "claim_support_rate": sum(status == "supported" for status in checkable) / len(checkable) if checkable else None,
            "invalid_citation_frequency": sum(status == "invalid_reference" for status in checkable) / len(checkable) if checkable else None,
            "locator_validity": locator_validity,
            "expected_fact_coverage": expected_fact_coverage,
            "numerical_correctness": numerical_correctness,
            "missing_evidence_detection": missing_evidence_detection,
            "contradiction_handling": contradiction_handling,
            "retrieval_rounds": rag_result.metadata.get("retrieval_rounds", 0),
            "model_calls": rag_result.metadata.get("model_calls", 0),
            "stage_timings": rag_result.metadata.get("timings", {}),
        }

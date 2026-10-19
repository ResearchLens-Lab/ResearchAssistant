"""
Unified RAG evaluator runner.
Loads benchmark datasets and generates comprehensive metric reports.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from rag.pipelines.query_pipeline import QueryPipeline
from rag.retrieval.retriever import ResearchRetriever
from rag.evaluation.retrieval_eval import RetrievalEvaluator
from rag.evaluation.generation_eval import GenerationEvaluator
from rag.evaluation.metrics import EvaluationItemResult, EvaluationSummary

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    Runs end-to-end evaluation across a benchmark question dataset.
    """

    def __init__(
        self,
        query_pipeline: Optional[QueryPipeline] = None,
        retriever: Optional[ResearchRetriever] = None,
    ):
        self.query_pipeline = query_pipeline or QueryPipeline()
        self.retriever = retriever or self.query_pipeline.retriever
        self.retrieval_eval = RetrievalEvaluator(self.retriever, query_pipeline=self.query_pipeline)
        self.generation_eval = GenerationEvaluator(self.query_pipeline)

    def load_dataset(self, dataset_path: Optional[str] = None) -> List[Dict[str, Any]]:
        if dataset_path:
            path = Path(dataset_path)
        else:
            path = Path(__file__).parent / "datasets" / "sample_questions.json"

        if not path.exists():
            raise FileNotFoundError(f"Dataset not found at: {path}")

        return json.loads(path.read_text(encoding="utf-8-sig"))

    def run_evaluation(
        self,
        dataset: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 5,
    ) -> EvaluationSummary:
        items = dataset if dataset is not None else self.load_dataset()
        results: List[EvaluationItemResult] = []

        logger.info("Running evaluation on %d test questions (top_k=%d)", len(items), top_k)

        for item in items:
            q_id = item.get("id", "q")
            q_text = item["question"]

            # Evaluate retrieval
            ret_metrics = self.retrieval_eval.evaluate_item(item, top_k=top_k)

            # Evaluate generation
            gen_metrics = self.generation_eval.evaluate_item(item, top_k=top_k)

            res = EvaluationItemResult(
                question_id=q_id,
                question=q_text,
                hit_at_k=ret_metrics["hit_at_k"],
                source_relevance=ret_metrics["source_relevance"],
                answer_grounding=gen_metrics["answer_grounding"],
                citation_correctness=gen_metrics["citation_correctness"],
                retrieved_count=ret_metrics["retrieved_count"],
                cited_count=gen_metrics["cited_count"],
                source_coverage=ret_metrics.get("source_coverage", 0.0),
                reciprocal_rank=ret_metrics.get("reciprocal_rank", 0.0),
                unsupported_handling=gen_metrics.get("unsupported_handling", 0.0),
                latency_seconds=gen_metrics.get("execution_time_seconds", 0.0),
                category=item.get("category", {
                    "direct_fact": "direct", "exact_equation": "terminology_equation", "conceptual": "conceptual",
                    "multi_passage": "multi_chunk", "multi_document_compare": "cross_document",
                    "method_results": "methodology_results", "insufficient": "unanswerable",
                    "contradiction": "contradictory_sources", "follow_up": "follow_up",
                    "adversarial_source": "prompt_injection_source",
                }.get(q_id, "uncategorized")),
                claim_support_rate=gen_metrics.get("claim_support_rate"),
                invalid_citation_frequency=gen_metrics.get("invalid_citation_frequency"),
                locator_validity=gen_metrics.get("locator_validity"),
                expected_fact_coverage=gen_metrics.get("expected_fact_coverage"),
                numerical_correctness=gen_metrics.get("numerical_correctness"),
                contradiction_handling=gen_metrics.get("contradiction_handling"),
                missing_evidence_detection=gen_metrics.get("missing_evidence_detection"),
                retrieval_rounds=gen_metrics.get("retrieval_rounds", 0),
                model_calls=gen_metrics.get("model_calls", 0),
                stage_timings=gen_metrics.get("stage_timings", {}),
            )
            results.append(res)

        # Compute averages
        n = max(1, len(results))
        summary = EvaluationSummary(
            total_questions=len(results),
            mean_hit_at_k=round(sum(r.hit_at_k for r in results) / n, 4),
            mean_source_relevance=round(sum(r.source_relevance for r in results) / n, 4),
            mean_answer_grounding=round(sum(r.answer_grounding for r in results) / n, 4),
            mean_citation_correctness=round(sum(r.citation_correctness for r in results) / n, 4),
            mean_source_coverage=round(sum(r.source_coverage for r in results if r.source_coverage is not None) / max(1, sum(r.source_coverage is not None for r in results)), 4),
            mean_reciprocal_rank=round(sum(r.reciprocal_rank for r in results if r.reciprocal_rank is not None) / max(1, sum(r.reciprocal_rank is not None for r in results)), 4),
            mean_unsupported_handling=round(sum(r.unsupported_handling for r in results if r.unsupported_handling is not None) / max(1, sum(r.unsupported_handling is not None for r in results)), 4),
            mean_latency_seconds=round(sum(r.latency_seconds for r in results) / n, 4),
            item_results=results,
            by_category={
                category: {
                    metric: round(sum(value for item in grouped if (value := getattr(item, metric)) is not None) / max(1, sum(getattr(item, metric) is not None for item in grouped)), 4)
                    for metric in ("hit_at_k", "source_relevance", "answer_grounding", "citation_correctness",
                                   "claim_support_rate", "locator_validity", "expected_fact_coverage", "numerical_correctness")
                }
                for category in sorted({result.category for result in results})
                for grouped in [[r for r in results if r.category == category]]
            },
        )

        logger.info(
            "Evaluation complete! Hit@%d: %.2f | Relevance: %.2f | Grounding: %.2f | Citation: %.2f",
            top_k,
            summary.mean_hit_at_k,
            summary.mean_source_relevance,
            summary.mean_answer_grounding,
            summary.mean_citation_correctness,
        )
        return summary

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
        self.retrieval_eval = RetrievalEvaluator(self.retriever)
        self.generation_eval = GenerationEvaluator(self.query_pipeline)

    def load_dataset(self, dataset_path: Optional[str] = None) -> List[Dict[str, Any]]:
        if dataset_path:
            path = Path(dataset_path)
        else:
            path = Path(__file__).parent / "datasets" / "sample_questions.json"

        if not path.exists():
            raise FileNotFoundError(f"Dataset not found at: {path}")

        return json.loads(path.read_text(encoding="utf-8"))

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
            item_results=results,
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

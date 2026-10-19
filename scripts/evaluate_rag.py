#!/usr/bin/env python3
"""Run the practical RAG benchmark against an isolated disposable vector store."""
import sys
import argparse
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.evaluation.evaluator import RAGEvaluator
from rag.pipelines.query_pipeline import QueryPipeline
from rag.research.orchestrator import QueryPlanner
from rag.config.settings import settings
from rag.vectorstore.chroma_client import ChromaClientFactory


class DirectOnlyPlanner(QueryPlanner):
    """Evaluation baseline: one user query, with no subquestions or retry."""
    def plan(self, question, source_ids=None, retrieval_scope=None):
        plan = super().plan(question, source_ids, retrieval_scope)
        return plan.model_copy(update={
            "subquestions": [], "search_queries": [plan.search_queries[0]],
            "max_retrieval_rounds": 1,
        })


def main():
    parser = argparse.ArgumentParser(description="Evaluate ResearchLens RAG retrieval and generation metrics.")
    parser.add_argument("--dataset-path", type=str, default=str(Path(__file__).parent.parent / "rag" / "evaluation" / "datasets" / "research_intelligence_questions.json"))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--auto-ingest-fixture", action="store_true", default=True)
    parser.add_argument("--report-path", type=str, default=str(Path(__file__).parent.parent / "docs" / "rag" / "reports" / "phase3_1_mock.json"))
    args = parser.parse_args()

    print(f"ResearchLens RAG Evaluation | dataset={args.dataset_path} | top_k={args.top_k}")
    with tempfile.TemporaryDirectory(prefix="researchlens-eval-") as evaluation_store:
        settings.chroma_persist_dir = evaluation_store
        settings.embedding_provider = "mock"
        settings.embedding_model = "mock-dense-384"
        settings.embedding_dimension = 384
        settings.llm_provider = "mock"
        ChromaClientFactory.reset_client()
        try:
            if args.auto_ingest_fixture:
                fixture_specs = [
                    ("sample_paper.txt", "paper_attention_2017", "Attention Is All You Need"),
                    ("sample_paper_2.txt", "paper_graphlens_2020", "Graph Neural Networks for Research Paper Representation"),
                    ("benchmark_cedar.txt", "benchmark_cedar_a", "Cedar benchmark report"),
                    ("benchmark_cedar_replication.txt", "benchmark_cedar_b", "Cedar replication report"),
                    ("adversarial_document.txt", "paper_adversarial", "Adversarial source fixture"),
                ]
                ingest = IngestionPipeline()
                for filename, paper_id, title in fixture_specs:
                    path = str(Path(__file__).parent / "sample_data" / filename)
                    result = ingest.ingest_file(path, paper_id=paper_id, metadata={"title": title})
                    print(f"Fixture indexed: {paper_id} ({result.chunk_count} chunks)")
            dataset = RAGEvaluator().load_dataset(args.dataset_path)
            baseline = RAGEvaluator(query_pipeline=QueryPipeline(planner=DirectOnlyPlanner()))
            baseline_summary = baseline.run_evaluation(dataset=dataset, top_k=args.top_k)
            advanced = RAGEvaluator()
            summary = advanced.run_evaluation(dataset=dataset, top_k=args.top_k)
        finally:
            ChromaClientFactory.shutdown_client()

    print(f"Questions: {summary.total_questions}")
    print(f"Mean Hit@{args.top_k}: {summary.mean_hit_at_k * 100:.1f}%")
    print(f"Mean source relevance: {summary.mean_source_relevance * 100:.1f}%")
    print(f"Mean answer grounding: {summary.mean_answer_grounding * 100:.1f}%")
    print(f"Mean citation correctness: {summary.mean_citation_correctness * 100:.1f}%")
    print(f"Mean source coverage: {summary.mean_source_coverage * 100:.1f}% (only questions with labeled required papers)")
    print(f"Mean reciprocal rank: {summary.mean_reciprocal_rank:.3f} (keyword-labeled fixtures)")
    print(f"Unsupported-question handling: {summary.mean_unsupported_handling * 100:.1f}%")
    print(f"Mean end-to-end latency: {summary.mean_latency_seconds:.3f}s")
    for field, label in [("claim_support_rate", "Claim heuristic support"),
                         ("locator_validity", "Deterministic locator validity"),
                         ("expected_fact_coverage", "Expected fact coverage")]:
        values = [getattr(item, field) for item in summary.item_results if getattr(item, field) is not None]
        if values:
            print(f"{label}: {sum(values) / len(values) * 100:.1f}% (n={len(values)})")
    for field, label in [("numerical_correctness", "Numerical extraction"),
                         ("missing_evidence_detection", "Missing-evidence detection"),
                         ("contradiction_handling", "Contradiction handling"),
                         ("invalid_citation_frequency", "Invalid citation frequency")]:
        values = [getattr(item, field) for item in summary.item_results if getattr(item, field) is not None]
        if values:
            print(f"{label}: {sum(values) / len(values) * 100:.1f}% (n={len(values)})")
    print(f"Mean retrieval rounds / model calls: "
          f"{sum(i.retrieval_rounds for i in summary.item_results) / max(1, summary.total_questions):.2f} / "
          f"{sum(i.model_calls for i in summary.item_results) / max(1, summary.total_questions):.2f}")
    for stage in ("planning_seconds", "retrieval_seconds", "generation_seconds", "verification_seconds"):
        values = [i.stage_timings[stage] for i in summary.item_results if stage in i.stage_timings]
        if values:
            print(f"Mean {stage}: {sum(values) / len(values):.4f}s (n={len(values)})")
    print("\nPer-category results (Hit@K / relevance / grounding / citation identity):")
    for category, metrics in summary.by_category.items():
        before = baseline_summary.by_category.get(category, {})
        print(f"{category}: hit {before.get('hit_at_k', 0)*100:.1f}->{metrics['hit_at_k']*100:.1f}%, "
              f"relevance {before.get('source_relevance', 0)*100:.1f}->{metrics['source_relevance']*100:.1f}%, "
              f"grounding {before.get('answer_grounding', 0)*100:.1f}->{metrics['answer_grounding']*100:.1f}%, "
              f"citation {before.get('citation_correctness', 0)*100:.1f}->{metrics['citation_correctness']*100:.1f}%")
    print("\nDirect-query baseline -> bounded research orchestration")
    for metric, before, after in [
        ("Hit@K", baseline_summary.mean_hit_at_k, summary.mean_hit_at_k),
        ("Source relevance", baseline_summary.mean_source_relevance, summary.mean_source_relevance),
        ("Answer grounding", baseline_summary.mean_answer_grounding, summary.mean_answer_grounding),
        ("Citation correctness", baseline_summary.mean_citation_correctness, summary.mean_citation_correctness),
        ("Source coverage", baseline_summary.mean_source_coverage, summary.mean_source_coverage),
        ("MRR", baseline_summary.mean_reciprocal_rank, summary.mean_reciprocal_rank),
    ]:
        print(f"{metric}: {before * 100:.1f}% -> {after * 100:.1f}% ({(after - before) * 100:+.1f} pp)")
    print(f"Mean end-to-end latency: {baseline_summary.mean_latency_seconds:.3f}s -> {summary.mean_latency_seconds:.3f}s")
    for item in summary.item_results:
        print(f"[{item.question_id}] hit={item.hit_at_k:.2f} relevance={item.source_relevance:.2f} grounding={item.answer_grounding:.2f} citation={item.citation_correctness:.2f} retrieved={item.retrieved_count} cited={item.cited_count}")
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"provider_mode": "deterministic mock", "top_k": args.top_k,
        "dataset_path": str(Path(args.dataset_path).as_posix()), "question_count": summary.total_questions,
        "direct_single_pass": baseline_summary.model_dump(mode="json"),
        "research_orchestration": summary.model_dump(mode="json")}, indent=2), encoding="utf-8")
    print(f"Actual execution report: {report_path}")


if __name__ == "__main__":
    main()

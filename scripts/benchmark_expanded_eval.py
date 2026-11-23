"""Expanded Real-World Evaluation Benchmark for Deterministic Answer Generation V2.

Evaluates:
- Long research papers
- Complex PDF tables & microarchitecture specifications
- Mathematical and technical terminology
- Multi-document comparisons
- Cross-section synthesis
- Numerical queries
- Implicit context & dangling references
- Negative control abstention
"""

import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import tracemalloc
import unicodedata
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.independent.engine import IndependentResearchEngine
from rag.independent.retriever import IndependentRetriever, configured_lexical_collection_name
from scripts.benchmark_deterministic_v2 import build_sqlite_index, normalize_text, extract_words, compute_redundancy

DATASETS_DIR = REPO_ROOT / "rag" / "evaluation" / "datasets"
EXP_CORPUS_PATH = DATASETS_DIR / "expanded_realworld_corpus.json"
EXP_CASES_PATH = DATASETS_DIR / "expanded_realworld_cases.json"


def run_expanded_benchmark(verbose: bool = True) -> dict:
    corpus = json.loads(EXP_CORPUS_PATH.read_text(encoding="utf-8"))
    cases = json.loads(EXP_CASES_PATH.read_text(encoding="utf-8"))

    results_by_run = []
    cold_latencies = []
    warm_latencies = []

    with tempfile.TemporaryDirectory(prefix="researchlens_exp_bench_") as tmp_dir:
        db_path = Path(tmp_dir) / "exp_benchmark.sqlite3"
        build_sqlite_index(db_path, corpus)

        retriever = IndependentRetriever(db_path=db_path)
        engine = IndependentResearchEngine(retriever=retriever)

        # 3 consecutive runs to verify determinism and latency
        for run_idx in range(3):
            run_answers = {}
            for case in cases:
                t0 = time.perf_counter()
                rag_result = engine.answer(
                    question=case["question"],
                    paper_ids=case.get("papers"),
                    top_k=6,
                    owner_id="v2_bench_owner",
                )
                dt = (time.perf_counter() - t0) * 1000.0  # ms
                if run_idx == 0:
                    cold_latencies.append(dt)
                else:
                    warm_latencies.append(dt)
                run_answers[case["id"]] = {
                    "answer": rag_result.answer,
                    "sources": rag_result.sources,
                    "metadata": rag_result.metadata,
                }
            results_by_run.append(run_answers)

        # Isolated memory measurement pass
        tracemalloc.start()
        start_mem = tracemalloc.get_traced_memory()[0]
        for case in cases[:4]:
            _ = engine.answer(
                question=case["question"],
                paper_ids=case.get("papers"),
                top_k=6,
                owner_id="v2_bench_owner",
            )
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Check Determinism
        identical_runs = 0
        total_cases = len(cases)
        for case in cases:
            c_id = case["id"]
            ans0 = results_by_run[0][c_id]["answer"]
            ans1 = results_by_run[1][c_id]["answer"]
            ans2 = results_by_run[2][c_id]["answer"]
            if ans0 == ans1 and ans1 == ans2:
                identical_runs += 1
        determinism_rate = identical_runs / total_cases

        run0 = results_by_run[0]
        relevance_scores = []
        completeness_scores = []
        grounding_scores = []
        redundancy_scores = []
        citation_scores = []
        abstention_correct = 0
        total_abstentions_expected = sum(1 for c in cases if c.get("expected_abstain"))

        for case in cases:
            c_id = case["id"]
            data = run0[c_id]
            answer = data["answer"]
            answer_low = normalize_text(answer)
            sources = data["sources"]
            source_map = {s.source_id.upper(): s for s in sources}

            is_abstain = "not found in your selected documents." in answer_low
            expected_abstain = case.get("expected_abstain", False)

            if expected_abstain:
                if is_abstain:
                    abstention_correct += 1
                else:
                    print(f"FAILED ABSTENTION {c_id}: answer={repr(answer[:200])}")
                relevance_scores.append(1.0 if is_abstain else 0.0)
                completeness_scores.append(1.0 if is_abstain else 0.0)
                grounding_scores.append(1.0)
                citation_scores.append(1.0 if not re.findall(r"\[S\d+\]", answer, re.I) else 0.0)
                continue

            q_words = [w for w in extract_words(case["question"]) if len(w) > 3]
            a_words = extract_words(answer)
            rel = len([w for w in q_words if w in a_words]) / max(len(q_words), 1)
            relevance_scores.append(rel)

            expected_kw = case.get("expected_keywords", [])
            kw_hits = len([kw for kw in expected_kw if normalize_text(kw) in answer_low])
            comp = kw_hits / max(len(expected_kw), 1)
            completeness_scores.append(comp)

            cited_tags = re.findall(r"\[(S\d+)\]", answer, re.I)
            valid_citations = 0
            for tag in cited_tags:
                tag_u = tag.upper()
                if tag_u in source_map and source_map[tag_u].page_start is not None:
                    valid_citations += 1
            cit_acc = valid_citations / max(len(cited_tags), 1) if cited_tags else 0.0
            if cit_acc < 1.0:
                print(f"CIT ACC < 1 {c_id}: cit_acc={cit_acc}, cited_tags={cited_tags}, sources={list(source_map.keys())}")
            citation_scores.append(cit_acc)

            evidence_status = (
                data["metadata"]
                .get("independent_research", {})
                .get("evidence_decision", {})
                .get("status", "")
            )
            unsupported = (
                data["metadata"]
                .get("independent_research", {})
                .get("evidence_decision", {})
                .get("unsupported_claims", [])
            )
            grounding = 1.0 if not unsupported and evidence_status in ("STRONGLY SUPPORTED", "PARTIALLY SUPPORTED", "COMPUTED FROM EXTRACTED DOCUMENT STRUCTURE", "CONFLICTING EVIDENCE") else (0.5 if not unsupported else 0.0)
            grounding_scores.append(grounding)

            red = compute_redundancy(answer)
            redundancy_scores.append(red)

            if verbose and (expected_abstain or cit_acc < 1.0 or comp < 0.5):
                print(f"CASE {c_id}: comp={comp:.2f}, cit_acc={cit_acc:.2f}, is_abstain={is_abstain}, expected_abstain={expected_abstain}")
                print(f"  Question: {case['question']}")
                print(f"  Answer start: {repr(answer[:150])}")

        avg_relevance = sum(relevance_scores) / total_cases
        avg_completeness = sum(completeness_scores) / total_cases
        avg_grounding = sum(grounding_scores) / total_cases
        avg_redundancy = sum(redundancy_scores) / max(total_cases - total_abstentions_expected, 1)
        avg_citation_acc = sum(citation_scores) / total_cases
        abstention_rate = abstention_correct / max(total_abstentions_expected, 1)

        cold_sorted = sorted(cold_latencies)
        cold_mean = sum(cold_latencies) / len(cold_latencies)
        cold_median = cold_sorted[len(cold_sorted) // 2]
        cold_p95 = cold_sorted[int(0.95 * len(cold_sorted))]
        cold_max = max(cold_latencies)

        warm_sorted = sorted(warm_latencies)
        warm_mean = sum(warm_latencies) / len(warm_latencies)
        warm_median = warm_sorted[len(warm_sorted) // 2]
        warm_p95 = warm_sorted[int(0.95 * len(warm_sorted))]
        warm_max = max(warm_latencies)

        peak_mem_mb = (peak_mem - start_mem) / (1024 * 1024)

        metrics = {
            "total_cases": total_cases,
            "answer_relevance": round(avg_relevance, 4),
            "completeness": round(avg_completeness, 4),
            "factual_grounding": round(avg_grounding, 4),
            "redundancy_jaccard": round(avg_redundancy, 4),
            "citation_accuracy": round(avg_citation_acc, 4),
            "determinism_rate": round(determinism_rate, 4),
            "abstention_accuracy": round(abstention_rate, 4),
            "cold_mean_latency_ms": round(cold_mean, 2),
            "cold_median_latency_ms": round(cold_median, 2),
            "cold_p95_latency_ms": round(cold_p95, 2),
            "cold_max_latency_ms": round(cold_max, 2),
            "warm_mean_latency_ms": round(warm_mean, 2),
            "warm_median_latency_ms": round(warm_median, 2),
            "warm_p95_latency_ms": round(warm_p95, 2),
            "warm_max_latency_ms": round(warm_max, 2),
            "peak_memory_mb": round(peak_mem_mb, 3),
        }

        if verbose:
            print("==================================================")
            print("Expanded Real-World Evaluation Benchmark")
            print("==================================================")
            for k, v in metrics.items():
                print(f"  {k:25}: {v}")
            print("==================================================")

        return metrics


if __name__ == "__main__":
    run_expanded_benchmark(verbose=True)

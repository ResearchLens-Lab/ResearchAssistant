#!/usr/bin/env python3
"""
Authoritative Gold Evaluation Harness for ResearchLens RAG Intelligence.
Evaluates query retrieval and grounded answer synthesis against gold_algorithms_v1.json.
Reports metrics across Tune (40), Held-out (20), and Out-of-corpus controls (12).
"""

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Ensure LLM is disabled for deterministic extractive evaluation
os.environ["LLM_ENABLED"] = "false"

logging.basicConfig(level=logging.ERROR)

from rag.intelligence.engine import ResearchIntelligenceEngine
from rag.intelligence.confidence_evaluator import ConfidenceLevel


def run_gold_evaluation(db_path: str, dataset_path: str, verbose: bool = False) -> Dict[str, Any]:
    print(f"--- Running Gold Evaluation against: {db_path} ---")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    questions = dataset["questions"]
    in_corpus = [q for q in questions if not q.get("expected_abstention", False)]
    out_of_corpus = [q for q in questions if q.get("expected_abstention", False)]

    engine = ResearchIntelligenceEngine(db_path=db_path)

    in_corpus_results = []
    latencies = []

    # Run in-corpus evaluation
    for item in in_corpus:
        qid = item["id"]
        qtext = item["question"]
        intent = item["intent"]
        split = item.get("split", "tune")
        pattern = re.compile(item["must_match"], re.I)

        t0 = time.perf_counter()
        # Retrieve sources and answer
        u = engine.query_analyzer.analyze(qtext)
        sources, traces = engine.retrieval_engine.retrieve(u, top_k=10)
        conf = engine.confidence_evaluator.evaluate(u, sources, traces)
        ans = engine.answer_composer.compose(u, sources, conf)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        h1 = False
        h3 = False
        h10 = False

        for rank, s in enumerate(sources[:10]):
            stext = getattr(s, "text", "") or ""
            if pattern.search(stext):
                if rank == 0:
                    h1 = True
                if rank < 3:
                    h3 = True
                h10 = True

        is_abstained = (
            ans.confidence_level == ConfidenceLevel.NOT_LOCATED
            or "could not locate" in (ans.headline_answer or "").lower()
            or "could not locate" in (ans.markdown_content or "").lower()
        )

        in_corpus_results.append({
            "id": qid,
            "split": split,
            "intent": intent,
            "question": qtext,
            "head_concept": getattr(u, "head_concept", None) or u.raw_query,
            "must_match": item["must_match"],
            "hit1": h1,
            "hit3": h3,
            "hit10": h10,
            "abstained": is_abstained,
            "candidate_count": len(sources),
            "sources": sources,
            "ans": ans,
            "latency_ms": latency_ms,
        })

    # Run out-of-corpus evaluation
    ooc_results = []
    for item in out_of_corpus:
        qid = item["id"]
        qtext = item["question"]

        t0 = time.perf_counter()
        u = engine.query_analyzer.analyze(qtext)
        sources, traces = engine.retrieval_engine.retrieve(u, top_k=10)
        conf = engine.confidence_evaluator.evaluate(u, sources, traces)
        ans = engine.answer_composer.compose(u, sources, conf)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        is_abstained = (
            ans.confidence_level == ConfidenceLevel.NOT_LOCATED
            or "could not locate" in (ans.headline_answer or "").lower()
            or "could not locate" in (ans.markdown_content or "").lower()
        )
        false_answer = not is_abstained

        ooc_results.append({
            "id": qid,
            "question": qtext,
            "head_concept": getattr(u, "head_concept", None) or u.raw_query,
            "abstained": is_abstained,
            "false_answer": false_answer,
            "confidence": ans.confidence_level.value,
            "headline": ans.headline_answer,
            "candidate_count": len(sources),
            "latency_ms": latency_ms,
        })

    def calc_split_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(results)
        if not n:
            return {"count": 0, "hit1": 0.0, "hit3": 0.0, "hit10": 0.0, "false_abstention": 0.0}
        return {
            "count": n,
            "hit1": sum(1 for r in results if r["hit1"]) / n,
            "hit3": sum(1 for r in results if r["hit3"]) / n,
            "hit10": sum(1 for r in results if r["hit10"]) / n,
            "false_abstention": sum(1 for r in results if r["abstained"]) / n,
            "hit1_count": sum(1 for r in results if r["hit1"]),
            "hit3_count": sum(1 for r in results if r["hit3"]),
            "hit10_count": sum(1 for r in results if r["hit10"]),
            "abstained_count": sum(1 for r in results if r["abstained"]),
        }

    tune_results = [r for r in in_corpus_results if r["split"] == "tune"]
    held_out_results = [r for r in in_corpus_results if r["split"] == "held_out"]

    tune_metrics = calc_split_metrics(tune_results)
    held_out_metrics = calc_split_metrics(held_out_results)
    overall_metrics = calc_split_metrics(in_corpus_results)

    n_ooc = len(ooc_results)
    ooc_false_answer_rate = sum(1 for r in ooc_results if r["false_answer"]) / n_ooc if n_ooc else 0

    p50_latency = statistics.median(latencies) if latencies else 0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies or [0])

    print("\n" + "=" * 70)
    print("                    GOLD BENCHMARK RESULTS")
    print("=" * 70)
    print(f"OVERALL IN-CORPUS (N={overall_metrics['count']}):")
    print(f"  Hit@1:            {overall_metrics['hit1'] * 100:.1f}% ({overall_metrics['hit1_count']}/{overall_metrics['count']})")
    print(f"  Hit@3:            {overall_metrics['hit3'] * 100:.1f}% ({overall_metrics['hit3_count']}/{overall_metrics['count']})")
    print(f"  Hit@10:           {overall_metrics['hit10'] * 100:.1f}% ({overall_metrics['hit10_count']}/{overall_metrics['count']})")
    print(f"  False Abstention: {overall_metrics['false_abstention'] * 100:.1f}% ({overall_metrics['abstained_count']}/{overall_metrics['count']})")
    print("-" * 70)
    print(f"TUNE SPLIT (N={tune_metrics['count']}):")
    print(f"  Hit@1:            {tune_metrics['hit1'] * 100:.1f}% ({tune_metrics['hit1_count']}/{tune_metrics['count']})")
    print(f"  Hit@3:            {tune_metrics['hit3'] * 100:.1f}% ({tune_metrics['hit3_count']}/{tune_metrics['count']})")
    print(f"  Hit@10:           {tune_metrics['hit10'] * 100:.1f}% ({tune_metrics['hit10_count']}/{tune_metrics['count']})")
    print(f"  False Abstention: {tune_metrics['false_abstention'] * 100:.1f}% ({tune_metrics['abstained_count']}/{tune_metrics['count']})")
    print("-" * 70)
    print(f"HELD-OUT SPLIT (N={held_out_metrics['count']}):")
    print(f"  Hit@1:            {held_out_metrics['hit1'] * 100:.1f}% ({held_out_metrics['hit1_count']}/{held_out_metrics['count']})")
    print(f"  Hit@3:            {held_out_metrics['hit3'] * 100:.1f}% ({held_out_metrics['hit3_count']}/{held_out_metrics['count']})")
    print(f"  Hit@10:           {held_out_metrics['hit10'] * 100:.1f}% ({held_out_metrics['hit10_count']}/{held_out_metrics['count']})")
    print(f"  False Abstention: {held_out_metrics['false_abstention'] * 100:.1f}% ({held_out_metrics['abstained_count']}/{held_out_metrics['count']})")
    print("-" * 70)
    print(f"OUT-OF-CORPUS CONTROLS (N={n_ooc}):")
    print(f"  False Answer:     {ooc_false_answer_rate * 100:.1f}% ({sum(1 for r in ooc_results if r['false_answer'])}/{n_ooc}) [Target: 0.0%]")
    print("-" * 70)
    print(f"Latency P50:        {p50_latency:.1f} ms | P95: {p95_latency:.1f} ms")
    print("=" * 70)

    # Breakdown by intent for Hit@3
    intents = sorted(list(set(r["intent"] for r in in_corpus_results)))
    print("\n--- INTENT BREAKDOWN (Hit@3) ---")
    for it in intents:
        subset = [r for r in in_corpus_results if r["intent"] == it]
        h3_rate = sum(1 for r in subset if r["hit3"]) / len(subset) if subset else 0
        abs_cnt = sum(1 for r in subset if r["abstained"])
        print(f"  {it:<15} {h3_rate * 100:>5.1f}% ({sum(1 for r in subset if r['hit3'])}/{len(subset)}) | Abstained: {abs_cnt}")

    # False abstentions
    false_abstentions = [r for r in in_corpus_results if r["abstained"]]
    print(f"\n--- FALSE ABSTENTIONS ({len(false_abstentions)} total) ---")
    for idx, fa in enumerate(false_abstentions):
        print(f"\nAbstention #{idx + 1}: [{fa['id']}] ({fa['split']}/{fa['intent']}) {fa['question']}")
        print(f"  Head concept:     {fa['head_concept']}")
        print(f"  Candidate count:  {fa['candidate_count']}")
        print(f"  Confidence:       {fa['ans'].confidence_level.value} (Score: {fa['ans'].confidence_score:.3f})")
        print(f"  Headline:         {fa['ans'].headline_answer}")
        print("  Top candidates:")
        for rk, s in enumerate(fa["sources"][:3]):
            stext = (getattr(s, "text", "") or "").replace("\n", " ")[:120]
            print(f"    Rank {rk + 1} [chunk_id={getattr(s, 'chunk_id', 'N/A')} p.{getattr(s, 'page_start', 'N/A')}]: {stext}...")

    # Hit@3 misses
    hit3_misses = [r for r in in_corpus_results if not r["hit3"]]
    print(f"\n--- HIT@3 MISSES ({len(hit3_misses)} total) ---")
    for idx, hm in enumerate(hit3_misses):
        print(f"\nMiss #{idx + 1}: [{hm['id']}] ({hm['split']}/{hm['intent']}) {hm['question']}")
        print(f"  Must match:       {hm['must_match']}")
        print(f"  Head concept:     {hm['head_concept']}")
        print(f"  Candidate count:  {hm['candidate_count']}")
        print(f"  Hit@10:           {hm['hit10']} | Abstained: {hm['abstained']}")
        print("  Top candidates:")
        for rk, s in enumerate(hm["sources"][:3]):
            stext = (getattr(s, "text", "") or "").replace("\n", " ")[:120]
            print(f"    Rank {rk + 1} [chunk_id={getattr(s, 'chunk_id', 'N/A')} p.{getattr(s, 'page_start', 'N/A')}]: {stext}...")

    return {
        "overall": overall_metrics,
        "tune": tune_metrics,
        "held_out": held_out_metrics,
        "ooc_false_answer": ooc_false_answer_rate,
        "p50_latency": p50_latency,
        "p95_latency": p95_latency,
        "false_abstentions": false_abstentions,
        "hit3_misses": hit3_misses,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gold algorithm evaluation harness.")
    default_db = os.path.join(os.environ.get("TEMP", ""), "rl_diag_copy", "researchlens_lexical.sqlite3")
    parser.add_argument("--db-path", default=default_db, help="Path to researchlens_lexical.sqlite3")
    parser.add_argument("--dataset", default="rag/evaluation/datasets/gold_algorithms_v1.json", help="Path to dataset JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    run_gold_evaluation(args.db_path, args.dataset, args.verbose)

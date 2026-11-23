"""Integration and regression test for expanded real-world evaluation benchmark."""

import pytest
from scripts.benchmark_expanded_eval import run_expanded_benchmark


def test_expanded_benchmark_metrics():
    metrics = run_expanded_benchmark(verbose=False)

    assert metrics["total_cases"] == 16
    assert metrics["determinism_rate"] == 1.0, "Expanded benchmark must be 100% deterministic"
    assert metrics["factual_grounding"] == 1.0, "All cited claims must be grounded in source text"
    assert metrics["citation_accuracy"] == 1.0, "All citations must resolve to valid retrieved chunks"
    assert metrics["abstention_accuracy"] == 1.0, "Negative controls must achieve 100% honest abstention"
    assert metrics["completeness"] >= 0.90, f"Completeness should be >= 90%, got {metrics['completeness']}"
    assert metrics["warm_mean_latency_ms"] < 50.0, f"Warm mean latency should be < 50ms, got {metrics['warm_mean_latency_ms']}"

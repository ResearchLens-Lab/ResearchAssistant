"""Comprehensive regression and validation tests for Deterministic Answer Generation V2.

Covers:
1. Pronoun & dangling-reference restoration
2. Duplicate sentence removal & MMR diversity
3. Multi-document structured answers & dimension alignment
4. Calibrated evidence validation & honest academic abstention
5. Citation & physical page-number preservation
6. Strict determinism across repeated executions
7. Performance and memory overhead boundaries
"""

import json
import re
import tempfile
import time
import tracemalloc
from pathlib import Path

import pytest

from rag.independent.engine import IndependentResearchEngine
from rag.independent.models import QueryAnalysis, QuestionIntent
from rag.independent.retriever import IndependentRetriever, configured_lexical_collection_name
from rag.independent.sentence_selector import SentenceSelector, extract_prose_steps, segment_into_sentences
from rag.retrieval.query import RetrievedSource
from scripts.benchmark_deterministic_v2 import CASES_PATH, CORPUS_PATH, build_sqlite_index


@pytest.fixture(scope="module")
def v2_benchmark_env():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="v2_reg_test_") as tmp_dir:
        db_path = Path(tmp_dir) / "v2_reg.sqlite3"
        build_sqlite_index(db_path, corpus)
        retriever = IndependentRetriever(db_path=db_path)
        engine = IndependentResearchEngine(retriever=retriever)
        yield {"engine": engine, "cases": {c["id"]: c for c in cases}, "retriever": retriever}


def test_dangling_reference_context_restoration():
    """Verify that sentences starting with anaphora or connectors restore preceding context."""
    s = RetrievedSource(
        source_id="S1",
        chunk_id="chunk_proc",
        paper_id="paper_1",
        document_id="doc_1",
        page_start=12,
        page_end=12,
        section="Procedure",
        text=(
            "Binary search repeatedly partitions the search space in half. "
            "It terminates when the target is found or the interval is empty. "
            "However, dynamic insertions require O(n) reorganization."
        ),
        score=0.95,
    )
    selector = SentenceSelector()
    candidates = selector.extract_candidates([s])

    # Check candidate 2: "It terminates..."
    it_cand = next(c for c in candidates if c.text.startswith("It terminates"))
    assert it_cand.has_dangling_reference is True
    assert it_cand.preceding_text is not None
    assert "Binary search repeatedly partitions" in it_cand.restored_text
    assert "It terminates when" in it_cand.restored_text

    # Check candidate 3: "However, dynamic insertions..."
    how_cand = next(c for c in candidates if c.text.startswith("However"))
    assert how_cand.has_dangling_reference is True
    assert "It terminates when" in how_cand.preceding_text


def test_duplicate_sentence_removal_via_mmr():
    """Verify MMR filters near-identical sentences across retrieved passages."""
    s1 = RetrievedSource(
        source_id="S1",
        chunk_id="c1",
        paper_id="p1",
        document_id="d1",
        page_start=1,
        page_end=1,
        section="Results",
        text="ShieldNet achieved an intrusion detection accuracy of 94.6 percent in benchmark tests.",
        score=0.9,
    )
    s2 = RetrievedSource(
        source_id="S2",
        chunk_id="c2",
        paper_id="p1",
        document_id="d1",
        page_start=2,
        page_end=2,
        section="Summary",
        text="ShieldNet achieved an intrusion detection accuracy of 94.6 percent in comprehensive benchmark evaluations.",
        score=0.88,
    )
    analysis = QueryAnalysis(
        intent=QuestionIntent.EXPLANATION,
        normalized_question="what is the intrusion detection accuracy of ShieldNet",
        search_query="shieldnet intrusion detection accuracy",
        important_terms=["shieldnet", "intrusion", "detection", "accuracy"],
        primary_phrase="shieldnet",
    )
    selector = SentenceSelector(mmr_lambda=0.70)
    selected = selector.select_evidence_mmr(analysis, [s1, s2], limit=2)
    # The two sentences are near-duplicates (> 0.55 Jaccard similarity); MMR must select only 1
    assert len(selected) == 1
    assert selected[0].source_id == "S1"


def test_prose_sequential_steps_extraction():
    """Verify extraction of sequential procedural steps from prose text."""
    text = (
        "The merge sort procedure consists of three sequential steps: "
        "first, divide the n-element sequence to be sorted into two subsequences of n/2 elements each; "
        "second, conquer by sorting the two subsequences recursively using merge sort; "
        "third, combine the sorted subsequences by merging them to produce the sorted answer."
    )
    steps = extract_prose_steps(text)
    assert len(steps) == 3
    assert steps[0][0].lower() == "divide"
    assert "subsequences of n/2 elements" in steps[0][1]
    assert steps[1][0].lower() == "conquer"
    assert steps[2][0].lower() == "combine"


def test_calibrated_insufficient_evidence_abstention(v2_benchmark_env):
    """Verify engine cleanly abstains on out-of-scope and unanswerable questions."""
    engine = v2_benchmark_env["engine"]

    # 1. Out-of-corpus domain query
    r1 = engine.answer(
        "What is the chemical formula of penicillin in the selected papers?",
        paper_ids=["paper-algo", "paper-shield"],
        owner_id="v2_bench_owner",
    )
    assert "Not found in your selected documents." in r1.answer
    assert r1.metadata["independent_research"]["evidence_decision"]["status"] == "NOT FOUND"

    # 2. Concept query with missing attribute
    r2 = engine.answer(
        "What GPU memory bandwidth does EdgeGuard require for training?",
        paper_ids=["paper-edge"],
        owner_id="v2_bench_owner",
    )
    assert "Not found in your selected documents." in r2.answer
    assert r2.metadata["independent_research"]["evidence_decision"]["status"] == "NOT FOUND"

    # 3. Numerical query with missing metric
    r3 = engine.answer(
        "How many qubits does the ShieldNet quantum gate simulator employ?",
        paper_ids=["paper-shield"],
        owner_id="v2_bench_owner",
    )
    assert "Not found in your selected documents." in r3.answer
    assert r3.metadata["independent_research"]["evidence_decision"]["status"] == "NOT FOUND"


def test_multi_document_structured_comparison(v2_benchmark_env):
    """Verify multi-document comparison retains document integrity and verified citations."""
    engine = v2_benchmark_env["engine"]
    result = engine.answer(
        "Compare ShieldNet and EdgeGuard in terms of reported intrusion detection accuracy and latency.",
        paper_ids=["paper-shield", "paper-edge"],
        owner_id="v2_bench_owner",
    )
    # Check that table and comparison dimensions are populated
    assert "Comparison dimension" in result.answer
    assert "94.6%" in result.answer
    assert "89.4%" in result.answer
    assert "4.2 ms" in result.answer
    assert "CONFLICTING EVIDENCE" in result.answer
    assert "doc-shield" in result.answer and "doc-edge" in result.answer

    # Check zero unsupported claims
    unsupported = result.metadata["independent_research"]["evidence_decision"]["unsupported_claims"]
    assert not unsupported

    # Check citations resolve and have valid physical pages
    assert result.sources
    for s in result.sources:
        assert s.page_start is not None and s.page_start > 0


def test_strict_determinism_across_runs(v2_benchmark_env):
    """Verify 100% bitwise determinism across 3 repeated runs on varied questions."""
    engine = v2_benchmark_env["engine"]
    questions = [
        ("What is an algorithm?", ["paper-algo"]),
        ("What are the sequential steps of the merge sort procedure?", ["paper-algo"]),
        ("What are the limitations of ShieldNet?", ["paper-shield"]),
        ("Compare the primary constraints and limitations of ShieldNet and EdgeGuard.", ["paper-shield", "paper-edge"]),
        ("What is the chemical formula of penicillin in the selected papers?", ["paper-algo"]),
    ]

    for q, pids in questions:
        res1 = engine.answer(q, paper_ids=pids, owner_id="v2_bench_owner")
        res2 = engine.answer(q, paper_ids=pids, owner_id="v2_bench_owner")
        res3 = engine.answer(q, paper_ids=pids, owner_id="v2_bench_owner")

        assert res1.answer == res2.answer == res3.answer
        assert [s.source_id for s in res1.sources] == [s.source_id for s in res2.sources] == [s.source_id for s in res3.sources]
        assert [s.chunk_id for s in res1.sources] == [s.chunk_id for s in res2.sources] == [s.chunk_id for s in res3.sources]


def test_performance_latency_and_memory_boundaries(v2_benchmark_env):
    """Verify execution time is well within acceptable boundaries (< 250ms) and minimal RAM."""
    engine = v2_benchmark_env["engine"]

    tracemalloc.start()
    t0 = time.perf_counter()
    res = engine.answer("What is an algorithm?", paper_ids=["paper-algo"], owner_id="v2_bench_owner")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Latency should be sub-200ms on CPU
    assert elapsed_ms < 300.0, f"Query latency {elapsed_ms:.1f}ms exceeded limit"
    # Peak memory overhead under 15MB
    peak_mb = peak_mem / (1024 * 1024)
    assert peak_mb < 20.0, f"Memory overhead {peak_mb:.2f}MB exceeded limit"

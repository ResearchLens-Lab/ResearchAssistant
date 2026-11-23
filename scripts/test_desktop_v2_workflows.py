"""
Desktop V2 Integration Validation: Testing 10 real desktop workflows on sample PDFs.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED_SOURCE = REPO_ROOT / "desktop" / "build" / "app-runtime" / "source"

# Prioritize staged runtime source to guarantee testing the exact packaged code
sys.path.insert(0, str(STAGED_SOURCE))

# Force offline & independent mode environment variables
os.environ["RAG_ENGINE_MODE"] = "independent"
os.environ["RAG_MODE"] = "local"
os.environ["LLM_ENABLED"] = "false"
os.environ["EXTERNAL_LOOKUPS_ENABLED"] = "false"
os.environ["DESKTOP_RUNTIME"] = "true"

from rag.independent.ingest_pipeline import IndependentIngestionPipeline
from rag.independent.index_writer import IndependentIndexWriter
from rag.independent.retriever import IndependentRetriever
from rag.independent.engine import IndependentResearchEngine
from rag.independent.sentence_selector import SentenceSelector
from rag.independent.answer_composer import StructuredAnswerComposer
from rag.config.settings import settings


def run_validation():
    print("=" * 70)
    print("ResearchLens Desktop V2 Integration & Workflow Validation")
    print("=" * 70)

    # 1. Verify runtime imports from staged runtime source
    print("\n[Phase 1] Verifying runtime modules and import locations...")
    import rag.independent.sentence_selector as sel_mod
    import rag.independent.engine as eng_mod
    print(f"  SentenceSelector loaded from: {sel_mod.__file__}")
    print(f"  IndependentResearchEngine loaded from: {eng_mod.__file__}")
    assert "desktop" in sel_mod.__file__ and "app-runtime" in sel_mod.__file__, "Must load from staged app-runtime!"
    print("  => Confirmed: Staged desktop runtime source active with V2.")

    with tempfile.TemporaryDirectory(prefix="researchlens_desktop_val_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "indexes" / "researchlens_lexical.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Ingest Sample PDFs
        print("\n[Phase 2] Ingesting sample PDFs using IndependentIngestionPipeline...")
        writer = IndependentIndexWriter(db_path=db_path)
        pipeline = IndependentIngestionPipeline(index_writer=writer)

        samples_dir = REPO_ROOT / "desktop" / "samples"
        files_to_ingest = [
            ("synthetic_algorithms_paper.pdf", "paper-synthetic-01", "A Comparative Study of Deterministic Algorithmic Paradigms"),
            ("algorithm_report.pdf", "paper-algo-report-02", "ResearchLens Intelligence Brief: What is an algorithm?"),
            ("sample_report.pdf", "paper-sample-report-03", "ResearchLens Intelligence Report: Definition of Algorithm"),
        ]

        doc_ids = []
        for fname, paper_id, title in files_to_ingest:
            fpath = str(samples_dir / fname)
            print(f"  Ingesting {fname} (paper_id={paper_id})...")
            res = pipeline.ingest_file(
                file_path=fpath,
                paper_id=paper_id,
                metadata={
                    "document_id": f"doc_{paper_id}",
                    "owner_id": "desktop_user_01",
                    "title": title,
                    "filename": fname,
                }
            )
            assert res.success, f"Ingestion failed for {fname}: {res.error}"
            print(f"    Success: {res.chunk_count} chunks, {res.total_pages} pages in {res.execution_time_seconds}s")
            doc_ids.append(f"doc_{paper_id}")

        retriever = IndependentRetriever(db_path=db_path)
        engine = IndependentResearchEngine(retriever=retriever)

        # 3. Test 10 Real Desktop Workflows
        print("\n[Phase 3] Executing 10 Real Desktop Workflows...")
        test_workflows = [
            {
                "id": "WF-01",
                "category": "Definitions",
                "question": "What is an algorithm?",
                "papers": ["paper-algo-report-02", "paper-sample-report-03"],
                "check": lambda r: "computational procedure" in r.answer.lower() and len(r.sources) > 0,
            },
            {
                "id": "WF-02",
                "category": "Definitions",
                "question": "What is Divide-and-Conquer?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: "subproblems" in r.answer.lower() and len(r.sources) > 0,
            },
            {
                "id": "WF-03",
                "category": "Procedural Questions",
                "question": "What are the sequential steps of divide and conquer?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: ("steps" in r.answer.lower() or "procedural" in r.answer.lower() or "1." in r.answer) and len(r.sources) > 0,
            },
            {
                "id": "WF-04",
                "category": "Explanations",
                "question": "Explain how divide-and-conquer combines independent subproblems and uses the Master Theorem.",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: "master theorem" in r.answer.lower() and len(r.sources) > 0,
            },
            {
                "id": "WF-05",
                "category": "Numerical Lookups",
                "question": "What is the worst case time complexity and space complexity of Binary Search in Table 1?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: ("o(1)" in r.answer.lower() or "o(log n)" in r.answer.lower() or "table" in r.answer.lower()) and len(r.sources) > 0,
            },
            {
                "id": "WF-06",
                "category": "Limitations",
                "question": "What are the limitations of greedy strategies and dynamic programming?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: ("matroid" in r.answer.lower() or "storage" in r.answer.lower() or "overhead" in r.answer.lower()) and len(r.sources) > 0,
            },
            {
                "id": "WF-07",
                "category": "Unanswerable Questions (Honest Abstention)",
                "question": "What is the quantum decoherence threshold for surface codes reported in these documents?",
                "papers": ["paper-synthetic-01", "paper-algo-report-02"],
                "check": lambda r: "not found in your selected documents" in r.answer.lower() and len(r.sources) == 0,
            },
            {
                "id": "WF-08",
                "category": "Dangling-Reference Restoration",
                "question": "What do greedy algorithms provide and why do they not guarantee global optimality?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: "greedy" in r.answer.lower() and ("optimal" in r.answer.lower() or "matroid" in r.answer.lower()),
            },
            {
                "id": "WF-09",
                "category": "Citation Navigation & Provenance",
                "question": "What closed-form bounds does the Master Theorem provide?",
                "papers": ["paper-synthetic-01"],
                "check": lambda r: any(s.source_id.startswith("S") and s.page_start is not None for s in r.sources),
            },
            {
                "id": "WF-10",
                "category": "Multi-Document Evidence Grouping",
                "question": "Compare the definition of algorithm across both the brief and the comparative paper.",
                "papers": ["paper-synthetic-01", "paper-algo-report-02", "paper-sample-report-03"],
                "output_format": "side_by_side",
                "check": lambda r: len(r.sources) >= 2 and any(s.paper_id == "paper-synthetic-01" for s in r.sources) and any("algo" in s.paper_id or "sample" in s.paper_id for s in r.sources),
            },
        ]

        passed = 0
        results_summary = []
        for wf in test_workflows:
            t0 = time.perf_counter()
            rag_result = engine.answer(
                question=wf["question"],
                paper_ids=wf.get("papers"),
                output_format=wf.get("output_format"),
                top_k=6,
                owner_id="desktop_user_01",
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            is_valid = wf["check"](rag_result)
            passed += 1 if is_valid else 0
            status_str = "PASS" if is_valid else "FAIL"
            print(f"  [{status_str}] {wf['id']} ({wf['category']}): '{wf['question'][:45]}...' ({elapsed_ms:.2f}ms)")
            print(f"         Answer excerpt: {rag_result.answer[:120]}...")
            print(f"         Sources: {len(rag_result.sources)} citations: {[s.source_id + ' (p.' + str(s.page_start) + ')' for s in rag_result.sources[:3]]}")
            print(f"         Abstained: {rag_result.metadata.get('is_abstained', False)}")
            results_summary.append({
                "id": wf["id"],
                "category": wf["category"],
                "question": wf["question"],
                "passed": is_valid,
                "latency_ms": elapsed_ms,
                "sources_count": len(rag_result.sources),
                "is_abstained": rag_result.metadata.get("is_abstained", False),
                "answer_excerpt": rag_result.answer[:180],
            })

        print("\n" + "=" * 70)
        print(f"Results: {passed} / {len(test_workflows)} desktop workflows passed validation.")
        print("=" * 70)
        assert passed == len(test_workflows), f"Expected all {len(test_workflows)} to pass, got {passed}"
        return results_summary


if __name__ == "__main__":
    run_validation()

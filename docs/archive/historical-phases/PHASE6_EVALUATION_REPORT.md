# Phase 6 Evaluation Report

## Verification results

| Check | Result |
|---|---:|
| Phase 5 knowledge-graph tests plus Phase 6 tests | 15 passed in the focused run |
| Phase 6 tests | 4 synthetic cases (formation/idempotency/provenance, opt-in session capture/deletion, contradiction review gate, evaluator metric contract) |
| Full backend/RAG regression | 299 passed in the final run |
| Isolated SQLite migration upgrade through `978943c31f5c` | Passed |
| Alembic schema drift check | Passed: no new operations detected |
| Python compilation (`compileall -q backend rag`) | Passed |
| FastAPI OpenAPI generation | Passed; 77 paths in the current app |

## Reproducible synthetic evaluation

Fixture: `backend/tests/fixtures/phase6_synthetic_memory.json`. Run:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_research_memory.py
```

Measured fixture values: two retrieval queries; Recall@5 1.000, MRR 1.000, NDCG@5 1.000; association false-presentation rate 0/3; contradiction candidate precision 1/2, recall 1/2, false-candidate rate 1/4, reviewed-outcome accuracy 2/2; gap type/recording accuracy 3/3; temporal invariant checks 5/5. These values are a small hand-authored synthetic contract fixture, not a statistical model benchmark.

The service tests additionally verify that empty graph scope is ineligible, selected approved graph evidence forms semantic/source/episodic records, repeated same-scope processing is idempotent, retrieval returns current exact passages, and session capture fails until opt-in. Session deletion retains a review event. The fixture uses only temporary SQLite and synthetic Phase 4 artifacts. The memory audit command is read-only; stale evidence is suppressed at retrieval and reported by audit.

## Real-data and performance status

The Phase 5 report states that the real graph has zero imported documents and no real nodes/edges. No real memory evaluation was therefore possible or claimed. The configured database was not migrated, inspected, or populated. No performance benchmark was run against a representative graph or the i5-6300U/8 GB machine. Formation caps a scope at 200 selected assertions, evidence queries at 500 rows per assertion, retrieval at 1,000 recent memory records and 100 returned results, and associations at bounded pair counts. These bounds protect memory use but do not establish production latency.

## Limitations

Current association discovery uses shared reviewed graph nodes only; lexical association discovery, FTS5 memory search, citation-derived links, multi-signal weights, and graph-path scoring are not yet active. Contradiction detection only catches explicit opposing reviewed predicates on matching endpoints; it does not parse quantitative claims or experiment context. Research gaps are explicitly recorded and resolved by the researcher; unsupported chat queries are not auto-captured. No Phase 1 chat integration or frontend is enabled. No scientific entailment, truth, or citation-authenticity score is produced.

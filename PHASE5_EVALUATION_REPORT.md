# Phase 5 Evaluation Report

## Verification results

| Check | Result |
|---|---:|
| Focused graph tests | 11 passed |
| Full backend/RAG regression | 295 passed in 129.89 seconds |
| Migration upgrade | Passed on isolated temporary SQLite database, revisions `0001` through `0005` |
| Alembic schema drift check | Passed: no operations detected |
| Python compile | Passed (`compileall -q backend rag`) |

FastAPI OpenAPI generation listed 22 knowledge-graph routes. The routes use existing bearer authentication and owner scoping; API review attribution is resolved from the authenticated user.

Graph tests use a synthetic Phase 4 snapshot and temporary SQLite database. They cover approved-only import, exact evidence offsets, current-run gating, stale rejection after import, private-source consent/query behavior, owner isolation, endpoint-type validation, import idempotency and rollback, review history, bounded path/neighborhood traversal, edge correction and status, merge/undo provenance preservation, and authenticated API access/explicit confirmation. These checks are not real-paper extraction scores.

## Graph population and audit

- Real document imports this phase: **0**.
- Real graph nodes, edges, graph evidence, and approved graph candidates created: **0**.
- No synthetic fixture was imported into the configured graph database.
- No configured production database migration or read-only audit was run; the migration remains unapplied there. Therefore existing application graph counts are not claimed. The new tables will start empty when migration `0005` is applied.
- The test fixture audit returned two synthetic nodes, one synthetic edge, three exact provenance rows, 100% synthetic provenance coverage, and no issues after status was restored to current.

## Performance and quality limits

The full regression suite wall time is a correctness test runtime, not graph query throughput. No representative graph or target i5-6300U / 8 GB workload was available, so no production query latency or memory benchmark is claimed. Neighborhood/path operations are depth/result bounded and query one frontier at a time. The read-only audit streams edge, node, and evidence rows in batches; exact source validation remains I/O-bound on the local Phase 4 artifact store.

No semantic correctness, scientific truth, citation authenticity, or fuzzy identity merge accuracy is measured. Relationship validity is ontology/type validation plus a human's explicit assertion and source evidence; it is not automated entailment verification.

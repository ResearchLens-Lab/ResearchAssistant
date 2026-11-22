# Research Product Capability Roadmap

## Reuse existing work without overstating integration

| Capability | Existing basis | Desktop work and gate |
|---|---|---|
| Library / project records | FastAPI SQLAlchemy user, paper, document models; Next library routes/components | Make a per-user local library, project/document identity, managed/link storage and import recovery. |
| Deterministic Q&A | Phase 1 independent FTS5 retrieval/composer; default mode in backend/RAG config | Package FTS5 runtime; improve claim-level support and abstention; preserve local-only baseline. |
| PDF/source evidence | Page-aware chunks and citation mapping; PDF viewer/evidence components | Immutable version/page/block offsets and accurate passage highlighting; gracefully degrade to page locator. |
| Comparison / reports | Comparison service, UI and structured output formats | Validate document-level scope, independent citation mapping, gaps and durable report provenance. |
| Document intelligence, Phase 4 | Extractor/models/store and CLI; current audit found it is not standard upload path | Integrate per-version ingestion, transactional status, reviewable parser output and migration plan before release. |
| Training, Phases 2–3 | Dataset/schema, split, metrics, registry and NLP adapters | Keep candidate and approved data separate; build explicit review UI/API; no auto-training. Measure real reviewed data quality before enabling learned ranking. |
| Knowledge graph, Phase 5 | SQL models/routes/service plus separate graph integration boundary | Select one authoritative local graph path, link assertions to immutable evidence, review candidates, rollback/version and owner isolation. Current boundaries are duplicated/disconnected. |
| Memory, Phase 6 | Opt-in models/service and evaluation | Keep disabled by default, per-project/per-conversation scope and delete/export controls; measure retrieval impact. |
| Research Intelligence, Phase 7 | Planner/service, evidence and assessment structures | Reconcile its planning route with default independent answer flow; expose explainable retrieval path and quality measures. |
| Notebook / evidence ledger | Partial structures/UI patterns, not a verified end-to-end durable subsystem | Define normalized note, claim, evidence and review model with stable provenance; export/backup and deletion semantics. |

## Required before desktop alpha

1. Phase 4 integrated into standard ingestion with document-version/fingerprint identity.
2. Canonical evidence IDs and immutable provenance across parser, chunks, answer, graph, notebook, map and PDF viewer.
3. Desktop-specific data ownership and API auth; account IDs must not be treated as OS-user isolation.
4. Recovery-safe backup and a migration rehearsal; no direct migration of developer data.
5. Local metadata lookup and all optional network/provider paths governed by the permission centre.

## Required before beta/stable

- Human-reviewed, document-held-out retrieval/evidence gold set and measurable baselines.
- Reviewed feedback bridge; privacy approval, versioned dataset manifests, rollback and deletion policy.
- Safe graph candidate review, source versioning, contradiction display and rebuild/reconciliation strategy.
- Opt-in memory relevance, scoping, expiry and deletion evaluation.
- PDF full-text highlight fidelity and fallback behavior for scans/complex layout.
- Backup/restore, concurrency, crash recovery, long document, duplicate, linked-file and low-disk acceptance.

## Phase 8 boundary

This assessment does not begin Phase 8 implementation. Desktop packaging, orchestration and migration requirements may be mapped in documentation, but runtime code, schema and indexes remain unchanged during this task.

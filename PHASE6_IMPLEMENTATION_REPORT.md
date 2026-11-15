# ResearchLens Phase 6 Implementation Report

## Scope and safety

Phase 6 adds an additive, owner-scoped relational memory layer to the existing SQLAlchemy/PostgreSQL application. It follows Phase 5 revision `0005` with revision `978943c31f5c`. The new migration was upgraded and schema-checked on an isolated temporary SQLite database. It was **not** applied to the configured application database. No library-wide scan, document import, training, external model, cloud service, or Phase 1 serving change was performed.

The Phase 5 reports were reviewed. Current project constraints remain: Phase 5 has no real imported graph data, Phase 4 has not been evaluated on real documents in its report, and Phase 3 has no approved trained model. The memory service reports no eligible inputs for empty selections and requires explicit selected graph IDs for formation.

## Architecture

- `backend/app/models/research_memory.py`: normalized tables for memory records, associations, append-only observation events, graph references, source evidence, contradiction candidates, research gaps, review/feedback events, processing runs, and explicit session opt-ins.
- `backend/migrations/versions/978943c31f5c_associative_temporal_memory.py`: additive migration after `0005`.
- `backend/app/services/research_memory_service.py`: bounded, deterministic formation, source validity checks, idempotency, lexical retrieval, explainable association candidates, conservative contradiction candidates, gap management, temporal history, session capture, feedback, and audit.
- `backend/app/services/research_memory_evaluation.py`: reproducible fixture scoring for retrieval, association false-presentation, contradiction, temporal, and gap behavior.
- `backend/app/routes/research_memory.py` and `backend/app/schemas/research_memory.py`: bearer-authenticated API under `/api/v1/research-memory`.
- `backend/app/services/research_memory_cli.py`: trusted local owner-scoped CLI.
- `backend/tests/test_research_memory.py` and `backend/tests/fixtures/phase6_synthetic_memory.json`: isolated synthetic tests and a hand-judged evaluation fixture.

The seven types are represented by typed memory records: episodic observations, semantic knowledge, source passages, temporal records/events, associative links, contradiction candidates, and research gaps. Supporting normalized tables preserve source and review trails. Session memory is labeled `SESSION` and is separate from source-derived knowledge.

## Evidence and lifecycle rules

Formation accepts only explicitly selected, approved current graph nodes or relationships. For each source, the service reuses Phase 5's owner check, current Phase 4 run check, review-history check, and exact passage/offset validation. Private sources are excluded unless the formation request explicitly opts in. New sources are added; previous source rows are retained. A new extraction run does not overwrite a prior assertion.

Repeated formation is idempotent for the same selected assertions and evidence set. Independent papers are distinguished by source paper IDs; repeated passages from one source do not count as independent confirmation. First observation remains anchored to the graph assertion. Confirmation time uses the reviewed evidence timestamp. Publication dates are left unset when unavailable.

Graph reference versions are recorded. When a reviewed Phase 5 correction changes a referenced node or relationship version, a subsequent explicit formation run appends a correction event with old/new memory snapshots, then refreshes the current memory projection; the old interpretation remains in the event trail.

Association suggestions are not graph edges and are not facts. The initial deterministic signal is shared reviewed graph entities; its configurable constant is `ASSOCIATION_SCORING` in the service. The score is a reproducible ranking signal, not a probability. Candidates require reviewer confirmation before retrieval marks them established.

Contradiction detection is conservative: it only proposes a candidate for opposing, explicitly reviewed `SUPPORTS` and `CONTRADICTS` assertions with identical directed endpoints and current evidence on both sides. It never selects a scientifically correct claim. A reviewer can resolve as `TRUE_CONFLICT`, `CONTEXTUAL_DIFFERENCE`, `NOT_A_CONTRADICTION`, or `UNRESOLVED`.

Memory retrieval keeps direct evidence, graph-supported memories, confirmed associations, suggested associations, contradiction candidates, and research gaps in distinct response fields. Passage evidence is revalidated at retrieval time; stale or missing evidence is suppressed and reported by a read-only audit without erasing its history.

## Privacy and Phase 1 boundary

Memory capture is disabled by default. Session capture requires explicit per-conversation opt-in and an explicit capture request. Captured session queries are labeled `SESSION`, only exact currently valid evidence IDs are retained, and user-created session memories can be inspected or deleted while a review audit record remains. Conversations are never batch-imported, and no conversation data is used for training.

Phase 1's query engine, FTS5 retrieval path, `RAG_ENGINE_MODE`, and default chat behavior are unchanged. Phase 6 exposes a separate API and CLI only; no memory context enters default answers.

## Migration command

After reviewing the target `DATABASE_URL` and backing up the intended database, apply the additive schema with:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

The migration has not been run against the configured database. Memory APIs/CLI require the migration first.

## Verification

See `PHASE6_EVALUATION_REPORT.md` for isolated test and synthetic fixture results. The synthetic fixture is not real-paper evaluation. No real memory accuracy, scientific truth, production latency, or target-hardware throughput is claimed.

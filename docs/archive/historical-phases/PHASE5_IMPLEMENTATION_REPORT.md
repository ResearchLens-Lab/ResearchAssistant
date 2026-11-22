# ResearchLens Phase 5 Implementation Report

## Scope and safety

Phase 5 adds an evidence-backed relational knowledge graph using the project's existing SQLAlchemy/PostgreSQL architecture. Alembic migration `0005` follows `0004`; it is additive and creates eight `kg_*` tables. The migration was applied and checked against an isolated temporary SQLite database. **It was not applied to the configured application database.** No actual research documents were imported, and no existing document, conversation, index, Phase 4 snapshot, or serving behavior was changed.

The import path reads one selected Phase 4 document and run. Only currently approved records whose exact text, page, and offsets validate can enter the graph candidate queue. Imports create pending candidates, never accepted nodes or edges. A human supplies canonical entity type/name or an explicit typed source/predicate/target before graph assertions are accepted.

## Components implemented

- `backend/app/models/knowledge_graph.py`: typed SQLAlchemy persistence models for import runs, canonical nodes, relationships, graph candidates, evidence, aliases, review events, and identity decisions.
- `backend/migrations/versions/0005_knowledge_graph.py`: additive schema migration (`0004` → `0005`).
- `backend/app/services/knowledge_graph_service.py`: owner-scoped import, review, provenance verification, relationship validation, identity suggestions, aliases, merge/undo, bounded traversal/path, temporal assertion status, and read-only auditing.
- `backend/app/schemas/knowledge_graph.py` and `backend/app/routes/knowledge_graph.py`: authenticated API for graph status, explicit import preview/apply, candidate review, node/edge queries, evidence, traversal, corrections, aliases, identity decisions, merge/undo, history, and audit.
- `backend/app/services/knowledge_graph_cli.py`: local owner-scoped import/review/query/audit workflow and optional ontology extensions.
- `backend/tests/test_knowledge_graph.py`: isolated synthetic graph tests.
- `backend/tests/fixtures/phase5_synthetic_graph.json`: clearly synthetic fixture; it is not imported automatically and is never included in any real database counts.

All API routes use the existing authenticated `CurrentUser` dependency. The authenticated user ID scopes every query and is the reviewer identity recorded by the API; client-supplied reviewer names are not trusted. Private Phase 4 records require explicit `allow_private`/`--allow-private` to import or promote. The CLI is intended for a trusted local operator with access to the configured database and Phase 4 artifact directory.

## Graph behavior

Imported approved Phase 4 records are stored as review candidates with extraction run, record/block IDs, page, section, exact text, offsets, extraction method/version, confidence, and privacy flag. The graph stores only the supporting passage, not complete source documents. Accepted node/edge evidence points back to the Phase 4 run and library document.

Every accepted edge has reviewed evidence. Relationship endpoint types are checked against the built-in ontology; custom node/relationship types can be supplied in a local ontology JSON. Self-relations are rejected. The importer does not infer entities or edges from word co-occurrence. Phase 3 models are not required or activated.

Before candidate approval and during graph evidence queries, the service rechecks the Phase 4 review log, exact text/offsets, current successful extraction run, privacy classification, and continued source-document ownership. A later correction, rejection, superseding extraction run, or deleted/unowned source removes that stale evidence from graph query results; the auditor reports the stale assertion. Re-importing unchanged source data is idempotent.

Identity suggestions use exact normalized names, approved aliases, identifiers entered by an authorized reviewer, and bounded string-similarity suggestions. Suggestions never merge automatically. Explicit merge operations preserve and snapshot relationships, aliases, and node evidence; undo restores those mappings and validates edge types before commit.

## Ontology and queries

Built-in node types: PAPER, DOCUMENT, PERSON, ORGANIZATION, INSTITUTION, RESEARCH_GROUP, CONCEPT, DEFINITION, METHOD, ALGORITHM, MODEL, DATASET, METRIC, TASK, PROBLEM, TOOL, SOFTWARE, VENUE, CLAIM, FINDING, EQUATION, REFERENCE_MENTION.

Built-in relationships: AUTHORED_BY, AFFILIATED_WITH, MEMBER_OF, PROPOSES, INTRODUCES, USES_METHOD, USES_DATASET, EVALUATED_ON, REPORTS_METRIC, ADDRESSES_PROBLEM, DEFINES, RELATED_TO, COMPARED_WITH, DERIVED_FROM, CITES, SUPPORTS, CONTRADICTS, EXTENDS, IMPLEMENTS. Directed endpoint compatibility is enforced in the service.

Neighborhood depth is capped at 4, query results at 200, and path searches avoid revisiting cycles. Query results include edge evidence passages and source pages. The same operations support questions such as papers connected to a concept, methods connected through papers evaluated on a dataset, paper authors, and findings related to a problem by using typed relationships, endpoint filters, and bounded paths.

## Persistence and migration

Revision `0005` adds:

1. `kg_nodes` — canonical identity, type, identifiers, review/version state, and first/last observation.
2. `kg_relationships` — directed typed assertions, current/disputed/superseded/retracted state, and observation history.
3. `kg_graph_evidence` — exact reviewed passage and Phase 4/library provenance, with a check requiring one node or edge target.
4. `kg_node_aliases` — manually reviewed aliases.
5. `kg_identity_decisions` — merge, rejection, and undo history with relationship/evidence/alias snapshots.
6. `kg_review_events` — append-only reviewer corrections and decisions.
7. `kg_import_runs` — idempotent source-run import history.
8. `kg_graph_candidates` — imported, approved-source records awaiting graph-level review.

Source document IDs are retained as references rather than foreign keys so deleting a library source does not cascade-delete graph history. Queries hide evidence if its source is no longer owned/available, and the auditor reports broken references.

## Real and synthetic graph status

- Real documents imported by this implementation: **0**.
- Real nodes, edges, and graph evidence written by this implementation: **0**.
- Configured application database migration state: **not changed or inspected for graph rows**; migration `0005` remains unapplied there.
- Synthetic fixtures: used only in tests and the fixture file; excluded from any user graph.

## Verification

- Focused knowledge-graph tests: **11 passed**.
- Full backend/RAG suite: **295 passed in 129.89 seconds**.
- Python compilation: **passed**, `compileall -q backend rag`.
- FastAPI OpenAPI generation lists **22 authenticated knowledge-graph paths**.
- Migration: `alembic upgrade head` and `alembic check` succeeded on an isolated temporary SQLite database; Alembic reported no schema drift.
- No frontend files were changed. No Git commands were run.

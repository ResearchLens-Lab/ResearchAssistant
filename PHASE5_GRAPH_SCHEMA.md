# Phase 5 Graph Schema

The graph is owner-scoped relational data in the existing SQLAlchemy database. PostgreSQL uses the app's JSON variant; SQLite remains supported for tests. All graph IDs are stable UUID strings after creation. No graph database or inference model is introduced.

## Tables

| Table | Purpose |
|---|---|
| `kg_nodes` | Canonical typed entities, normalized identity, identifiers, metadata, review/version state, first/last observation, first source run, and merge target. |
| `kg_relationships` | Directed source/type/target assertions, confidence, review state, current/disputed/superseded/retracted assertion status, version and temporal source fields. |
| `kg_graph_evidence` | Exact source passage and document/paper/run/record/block/page/section/offset provenance. A check constraint requires exactly one target: a node or a relationship. |
| `kg_node_aliases` | Explicitly reviewer-approved aliases, normalized identity keys, and node type. |
| `kg_identity_decisions` | Rejected matches, merge decisions, and undo decisions. Merge snapshots preserve original edge endpoints, node evidence IDs, and alias locations. |
| `kg_review_events` | Append-only old/new values, action, authenticated reviewer, timestamps, and source linkage. |
| `kg_import_runs` | Unique owner/document/Phase 4 run imports, extractor version, input hash, status, timestamp, and candidate count. |
| `kg_graph_candidates` | Approved Phase 4 knowledge records awaiting graph-level human review. Keeps source snapshot and exact offsets unchanged. |

Migration: `backend/migrations/versions/0005_knowledge_graph.py`, revision `0005`, down revision `0004`.

## Node and edge rules

Node and relationship types are strings validated by the service against the built-in ontology or an optional explicit extension configuration. Relationship endpoint pairs are checked before creation and correction. Self-relations are disallowed. Fuzzy name similarity is a suggestion only; there is no automatic merge. People with identical names remain separate unless a reviewer resolves them.

`PAPER` and `REFERENCE_MENTION` are distinct. Phase 4 bibliography entries labeled `parsed_unverified` are not imported as verified papers. Existing Phase 1 DOI verification is untouched and no external DOI lookup is triggered.

## Evidence and active assertion validity

Candidate provenance comes from the latest Phase 4 `DocumentIntelligence` record. The importer validates:

- The document belongs to the authenticated/current library owner.
- The selected run is the current successful Phase 4 run.
- The record review status is approved at import and remains approved at graph review/query time.
- `page[char_start:char_end] == exact_text`, and document/run/block/section IDs match.
- A private-source flag matches the source snapshot and explicit private import consent was provided.

Evidence stores the exact passage, not the full document. Accepted graph evidence records a reviewer and review timestamp. Later Phase 4 review changes, newer extraction runs, or missing library sources make old graph evidence inactive in queries and visible to the audit.

## Time and history

Nodes and relationships preserve first-observed timestamps and source IDs; reviewed supporting records update last-confirmed time. New independent evidence adds another evidence row rather than replacing the first. Assertion status changes and corrections append review events. Merge/undo actions append identity decisions and preserve endpoint/evidence/alias snapshots.

## Ontology extension example

```json
{
  "node_types": ["BENCHMARK_SUITE"],
  "relationships": {
    "VALIDATED_AGAINST": {
      "source": ["METHOD", "MODEL"],
      "target": ["BENCHMARK_SUITE"]
    }
  }
}
```

Pass with global CLI option `--ontology-json path.json`. Extensions are local configuration; they do not alter existing database tables.

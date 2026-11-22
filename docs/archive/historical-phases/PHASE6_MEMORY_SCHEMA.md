# Phase 6 Memory Schema

All user content is scoped by authenticated `owner_id`; optional project scope is `scope_id`. Foreign keys connect to Phase 5 graph assertions and provenance records. Source-document IDs remain references in the same style as Phase 5, so source deletion does not erase retained history.

| Table | Purpose |
|---|---|
| `memory_records` | Typed memory, canonical title/content, status, privacy, version, first-observed and last-confirmed timestamps. |
| `memory_associations` | Directed candidate/confirmed/rejected links, category, explanation, reproducible score components, timestamps. |
| `memory_observation_events` | Append-only, idempotency-keyed creation, source-addition, confirmation, correction, and session events. |
| `memory_graph_references` | Many-to-many references to approved graph nodes and relationships, including the observed graph version. |
| `memory_source_evidence` | Passage text, document/paper, Phase 4 run/record, page/section/offsets, privacy and freshness status. |
| `memory_contradictions` | Competing graph assertions, comparison basis, context, uncertainty, reviewer outcome and time. |
| `memory_research_gaps` | Typed open/resolved questions, scope, inspected sources, reason, and resolution memory. |
| `memory_review_events` | Append-only association, gap, contradiction, feedback, deletion and opt-in review trail. |
| `memory_processing_runs` | Selected scope, evidence-set hash, readiness/counts, and idempotent formation run status. |
| `memory_session_opt_ins` | Explicit per-owner/per-conversation capture opt-in, disabled by default. |

Revision: `978943c31f5c`, down revision: `0005`. Scores are not probabilities. Memory associations are separate from `kg_relationships`; only a human-reviewed Phase 5 operation may add graph edges.

Evidence freshness is checked against current Phase 4 review state and the current successful extraction run through Phase 5. Search suppresses stale passages; `/audit` reports stale references without mutating memory history.

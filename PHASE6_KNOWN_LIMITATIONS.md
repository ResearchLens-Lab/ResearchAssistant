# Phase 6 Known Limitations

- The migration has been tested only on isolated temporary SQLite. The configured application database remains unchanged; apply the migration before using the feature.
- The Phase 5 graph has no real imported evidence. Memory formation is therefore unpopulated until a researcher explicitly imports and reviews graph data.
- Formation uses manually reviewed Phase 5 graph assertions and Phase 4-approved exact passages; it does not independently infer knowledge from all documents.
- Associations currently use shared reviewed graph entities. Lexical overlap, FTS5 association discovery, citation connections, methods/datasets/problem-type signals, and a user-editable scoring profile remain future work. Scores are not probabilities.
- Contradiction candidates cover only explicitly opposed `SUPPORTS`/`CONTRADICTS` assertions on exact matching endpoints. Numeric claim comparison and structured experimental-context compatibility are not implemented.
- Query retrieval is deterministic lexical overlap over a bounded set of memory rows. It does not call an external model, pretrained embedding, or cloud service. Large memory-store latency has not been benchmarked.
- Research gaps are explicitly created through API/CLI; unsupported Phase 1 queries are not automatically logged. The system carefully labels library/document gaps versus potential scientific gaps but does not decide that a broader scientific gap is true.
- Current source-derived formation is owner scoped; project scope is an optional field but this phase has no project-memory partition integration because existing graph entities are owner scoped.
- Session memory is opt-in and separate, but the UI for managing the opt-in and captured memories is not implemented. The API supports inspect/delete and retains audit events.
- There is no Phase 1 integration, frontend, graph visualization, automatic forgetting, training integration, scientific truth verification, or real-paper evaluation in Phase 6.
- Synthetic fixture scores have very small sample counts and demonstrate evaluator behavior only.

# Phase 7 known limitations

- FTS lexical relevance and graph approval are not semantic entailment. Synthesis is evidence retrieval with explicit caveats, not fluent literature review.
- The claim assessor only labels absent retrieved material `NOT_FOUND_IN_LIBRARY`; any retrieved material needs human review. It does not reliably detect support, contradiction, or mixed evidence automatically.
- Comparison dimensions use simple trigger terms against a small retrieved passage set. Cells preserve evidence and numeric strings but may miss content; no metric/unit alignment or winner is inferred.
- Contradiction reporting exposes current Phase 6 candidates and context with `UNRESOLVED`; detailed subject/predicate/metric/time classification remains future work.
- Gap analysis currently detects only an empty local evidence result. It cannot establish literature-wide gaps and does not query external literature.
- Memory associations, temporal summaries, and richer extraction records are not included as factual evidence. The current implementation deliberately avoids conflating associations with direct support.
- Phase 1 FTS retrieval may be unavailable; graph evidence remains usable. Empty scope is safe and never causes an unscoped FTS query.
- The CLI does not implement graph depth traversal; `--max-depth` is presently reserved. Pagination is provided for run history, not evidence expansion.
- The new source quality endpoint records a human profile without an automated rating; records need reviewer evidence and are not quality certification.
- Crossref/OpenAlex responses are public bibliographic metadata, not authoritative proof of scientific validity. Provider behavior, retries, rate limiting, and runtime timeouts need tests.
- The Alembic migration and all code remain unvalidated by an executable project Python environment in this turn. Do not treat this phase as deployment-ready until isolated migration and regression tests pass.

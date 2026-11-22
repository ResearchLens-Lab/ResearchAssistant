# Phase 7 implementation report

## Delivered in this implementation

- Deterministic question classification and comparison/claim sub-question plans.
- Authenticated, account-scoped APIs under `/api/v1/research-intelligence` for readiness, analysis, evidence synthesis, claims, paper comparison, contradiction candidates, DOI verification, explicit public metadata lookup, library-scoped gaps, human quality reviews, and run history/inspection.
- Bounded retrieval through Phase 1 FTS5 with explicitly validated owned/indexed document IDs, plus approved, non-private Phase 5 graph evidence after Phase 4 freshness validation.
- Evidence provenance fields include paper/document, passage, page, section, evidence identifier, review status, retrieval score components, and independent paper count. Same-paper passages are not counted as independent sources.
- Claim assessment is conservative: lexical results never become semantic entailment; absent evidence is not disproof; external state is separate. Assessments are append-only.
- Comparison returns source-linked raw passages and numeric strings. It does not normalize values or declare a winner; comparability is currently conservative and marked insufficient until dimensions are reviewed.
- Existing DOI verification remains explicit; the new public metadata provider calls Crossref/OpenAlex only from the explicit endpoint/CLI command and sends only a DOI or public title query. Failures are represented as unavailable/check failure rather than proof of nonexistence.
- Human quality profiles are separate from bibliographic authenticity and do not produce an automated trust score. Evidence references must be current, approved, non-private, and from the reviewed paper.
- A disabled-by-default adapter is available for explicit Phase 1 integration. No default chat behavior was changed.
- Phase 6 memory search is now optionally included in bounded synthesis output as separately labeled associations, contradiction candidates, and gaps. Missing Phase 6 tables fail safely within a savepoint.
- Additive migration `a8c7d9e2f104` adds research run history, claim assessments, and human source quality reviews.
- A small synthetic unit test set covers deterministic planning, adapter defaults, token normalization, and empty external lookup rejection.

## Not yet complete

This is infrastructure, not a completed production research-intelligence evaluation. Semantic claim entailment, full multi-dimension value extraction, external claim cross-verification, rich contradiction classification, comparative gap discovery, and real-paper evaluation still require human-reviewed records and additional implementation. Phase 7 must not be described as fully complete until the verification guide's outstanding checks pass.

## Safety

No configured application database migration or corpus-wide processing was run. No external lookup is made during local synthesis. No git commands, commits, pushes, browser automation, or model downloads were used.

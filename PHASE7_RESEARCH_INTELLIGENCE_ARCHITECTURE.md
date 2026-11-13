# Phase 7 research intelligence architecture

```text
Authenticated request
  -> deterministic question analyzer
  -> owner-scoped indexed document selection (bounded)
  -> Phase 1 local FTS5 retrieval (optional, read-only)
  -> approved/current/non-private Phase 5 evidence validation
  -> deduplicate passages; count independent papers
  -> structured output + explicit uncertainty + append-only run history
```

Phase 6 contradiction candidates are read only when both assertions and their evidence remain owner-scoped, approved, current, and sourced from distinct documents. Associative memory is not silently blended into factual support. Human source quality review uses a separate append-only record and has no trust score.

Crossref and OpenAlex form an explicit external metadata boundary. The request contains only DOI or user-provided public title metadata. Local passages, PDFs, library scope, and chat history are never sent. Provider snapshots, URLs, query type, timestamps, and errors are retained in run output. Local endpoints do not call these providers.

The Phase 1 adapter is a separate optional class with `enabled=False`; nothing imports it into default chat. Work is bounded by `research_max_documents`, `research_max_evidence`, `research_max_evidence_per_source`, and `research_max_comparison_papers` settings. `max_depth` is accepted by the CLI for forward-compatible interface but graph expansion is not yet implemented.

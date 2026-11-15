# Local Research Intelligence Architecture

## Status

This is the target architecture based on `EXISTING_PHASE1_7_CAPABILITY_AUDIT.md`. It is a design, not a claim that the integrations below are already deployed. The default answer path remains deterministic, local and model-free.

## Ownership and source of truth

The backend `User` owns `Paper` project rows; each `Document` row identifies one uploaded source. A document version is an immutable processing snapshot under that stable document identity. Pages, sections, blocks, chunks, extracted records and citations must refer to that version. A project is a scope/container and never substitutes for the file identity. Every index query uses authenticated owner scope plus explicit project/document scope; missing owner scope fails closed.

## Runtime planes

1. **Local source plane:** original files under the configured local upload root; authenticated backend metadata and processing status; no implicit cloud sync.
2. **Document understanding plane:** page-wise parser output, structure records, extraction confidence/errors, fingerprint and parser/chunker versions. Existing `DocumentIntelligenceExtractor` is reused; it must be moved behind per-owner storage before being invoked automatically.
3. **Search plane:** FTS5 remains the deterministic baseline. Candidate generation can combine FTS5 BM25, exact phrase and metadata/section matches. Optional vector retrieval remains separately configured and must pass the same ownership predicates. RRF or a trained ranker is an experiment until measured against human labels.
4. **Evidence plane:** each retrieval result retains owner, project, document/version, chunk, one-based PDF page, section, locator, exact text and extraction method. A citation is a pointer, not a semantic verification verdict.
5. **Composition plane:** intent and requested format select deterministic answer templates. Comparison retrieves per document. Missing evidence remains visible. Semantic claim verification is marked unavailable unless an approved, validated method is active.
6. **Research graph and memory plane:** current approved SQL graph assertions and opt-in memory are auxiliary evidence sources. Each relation retains source evidence and review state. The standalone Neo4j service is not considered active until its backend boundary is implemented and secured.
7. **Learning/evaluation plane:** local review queue, approved immutable datasets, document-held-out splits, candidate model registry and local metrics. Feedback does not change production behavior unless a reviewed candidate passes gates.

## Query flow (target)

```text
Authenticated request
  -> validate owner and explicit scope
  -> deterministic intent/format planning
  -> retrieve candidates within that scope
  -> deduplicate and balance by document
  -> rank and collect contextual parent blocks
  -> map exact evidence and pages
  -> compose answer with visible support limits
  -> persist run metadata without duplicating source content
```

The current default engine already covers a simplified version of this flow using FTS5, deterministic intent rules, per-document comparison retrieval, extraction and citation mapping. The legacy planner and richer research-intelligence APIs remain distinct until deliberately unified.

## Ingestion flow (target)

```text
Upload -> owner/project validation -> safe local staging -> content fingerprint
       -> page-wise parse -> structure/extraction records with confidence
       -> versioned chunks -> transactional index replacement for that document
       -> consistency check -> indexed status + audit/run record
```

Processing must be bounded per machine. A failed update leaves the previous committed version available until the replacement is verified. No whole-library rebuild is part of upload.

## Extension boundary for a future local model

Define an optional adapter interface for separately approved local inference. It must be disabled by default, load only an explicit locally installed artifact, receive only the minimum selected evidence, and emit provider/model/call metadata. This phase performs no model download, training, load or invocation. Retrieval and citations remain authoritative if such an extension is approved later.

## Current-to-target status

- **Already implemented:** local upload files, owner-scoped backend records, default FTS5 ingestion/query, deterministic composer, citation mapping, reviewable graph/memory models, local dataset/readiness tooling.
- **Partially implemented:** page-aware parsing, research planner and claim checks, graph/memory, local training registry, evaluation metrics.
- **Not integrated:** structured extraction in standard ingestion; product feedback to reviewed training queue; Phase 2/3 models in the default intent/retrieval path; one unified research orchestrator; standalone Neo4j backend client.
- **Not verified:** OS-account data separation, encryption at rest, complete offline operation, production backups, full document-version rollback.

# Research Quality Evaluation Framework

## Existing assets and limits

`rag/evaluation/` contains retrieval/answer metrics, a runner and fixture datasets. The Phase 1 independent corpus labels itself synthetic/hand-authored. Such fixtures can validate deterministic mechanics, citation ID behavior and regressions, but cannot establish accuracy on users’ research documents. Keyword overlap, expected-term coverage and citation existence are not semantic claim-support measures.

## Authorized golden-set schema

Each human-reviewed case should contain: opaque case ID; question; intent; explicit scope; relevant owner-local document/version IDs; relevant passage/chunk IDs; one-based PDF page and optional verified printed page; required factual points; requested format; abstention expectation; reviewer and review timestamp; dataset version; and an explicit permission class. Do not export source content or identifiers to shared datasets without permission.

## Metrics

**Retrieval:** Precision@K, Recall@K, MRR, nDCG@K, relevant-evidence coverage, selected-document coverage, duplicate/overlap rate, header/footer rate and per-document balance. Use reviewer relevance labels as ground truth.

**Answer:** intent accuracy, required-point coverage, format compliance, unsupported-claim rate, citation validity, page validity, citation-to-claim association, duplicate content and appropriate abstention. Mechanical measures must be identified as proxies; claim-to-passage meaning requires human review unless a separately approved local evaluator is validated.

**Security/performance:** zero cross-owner candidate/citation access; unauthorized document rejection; scope preservation; per-file peak memory, ingestion/query latency, cancellation behavior and index consistency.

## Improvement gate

Freeze a document-group split before training/tuning. Compare candidate with baseline on the same held-out cases and report per-intent/per-project results and confidence/variance. Reject changes that reduce retrieval/citation/security or increase irrelevant evidence/unsupported answers. Retain baseline and rollback artifact. Never create synthetic answers and label them verified gold. Current checked-in synthetic corpora remain regression fixtures only.

## Current status

Metrics and regression runners exist. A human-reviewed, authorized production golden set and a full citation-to-claim association benchmark were not established by this audit. No candidate quality improvement is claimed or measured in this task.

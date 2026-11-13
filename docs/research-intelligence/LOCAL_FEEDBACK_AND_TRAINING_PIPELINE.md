# Local Feedback and Training Pipeline

## Existing foundation

`rag/training/schema.py` defines task labels, source/page/chunk provenance, annotator/reviewer, approval status, dataset version and private-source training permission. `DatasetStore` keeps a local pending queue and exports immutable approved JSONL snapshots. Readiness/split tooling rejects synthetic or insufficient data; NLP adapters load only approved/checksummed models and otherwise report a deterministic fallback. This is a credible base, not a connected user-facing learning loop.

Backend research-memory feedback and graph review APIs are separate. They do not automatically create approved training records. No ordinary answer interaction should become training data.

## Target lifecycle

1. Collect explicit feedback under authenticated owner scope: wrong source, missing evidence, incorrect page/citation, incomplete answer, wrong format, incorrect answer or useful answer.
2. Keep feedback out of training by default. An explicit “approve for local evaluation/training” action is required; private source permission is separate from feedback submission.
3. Store a minimal query/run/source ID reference. Avoid copying PDFs or full passages into every example; materialize text only in an approved local export operation.
4. Require reviewer, review timestamp, corrected label/output, source document/version/page/chunk, task, dataset version, privacy class and consent record before approval.
5. Export immutable versioned snapshots with checksum, class balance and document-group split manifest.
6. Train/evaluate only on a local CPU-capable task-specific component. Never auto-promote. Keep baseline and rollback artifact.

## Candidate tasks and sufficiency

Possible candidates: intent classification, section classification, passage relevance, entity/relation classification and metadata field selection. A model is not useful if it lacks enough independent documents or balanced reviewed labels. Readiness should report exact annotation shortfalls; no examples are fabricated to meet a threshold. Splits must group by document/project to avoid adjacent-chunk leakage.

## Data boundary and status

The current default dataset path is local to the checkout but not per-user isolated, encrypted or exposed through an authenticated approval UI. Do not place private examples in shared fixtures. A secure feedback API/store and explicit export permission are **not implemented**. Requires privacy/storage design before integration.

# ResearchLens Phase 2 Dataset and Annotation Guide

## Format

Each line is one UTF-8 JSON object validated by `DatasetExample` in `rag/training/schema.py`. Core fields:

| Field | Meaning |
|---|---|
| `example_id`, `task_type` | Stable identifier and one of `intent`, `entity`, `passage_relevance`, `evidence_sufficiency`, `claim`, `relationship`. |
| `input_text`, `candidate_passage` | Question/context and optional candidate evidence text. Passage ranking requires a candidate passage. |
| `expected_label`, `expected_output` | Task-constrained label and optional structured expected output/span. |
| `source_document_id`, `paper_id`, `page_number`, `chunk_id`, `provenance` | Traceable source locator and annotation provenance. Passage/evidence/claim/entity/relationship rows require document, page, and chunk. Intent-only rows may use an annotation provenance note and a document grouping key. |
| `annotator`, `reviewer`, `created_at`, `reviewed_at`, `review_status` | Annotation and review audit fields. Status is `pending`, `approved`, or `rejected`. |
| `dataset_version`, `source_group_id` | Version and group used to keep one paper/document in a single split. |
| `private_source`, `training_permission` | Prevent accidental use of private material. Both source privacy and explicit approval are recorded per example. |

Allowed labels are enforced by task. Relevance is graded `0` to `3`; evidence is `sufficient`, `insufficient`, `conflicting`, or `partial`; claims are `supported`, `contradicted`, `neutral`, or `unsupported`; entity and relationship labels are enumerated in `schema.py`.

## Workflow and files

1. Add annotations to the pending queue using the CLI or `DatasetStore.add`.
2. Inspect pending rows with `list-pending`; correct or reject each row using `review`. Every review action writes its previous value/action to `correction_history.jsonl`.
3. Export only approved rows to `versions/<version>/approved.jsonl`. An immutable manifest records count and SHA-256. Reusing a version is rejected.
4. Run `validate_dataset`; fix duplicates, contradictions, missing provenance, unresolved review state, and class imbalance warnings.
5. Freeze a split manifest by paper/document, then train on `train` only. Validation is for model choices; test must stay untouched until final evaluation. A changed dataset requires a new dataset version and manifest.
6. Register a trained model as a candidate, inspect held-out metrics against the deterministic baseline, and explicitly approve only a measurable improvement. Otherwise keep the deterministic fallback.

Default local annotations live under `rag/training/local_data/` when using the sample CLI command. That directory is intentionally not pre-populated with private documents and should be access-controlled/backed up according to project policy.

## Leakage and quality rules

- Split by `source_group_id`, paper ID, or source document ID, never by random chunk.
- At least three independent document groups are needed to produce train/validation/test partitions.
- Duplicate task/input/passage pairs are rejected; conflicting labels for the same example require reviewer resolution.
- Private-source rows are blocked unless the reviewer records explicit training permission.
- Rows with missing source provenance are reported by task-aware validation.
- Frozen manifests record example IDs and dataset content hash; they refuse changed labels/content or document overlap.
- Synthetic fixtures and results live under `rag/training/fixtures/`, not in real-paper gold evaluation.

## Dataset example

```json
{"example_id":"ex-001","task_type":"passage_relevance","input_text":"What method was used?","candidate_passage":"We evaluated the method with cross-validation.","expected_label":"3","expected_output":{"relevance":3},"source_document_id":"doc-17","paper_id":"paper-4","page_number":5,"chunk_id":"doc-17-c12","provenance":{"annotation":"manual passage judgment"},"annotator":"researcher","reviewer":"reviewer","created_at":"2026-10-01T12:00:00Z","reviewed_at":"2026-10-02T12:00:00Z","review_status":"approved","dataset_version":"v1.0.0","source_group_id":"paper-4","private_source":false,"training_permission":false}
```

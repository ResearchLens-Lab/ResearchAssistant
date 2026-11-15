# ResearchLens Phase 2 Training Results

## Measured smoke run

Command: `.venv\Scripts\python.exe -m rag.training.smoke_run`

The run uses the explicitly synthetic 30-example fixture in `rag/training/fixtures/phase2_smoke.jsonl`. It contains six synthetic document groups, three intent examples per group, and two relevance judgments per group. The frozen split is 20 train examples / 5 validation / 5 test, with 4 / 1 / 1 independent document groups. The test sample is deliberately tiny; these figures are a plumbing smoke check, not a generalization estimate.

| Task / measure | Trained model | Deterministic baseline | Held-out support |
|---|---:|---:|---:|
| Intent accuracy | 1.000 | 0.667 | 3 examples, one per class |
| Intent macro F1 | 1.000 | 0.500 | Same 3 examples |
| Intent per-class precision/recall | 1.000 / 1.000 for each of 3 classes | Baseline confusion matrix is included in JSON | One case per class |
| Passage Recall@2 | 1.000 | 1.000 | 1 query group, 2 candidate passages |
| Passage MRR | 1.000 | 1.000 | Same one query group |
| Passage NDCG@2 | 1.000 | 1.000 | Same one query group |

Dataset schema/provenance checks passed; there were no duplicate/conflicting annotations, missing provenance, or class-imbalance warning on this fixture. Detailed confusion matrices and per-class results are in `rag/training/fixtures/phase2_smoke_results.json`.

The intent result is better than the deterministic baseline on this tiny held-out fixture, while passage ranking ties the baseline. **No model was activated.** One test document and one ranking query are insufficient grounds to deploy; the test set is retained only as a smoke test. No real-document model evaluation has been performed, so no production performance claim is made.

## Validation performed

- Synthetic training/evaluation command completed and wrote its results JSON.
- Focused training infrastructure suite: **13 passed** in the final run.
- Existing backend/RAG regression suite, including the final safeguards: **259 passed in 110.09 seconds**.
- Python compilation of `rag/training`: passed.
- Frontend was not modified, so frontend test/lint/typecheck/build were not rerun for Phase 2.

## Current artifacts

- `rag/training/fixtures/phase2_smoke.jsonl`
- `rag/training/fixtures/phase2_smoke_split_v2.json`
- `rag/training/fixtures/phase2_smoke_results.json`

These are synthetic development fixtures and must not be mixed into manually verified real-document evaluation results.

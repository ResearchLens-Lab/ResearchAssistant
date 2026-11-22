# ResearchLens Phase 3 Model Evaluation

## Trained model results

**No Phase 3 entity or relationship model was trained.** The local annotation store contains zero approved real examples and the only available fixture is synthetic. Reporting model precision, recall, F1, confusion matrices, false-positive/negative examples, or per-type scores as if they were real performance would be misleading.

| Component | Real train / validation / test examples | Independent real papers | Candidate / approved | Real-data metrics |
|---|---:|---:|---|---|
| Token-level entity recognizer | 0 / 0 / 0 | 0 | None / None | Not measured |
| Relationship extractor | 0 / 0 / 0 | 0 | None / None | Not measured |

The Phase 2 30-row synthetic fixture is excluded and is not a Phase 3 gold set. Unit tests validate the code paths and safety behavior; they are not model evaluation and do not create reported model scores.

## Evaluation available once data passes readiness

- Entity: exact-span micro precision/recall/F1, per-entity-type exact scores, token BIO confusion matrix, malformed/invalid BIO count, and comparison to an all-O deterministic baseline.
- Relationship: multi-label micro/macro precision/recall/F1, per-relation 2×2 confusion matrices, false-positive and false-negative examples, explicit `NO_RELATION` precision/recall, and comparison to a deterministic all-`NO_RELATION` baseline.
- Dataset size and independent document count accompany each evaluation report. Frozen train/validation/test assignments are document-level and content-checked.
- Relationship confidence threshold is selected on validation only. The held-out test partition is evaluated separately after candidate training and is required for explicit registry approval.

## Verification

The focused NLP and Phase 2 training-infrastructure tests passed: **28 passed**. The complete backend/RAG regression suite passed: **274 passed in 113.03 seconds**. Python compilation passed. These are implementation/regression checks, not entity or relationship performance scores.

No candidate artifact exists in the project model registry; the registry directory was absent during inspection. Test-created temporary registry artifacts were confined to pytest temporary directories.

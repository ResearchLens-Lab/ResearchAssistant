# ResearchLens Phase 3 Dataset Readiness

## Inspection performed

Command: `.venv\Scripts\python.exe -m rag.training.nlp.cli readiness`

Inspected the configured default Phase 2 annotation store at `rag/training/local_data/` and the separately stored Phase 2 fixture. The command is read-only and does not create the absent annotation store.

| Readiness item | Observed value |
|---|---:|
| Local annotation store | Absent |
| Pending / approved / rejected local annotations | 0 / 0 / 0 |
| Approved real examples: intent | 0 |
| Approved real examples: entity sequence labels | 0 |
| Approved real examples: passage relevance | 0 |
| Approved real examples: evidence sufficiency | 0 |
| Approved real examples: claim labels | 0 |
| Approved real examples: relationship labels | 0 |
| Distinct real source papers/documents for Phase 3 tasks | 0 |
| Reviewed entity spans and per-type labels | 0 |
| Labelled entity-pair relations, including `NO_RELATION` | 0 |
| Valid frozen real-data train/validation/test split | Not available; no real approved dataset exists |
| Private annotations / missing explicit permission | 0 / 0 |
| Phase 3 examples with missing required provenance | 0 |

The repository contains the separate Phase 2 synthetic fixture: **30 examples** (18 intent and 12 passage-relevance), six synthetic groups, zero entity spans, and zero relationship pairs. The readiness tool reports all 30 as synthetic and excludes them; they are not real labels and are not used for Phase 3 training or evaluation.

## Decision

Entity recognition: **not ready**. It needs at least 50 approved real task examples across five or more identifiable source documents, at least 50 exact-offset spans across two or more entity types with five examples per type, complete provenance, explicit private-data permissions, and a valid frozen document-level split.

Relationship extraction: **not ready**. It needs at least 50 approved real pair annotations across five or more source documents; at least one positive relation and reviewed `NO_RELATION` examples; at least five annotations per observed label; complete provenance/permissions; and a valid frozen split.

No model training or candidate registration was attempted. The gates are implemented and the trainer raises a readiness error before estimator fitting when the real reviewed dataset is insufficient.

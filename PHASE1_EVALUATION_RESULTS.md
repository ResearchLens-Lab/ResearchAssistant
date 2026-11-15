# ResearchLens Phase 1 Evaluation Results

## Dataset

The fixed gold set contains **30 hand-authored question/evidence cases** over eight short synthetic passages. It covers author lookup, definitions, direct facts, numerical values, dates, comparisons, summaries, methods, datasets, metrics, pros/cons, lists, evidence lookup, paraphrases, one unsupported question, and cross-document metric differences. No private user upload was used as training data.

The run is reproducible with:

```text
.venv\Scripts\python.exe -m rag.evaluation.run_phase1_evaluation
```

Detailed per-case output is in [`rag/evaluation/phase1_evaluation_run.json`](rag/evaluation/phase1_evaluation_run.json); the labelled set is [`rag/evaluation/phase1_independent_dataset.json`](rag/evaluation/phase1_independent_dataset.json).

## Measured results

| Measure | Result | Denominator / definition |
|---|---:|---|
| Intent accuracy | 100% | 30 questions |
| Recall@5 | 100% | 29 answerable questions; at least one expected chunk retrieved |
| MRR | 0.9828 | 29 answerable questions; rank of first expected chunk |
| Citation correctness | 100% | 30 cases; citations resolve to returned evidence IDs, abstention has no citation |
| Evidence coverage | 100% | All expected gold chunks were cited |
| Physical page accuracy | 100% | 25 cases with an expected page |
| Extraction correctness | 100% | 29 answerable questions; expected fact appears in the answer |
| Abstention accuracy | 100% | 1 unsupported question |
| Conflicting evidence surfaced | 3/3 | Three labelled cross-paper metric-difference cases |
| Mean / p95 query latency | 4.9 ms / 9.7 ms | Warm engine over the tiny eight-passage fixture |

These perfect scores are a result on a small, controlled, hand-authored fixture set. They are not a production accuracy estimate. The synthetic latency excludes process startup, PDF parsing, and large-corpus indexing. On the active indexed book, a single warm query took approximately 0.47 seconds in this environment.

## Real corpus smoke check

The independent engine was separately run against the selected indexed *Introduction to Algorithms* source. It retrieved the physical page 25 definition passage, produced the input/procedure/output structure, and returned `STRONGLY SUPPORTED`. Author lookup retrieved the four title-page authors and marked the extraction for review. These are manual spot checks and are not included in the 30-case metrics.

The cross-paper detector intentionally reports different metric values as “conflicting evidence” for review. It does not claim that the papers’ test conditions are scientifically equivalent.

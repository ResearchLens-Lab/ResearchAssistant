# Phase 4 Evaluation Report

## Executed checks

| Check | Result |
|---|---:|
| Focused Phase 4 fixture tests | 10 passed |
| Full backend + RAG regression | 284 passed, 112.57 s |
| Python compile check | Passed (`compileall -q backend rag`) |
| Existing real-document quality evaluation | Not run; no real documents were selected |

The ten tests use synthetic text or generated empty DOCX/PDF containers and a stubbed OMML output. They verify code behavior only. They are not real-document gold labels and do not estimate extraction precision or recall.

## What is measured

Tests check deterministic IDs and repeat runs, section hierarchy, exact evidence/offset matching, pending review state, parsed reference fields and citation-page links, unverified bibliography status, DOCX equation order with unknown page position, explicit image-only-PDF `needs_ocr`, failure recovery without replacing the successful run, and review correction validation.

The implementation records per-run extraction duration. No representative real document was selected, so no valid throughput or target-machine memory measurement is available. The existing PDF parser loads a normalized document before extraction, so Phase 4 does not claim bounded page-batch memory for large PDFs.

## Not meaningfully measurable yet

There is no manually reviewed Phase 4 gold set and no real source document was selected for this task. Accordingly, metadata accuracy, section precision/recall, reference field accuracy, table preservation rate, figure caption accuracy, equation coverage, and knowledge-candidate precision/recall remain **not measured**. Phase 3 has no approved trained model, so entity precision/recall is **not applicable**. The implementation validates evidence offsets deterministically in fixtures; that does not prove semantic claim entailment.

## Reproducible workflow for future evaluation

1. Select a small, consented set of papers and process only those document IDs with the CLI.
2. Have reviewers label title/authors/year/DOI, section spans/classes, bibliography entries and in-text links, native tables/figure captions/equations where available, and exact evidence candidates.
3. Keep the gold annotations separate from extraction output and split by document/paper before scoring.
4. Report field-level exact match and precision/recall/F1 where labels support it, plus evidence-provenance validity, duplicates, malformed records, run time, and peak memory.
5. Report parser-specific coverage and OCR exclusions separately. Never mix synthetic fixtures with real-paper scores.


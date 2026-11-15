# ResearchLens Phase 4 Implementation Report

## Scope and safety

Phase 4 adds opt-in structured extraction through the existing `DocumentLoaderFactory` and `DocumentNormalizer`. It does not add a second ingestion/indexing path, alter regular uploads, attach extraction to search or answer generation, or change Phase 1 serving. No database tables, migrations, indexes, conversations, or existing documents were changed. Extracted artifacts are stored separately under the ignored local directory `rag/document_intelligence/local_data/`; no library-wide processing was run.

The implementation uses deterministic rules and the existing DOCX OMML equation converter. It downloads no model, makes no external calls, and does not activate Phase 3 models. Records are extraction candidates, not verified facts; all knowledge records start `pending`, and confidence is kept separate from review status.

## Components

- `rag/document_intelligence/models.py`: normalized document, page-local blocks, hierarchical sections, knowledge candidates, references, equations, provenance positions, and append-only review event schema.
- `rag/document_intelligence/extractor.py`: parser adapter, deterministic section classification, abstract/keyword capture, list/paragraph/heading/caption/reference blocks, conservative knowledge-pattern candidates, citation markers, bibliography parsing, OCR-state handling, and capability reporting. Stable IDs are SHA-256-derived from document identity and source position/content; the run ID also includes input content hash and extractor version.
- `rag/document_intelligence/store.py`: atomic, versioned JSON snapshots; idempotent writes; current successful run pointer; run history; failed-run metadata; and append-only review/correction events. A failed run does not replace the last successful run.
- `rag/document_intelligence/cli.py`: explicit selected-file extraction, display, run history, per-document review queue, and approve/reject/correct commands.
- `rag/tests/test_phase4_document_intelligence.py`: ten synthetic fixture tests for hierarchy, offsets, citations/references, equations, OCR, repeatability, review validation, and failed-run recovery.

The artifact store retains the parser-normalized page text with extracted records because reviewers need to validate evidence against the exact offset basis. Offsets address Unicode character positions in the existing normalized page text, not PDF byte offsets or screen coordinates.

## Supported inputs and current structure

The adapter accepts the formats already routed by the project's loader: PDF, DOCX, TXT, Markdown, TeX, CSV, XLSX, PPTX, JSON, HTML, and HTM. A format may still fail when its optional parser dependency is not installed or the input is malformed.

- Page text, filename/type, existing title/authors/year/DOI metadata, page count, headings, paragraphs, list-like lines, abstract text under a classified abstract heading, and explicit keyword lines are represented where those values are available from the current parser.
- Section aliases are conservative. The original heading is retained; unknown headings use `unknown`/`needs_review`. Hierarchy follows explicit Markdown or numeric heading depth when present.
- Rules surface exact source sentences as low-confidence candidates for research questions, objectives, problems, definitions, methods, models, datasets, tools, metrics, settings, findings, claims, limitations, contributions, and conclusions. They do not paraphrase evidence.
- Numbered references are parsed for raw text, likely authors/title/year/DOI/URL and linked to matching numeric in-text markers. Every bibliography entry is marked `parsed_unverified`; external DOI verification is never called.
- DOCX equations are extracted through the existing OMML converter. The source converter gives document order but not page or character coordinates; those positions remain null and this limitation is shown in each equation record.
- Image-only PDFs rejected by normal ingestion are recognized by this opt-in command and saved as `needs_ocr`. OCR is not installed/integrated by this phase.

The current shared parser often flattens DOCX/PPTX/CSV/XLSX tables to text and does not expose stable cell positions. Phase 4 reports this capability gap instead of claiming preserved rows/columns. PDF figures are not interpreted; only text-shaped caption lines may be classified as captions. Figure image references, visual descriptions, PDF table structure, and reliable PDF equations are unavailable. No LaTeX is inferred from plain text.

## Commands

Run from the project root. `--file` and `--document-id` select exactly one source; extraction is never automatic.

```powershell
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli extract --document-id DOC_ID --paper-id PAPER_ID --file "C:\path\paper.pdf"
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli extract --document-id DOC_ID --file "C:\path\private.pdf" --private
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli show --document-id DOC_ID
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli runs --document-id DOC_ID
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli review-queue --document-id DOC_ID
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli review --document-id DOC_ID --run-id RUN_ID --record-id RECORD_ID --action approve --reviewer "Researcher"
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli review --document-id DOC_ID --run-id RUN_ID --record-id RECORD_ID --action correct --reviewer "Researcher" --correction-json '{"category":"finding"}'
```

Review corrections retain history and must still match source-page offsets and exact evidence. There is no API or training-data export in this phase. Extracted documents never become training data. A future manual export needs a defined label mapping and a distinct explicit privacy/permission gate; automatically assigning model labels from these rules would create false training labels.

## Verification

- Focused Phase 4 suite: **10 passed**.
- Full backend and RAG suite: **284 passed in 112.57 seconds**.
- Python compilation: **passed**, `python -m compileall -q backend rag`.
- No frontend files changed, so frontend checks were not run.
- No Git commands were run.

The fixture suite is synthetic software verification, not a document-quality benchmark. No user library or real research paper was read for Phase 4 evaluation.

# Document Understanding Specification

## Existing implementation

`rag/ingestion/document_loader.py` supports PDF, DOCX, plain text/Markdown/TeX, CSV, XLSX, PPTX, JSON and HTML adapters (some require optional packages). PDF uses PyMuPDF and yields page-wise text with one-based PDF page numbers. Scanned PDFs currently fail with an explicit OCR-not-enabled error. The standard pipeline normalizes pages and chunks them; it does not currently invoke `rag/document_intelligence/extractor.py`.

The separate Phase 4 extractor emits `DocumentIntelligence` JSON: page/block/section structure, heuristic knowledge records, reference candidates, equations, content hash, extraction version/status and quality issues. It has a separate filesystem `ExtractionStore` and CLI. It is not a transactional extension of the owner-scoped upload/index records. Tables are not preserved as reliable row/cell structures; figure visual interpretation is explicitly unavailable. These outputs are candidates, not verified facts.

## Target record contract

For every source version, persist: stable document ID; owner/project; content SHA-256; monotonically assigned version; parser/extractor/chunker/schema versions; processing/extraction/index status; start/end timestamps; file type; extraction errors; page count; page text and extraction method; structural blocks with character offsets; sections with hierarchy; exact source locator; and a quality/confidence status. Retain original bytes unchanged until user deletion policy says otherwise.

Logical structure should be linked, not duplicated: `DocumentVersion -> Page -> Section/Block -> Paragraph/Sentence -> Table/Row/Cell or Figure/Caption/Equation -> Chunk -> ExtractedRecord -> Evidence`. A chunk keeps parent IDs and page/section context. Only entities supported by a parser are populated; unsupported visual/equation structure is marked unavailable.

## Parsing policy

- **PDF:** extract native text page by page and preserve order as returned by parser. Record blank/low-text pages. Never silently OCR. If a future local OCR plugin is explicitly enabled, retain OCR engine/version, confidence and separate OCR text from native text.
- **DOCX/PPTX/CSV/XLSX:** preserve the existing supported structures when accessible; keep table headers attached to cell values. Do not execute formulas, macros or embedded content. Report omitted shapes/notes/formulas.
- **HTML/JSON/text:** sanitize according to the current parser; retain file-local positions when possible and label synthetic page boundaries as synthetic.
- **Bibliography:** distinguish file metadata, first-page text, user-confirmed metadata and parsed references. Store per-field source and verification status. Parsed bibliography data remains unverified until reviewed.
- **Scans, damaged files and unsupported data:** return explicit partial/needs-review status and parser error; never assert completeness.

## Incremental ingestion and versioning

Fingerprint the staged file before parse. If the same owner already has the same fingerprint, offer reuse/duplicate handling without creating duplicate chunks. New bytes for an existing document create a new version; do not overwrite old evidence pointers until the new extraction and index transaction pass integrity checks. Delete stale chunks only within the target document/version boundary after commit. Existing indexes must be inspected and migrated additively; no collection recreation or uncontrolled reindex.

## Confidence and review

Parser output confidence is about extraction, not factual truth. Rule-derived category labels should default to `candidate/needs_review`; citations/reference links are unresolved until verified. A human correction records actor, prior/new value, source locator, timestamp and explicit training permission. No OCR threshold or confidence score is promoted to factual support automatically.

## Implementation status

- **Already implemented:** page-aware PDF loader, broad file adapters, page/section chunk metadata, Phase 4 JSON model/extractor/store/CLI.
- **Partially implemented:** heading classification, references, equations and extraction quality flags.
- **Not implemented:** automatic owner-scoped Phase 4 integration; first-class paragraphs/sentences/table cells/figures; OCR; page printed-number mapping; stable document-version/fingerprint fields in the backend schema; metadata provenance per field; controlled replacement workflow.
- **Requires human review:** authors/title/year/DOI inferred from parsed text; extracted knowledge claims; bibliography linkage; OCR text.

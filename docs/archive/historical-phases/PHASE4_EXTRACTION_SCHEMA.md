# Phase 4 Extraction Schema

Schema version: `1.0`  
Extractor version: `phase4-rules-1`

## Document snapshot

Each immutable run snapshot contains:

- `document_id`, `paper_id`, filename/type, existing metadata fields, `private_source`, `page_count`, `content_hash`, `run_id`, `extraction_version`, duration, and status (`complete`, `partial`, `needs_ocr`, or `failed`).
- `pages[]`: parser-normalized page number and exact normalized page text, which is the basis for all character offsets.
- `structure_capabilities`: explicit status/limitations for page text, offsets, tables, figures, and equations, based on the input format.
- `sections[]`: stable section ID, exact heading, conservative classification, classification state, level, parent section ID when inferable, page span, and collected section text.
- `blocks[]`: stable block ID, type, exact block text, page-local `char_start`/`char_end`, section link, and classification state. Supported block types currently include heading, paragraph, list item, reference, caption, and table-like text. A text block does not imply native table/image structure.
- `knowledge_records[]`: exact evidence, category, stable ID, document/page/section/block provenance, page-local offsets, extraction method/version, confidence, uncertainty, and review state. Defaults are `pending` and confidence `0.55` for deterministic pattern matches.
- `references[]`: raw bibliography line and parsed candidate fields, page-local offsets, citation pages, `cited_in_text`, and `bibliographic_status=parsed_unverified`.
- `citation_markers[]`: marker text/key, page-local offsets, page and section. Citation links are lexical numeric links, not bibliographic verification.
- `equations[]`: existing DOCX OMML converter output and document order. Page/character positions are null because the source converter does not supply them.
- `quality_issues[]`: OCR gaps, incomplete references, unmatched numeric citations, uncertain headings, and any evidence integrity issue detected.

## Identity and versioning

- Block IDs derive from document ID, block kind, page, and page-local start position.
- Knowledge record IDs derive from document ID, category, page, start position, and exact source text.
- Section/reference/equation IDs are deterministic from document identity and their available source position/order.
- Run IDs derive from document ID, source content SHA-256, and extractor version. Reprocessing unchanged input with the same version returns the existing snapshot. A changed input or extractor version creates another snapshot.
- Snapshots are written atomically. A current pointer references only a successful extraction. Failed attempts are stored as small failure manifests and do not overwrite that pointer.

## Review and validation

Review events store actor, time, action, previous value, corrected value, run, record, and optional training-permission declaration. Approved status does not change confidence. Corrections must keep record/document identity and their evidence text must match the cited source page at the corrected offsets. Review history is append-only; the CLI materializes the latest updates when showing a run.

No extraction record is exported into Phase 2/3 datasets. Rule labels are not gold annotations, and the current project does not define a safe mapping from these knowledge categories to Phase 2/3 training labels.

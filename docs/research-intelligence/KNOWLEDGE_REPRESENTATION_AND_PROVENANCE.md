# Knowledge Representation and Provenance

## Current representation

The application has separate records for user, project (`Paper`), uploaded `Document`, and indexed chunks. `ChunkMetadata` currently includes owner, paper/project, document, section, physical PDF page range, title/filename/locator and arbitrary extras. The Phase 4 JSON artifact adds page/block/section/knowledge/reference/equation records with offsets and an extraction version. The SQL graph and memory schemas retain owner scope and links to evidence. These are useful building blocks but are not yet one version-aware hierarchy.

## Canonical evidence identity

The canonical reference should be `(owner_id, document_id, document_version_id, chunk_id)`. A citation also carries `paper_id` as project context, `page_index` (one-based PDF viewer page), optional printed page only when mapped, section/block IDs, exact text, character offsets where parser-safe, parser/version provenance and a citation locator. Chunk IDs must not be repurposed across changed document content. Existing stable document IDs remain; new version IDs are additive.

## Attribution model

Every extracted assertion must carry one explicit origin class:

- `source_statement`: text stated by the current source author;
- `cited_prior_work`: a statement attributed by that source to another work;
- `author_interpretation`: the source author's interpretation;
- `researchlens_candidate`: a deterministic extraction/classification, not reviewed;
- `human_reviewed`: a reviewed correction with reviewer and timestamp.

An in-text citation is not proof that a claim is from the current paper. Graph edges and memory associations must retain assertion class, review state, extraction run and supporting page/chunk. Only current, approved assertions may be used as established graph facts.

## Page and citation semantics

Use one-based PDF viewer page for parser page values because `PDFDocumentLoader` numbers pages from 1. Keep any zero-based internal offsets in separate fields. Printed page numbers are distinct and optional; never synthesize them from PDF page order. If text matching cannot resolve a highlight reliably, open the page without claiming a highlight match.

## Consolidation plan

1. Define version and locator contracts before adding schema fields.
2. Add nullable version/provenance fields with migration and rollback rehearsal; old chunks remain readable as `legacy-unversioned`.
3. Store extraction JSON under owner/document/version access control or an owner-filtered database store; do not leave sensitive structured records in an unscoped shared directory.
4. Make citations resolve through the canonical tuple and validate owner/version before returning content.
5. Retain Phase 5/6 evidence IDs only when they resolve to a current document version; obsolete evidence is marked stale, not silently rebound.

## Status

- **Already present:** owner ID at chunk/index boundary; document and project IDs; page, section and exact chunk text; source citations; graph/memory evidence references and review events.
- **Partially present:** extraction offsets, extraction version/hash, candidate/review status in the standalone Phase 4 store.
- **Missing:** canonical document version; cross-store transaction; printed pagination mapping; consistent source extraction provenance in chunk/citation APIs; stale evidence invalidation for document replacement.

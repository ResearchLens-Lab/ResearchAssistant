# ResearchLens Phase 1 Known Limitations

- Intent understanding, synonym expansion, and entity extraction are deterministic rules. They are explainable and testable, but they are not a trained ResearchLens model and may miss new phrasing or domain terms.
- The 30-case evaluation set is small and synthetic. Its perfect exact-match scores do not predict performance across user documents, OCR quality, layouts, or disciplines.
- Retrieval is lexical. BM25, TF-IDF, metadata signals, and curated synonyms work well for exact terminology but can miss semantically related passages with different vocabulary.
- Evidence validation checks source IDs, provenance, exact text presence, and lexical conditions. It is not a semantic entailment proof; a source passage can contain the cited words while failing to support a subtle interpretation.
- Numerical conflict detection is heuristic. It associates a metric label with nearby numeric values and does not normalize units, datasets, populations, protocols, or statistical significance. It surfaces differences for review rather than resolving them.
- Author extraction is deliberately conservative and always marks title-page/bibliographic patterns for human review. OCR errors, unusual ordering, multi-part names, and books without an edition/byline structure can still cause omissions or ambiguous candidates.
- Long-document summaries cover retrieved passages, not every chapter or finding. Increasing top-K can improve coverage at additional memory and response cost.
- Independent-mode uploads are FTS5-only: they do not create Chroma vectors. They remain searchable through independent lexical retrieval, but switching to legacy dense retrieval will not provide vector matches for those new uploads.
- Independent mode is opt-in through `RAG_ENGINE_MODE=independent`; the default remains `legacy` for migration compatibility. Existing Qwen/BGE code remains in the legacy path.
- Ingestion progress persists as before, but Phase 1 does not add restart-safe chunk checkpoints. Cancellation is checked at extraction/chunk/write boundaries; a large single SQLite transaction is not interruptible mid-commit.
- The active collection passed its read-only integrity audit. One separate mock-namespaced collection has 55 Chroma IDs missing from FTS5. It was left untouched and is detailed in [`PHASE1_INDEX_INTEGRITY.json`](PHASE1_INDEX_INTEGRITY.json).
- The existing backend real end-to-end test now uses temporary Chroma storage. A mock-namespaced collection currently contains 175 consistent rows; no suspected fixture rows were deleted because a precise safe restore set was not available.
- No Python static type checker is installed in the current environment. Python compilation, full backend/RAG tests, frontend unit tests, lint, frontend typecheck, and production build were run instead.

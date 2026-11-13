# ResearchLens Phase 3 Known Limitations

- The absence of reviewed real entity/relation labels prevents fitting, meaningful evaluation, candidate registration, and approval. Phase 3 currently supplies the infrastructure and safe refusal behavior, not trained real-data models.
- The deterministic tokenizer handles Unicode and common sentence endings/initials but is not a full scholarly tokenizer. Abbreviations, citations, OCR corruption, tables, and unusual punctuation can create boundary errors; reviewers must correct spans.
- The entity model is a linear token classifier over 32,768 hashed feature bins. Feature collisions are possible, long-distance context is limited, and confidence is not calibrated until measured on a larger validation corpus.
- The ontology is configurable through alias-to-canonical JSON, but custom types need sufficient reviewed examples and consistent annotation. It does not discover new entity categories automatically.
- Relationship candidate pairs are directed, sentence-local, and capped to avoid combinatorial growth. Cross-sentence/coreference relationships are not modeled. The classifier depends on manually reviewed positive and `NO_RELATION` examples; proximity alone is not treated as evidence.
- Multi-label relationship extraction can return more than one relation for a pair, but requires explicit multi-label annotations and validation data for confidence-threshold selection.
- The local annotation queue uses JSONL and is intended for a single maintainer process; concurrent editing and team permission management are not implemented. Private data directories are ignored by `.gitignore`, but the local machine still needs suitable access controls and backups.
- `joblib` artifacts must be loaded only from the trusted local registry. Checksums and software major-version checks detect accidental changes/incompatibilities; the manifest is not a signed supply-chain record.
- No peak RAM or throughput measurements on the target i5-6300U/8 GB computer are available because the real dataset is empty. Sparse hashed features bound feature width but training cost still grows with the number of annotated tokens/pairs.
- The inference adapters are not connected to Phase 1. No graph write, memory system, application interface, or automatic deployment is included.

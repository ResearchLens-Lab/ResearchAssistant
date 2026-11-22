# ResearchLens Phase 1 Implementation Report

## Scope

Phase 1 adds an executable deterministic research-answering mode. It does not train or install a foundation model, and it does not add the later roadmap phases. The existing legacy hybrid RAG path remains available.

Enable the new mode with `RAG_ENGINE_MODE=independent`. The setting currently defaults to `legacy` for migration safety; `legacy` remains an explicit option. Independent-mode answers and new uploads use SQLite FTS5 and local deterministic code only.

## What changed

- Added the `rag.independent` package: rules-based question classification, BM25/TF-IDF retrieval, conservative fact extraction, deterministic structured answers, evidence validation, and an end-to-end engine.
- Added FTS5-only document/text ingestion for independent mode. It uses the existing loaders and section-aware chunker, writes all chunks in one SQLite transaction, verifies IDs, supports cancellation boundaries, and does not invoke a pretrained embedder.
- Routed `QueryPipeline` through the independent engine before legacy retrieval/planning/generation objects are used. It returns explicit metadata (`generation_provider=none`, `embedding_provider=none`, zero model calls).
- Made model-backed ingestion lazy at RAG client startup. Independent-mode startup and Q&A do not construct BGE or a generation client.
- Updated upload consistency checks to accept a verified FTS5-only index in independent mode.
- Changed legacy lexical backfill so it adds missing Chroma rows without deleting FTS-only entries. A count mismatch no longer triggers a destructive full-index replacement.
- Added the independent-mode assistant badge in chat.
- Added a read-only Chroma/FTS integrity auditor and a hand-authored 30-case synthetic evaluation set.
- Isolated the existing real end-to-end backend test from the developer’s persistent `.chroma` directory.

## How the independent path works

1. Normalize question text and classify one of the 16 requested intents with explainable patterns, small inflection rules, and configurable synonym dictionaries. It records entities, terms, filters, retrieval strategy, and answer shape.
2. Read the configured collection’s existing SQLite FTS5 index using a `mode=ro` connection. Collection naming is resolved from settings and package metadata only; model weights are not loaded.
3. Retrieve FTS5 BM25 candidates, score them with local TF-IDF, and fuse ranks using reciprocal-rank fusion. Section/title signals, selected paper/document/section filters, comparison balance, title-page lookup, and exact same-paper passage de-duplication refine the result. Results retain source IDs, chunk/document IDs, section, filename, and physical page.
4. Extract exact source spans for definitions, author candidates, numbers and units, dates, methods, datasets, metrics, and explicit list items. Ambiguous author patterns require review.
5. Compose intent-specific answers from those passages. Examples are only shown when a source passage contains one. Comparisons remain source-by-source; no values are averaged.
6. Validate citation IDs against retrieved sources, and validate fact-to-chunk/document/page provenance and exact supporting text. Cross-paper metric differences are surfaced as conflicting evidence rather than merged.

The independent query path does not invoke Qwen/Ollama, another generative provider, BGE/FastEmbed inference, Gemini, or a remote inference API. New documents uploaded while independent mode is active are indexed in FTS5 only. Existing Chroma vectors are not rewritten.

## Files changed or added

- `rag/config/settings.py`, `.env.example`
- `rag/pipelines/query_pipeline.py`
- `rag/vectorstore/vector_repository.py`
- `rag/independent/__init__.py`
- `rag/independent/models.py`
- `rag/independent/intent_classifier.py`
- `rag/independent/retriever.py`
- `rag/independent/fact_extractor.py`
- `rag/independent/answer_composer.py`
- `rag/independent/evidence_validator.py`
- `rag/independent/engine.py`
- `rag/independent/index_writer.py`
- `rag/independent/ingest_pipeline.py`
- `backend/app/integrations/rag_client.py`
- `backend/app/services/document_service.py`
- `frontend/src/components/chat/MessageItem.jsx`
- `rag/tests/test_independent_engine.py`
- `rag/tests/test_vectorstore.py`
- `backend/tests/test_real_e2e_flow.py`
- `rag/evaluation/phase1_fixture_corpus.json`
- `rag/evaluation/phase1_independent_dataset.json`
- `rag/evaluation/run_phase1_evaluation.py`
- `rag/evaluation/audit_index_integrity.py`
- `rag/evaluation/phase1_evaluation_run.json`
- `PHASE1_INDEX_INTEGRITY.json`
- `PHASE1_TEST_RESULTS.md`
- `PHASE1_EVALUATION_RESULTS.md`
- `PHASE1_KNOWN_LIMITATIONS.md`

DOI verification and existing model integrations were left in place. No database or index reset was run.

## Existing corpus spot check

The active indexed copy of *Introduction to Algorithms* was queried with the selected paper ID. The independent engine retrieved the page 25 passage, composed the definition and input/procedure/output key points, and marked the response strongly supported. A separate author lookup returned Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, and Clifford Stein from the title-page/bibliographic passage, with a human-review note. A warm query against the active indexed project took about 0.47 seconds in this run; this is one local spot check, not a latency benchmark.

## Index integrity observation

The read-only audit found the active BGE-namespaced collection consistent at 6,523 Chroma IDs and 6,523 FTS rows, with no missing, orphaned, duplicate, or provenance-mismatch records. A separate `research_papers_mock-dense-384_384` collection has 175 Chroma IDs and 120 FTS rows (55 missing lexical entries). Another mock-namespaced collection is 175/175. The 55-entry mismatch is preserved and reported; the audit did not repair it. See [`PHASE1_INDEX_INTEGRITY.json`](PHASE1_INDEX_INTEGRITY.json).

The existing real end-to-end test originally used a pre-created RAG singleton and could write test fixtures into the persistent mock namespace. It is now wired to a temporary Chroma directory. The mock namespace currently reports 175/175; no rows were removed because there was no safe before-run record identifying exactly which persisted rows belonged to the fixture. The active BGE collection remained consistent in the final audit.

## Phase 2 prerequisites

Use this rules engine and the synthetic set as a baseline. Before training a custom classifier or NER model, expand the manually reviewed evaluation set with representative, permission-cleared documents and varied question phrasings. Keep training data separate from user uploads unless the user explicitly contributes it.

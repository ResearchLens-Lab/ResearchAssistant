# ResearchAssistant — Phase 1 Local RAG Validation

**Date:** 2026-10-26

**Scope:** Local PDF extraction, FastEmbed embeddings, token-safe chunking, ChromaDB/SQLite FTS5 indexing, retrieval provenance, retry cleanup, and reindex safety. Generation was not called. No Gemini/paid API calls, database service, Docker container, production collection, or user document was used.

## Outcome

Phase 1 blockers found during inspection and isolated runs are fixed in source: Windows local inference no longer starts an unnecessary process pool; FastEmbed inputs are split using the model's untruncated tokenizer so BGE's 512-token truncation does not silently discard passage tails; same-batch duplicate text is embedded once; chunk IDs include document identity; the collection namespace is versioned for the changed ID scheme; and reindexing now requires explicit scope and explicit apply.

Local FastEmbed indexing and retrieval succeeded against temporary PDF files and temporary Chroma/SQLite directories. A 3-page fixture and a 16-page fixture attached to the same paper produced 19 chunks in Chroma and 19 corresponding FTS rows. Retrieval returned the expected filenames, evidence text and source pages for all three questions. Repeat ingestion stayed idempotent. A separate injected local embedding failure cleaned the already-indexed partial batch from both stores, and retry indexed the complete document.

**Full-corpus reindex is not yet approved by this validation.** The integration inputs were generated synthetic PDFs, the actual database-backed reindex dry-run was not executed, and the original user PDFs were not available in this isolated workspace. Use a controlled selected-document dry-run and then a small selected `--apply` trial before scheduling any corpus-wide reindex.

## Confirmed fixes and affected files

- [embedder.py](rag/embeddings/embedder.py): FastEmbed uses in-process inference (`parallel=None`) rather than spawning a process pool on Windows. It deduplicates identical uncached text within each embedding call, caches vectors by FastEmbed version/model and text hash, and provides splitting using an untruncated clone of the model tokenizer. Each emitted text slice is checked against the 512-token model input limit.
- [chunker.py](rag/chunking/chunker.py) and [ingest_pipeline.py](rag/chunking/chunker.py): the default pipeline wires the FastEmbed-aware token limiter into chunking, retains each source span, assigns sequential stable metadata to split chunks, and resolves page ranges against the normalized source pages.
- [metadata.py](rag/chunking/metadata.py) and [strategies.py](rag/chunking/strategies.py): stable chunk IDs now contain both paper and document identity. Previously, two files in one project could produce the same `{paper_id}_c0000...` ID and overwrite each other.
- [collection_manager.py](rag/vectorstore/collection_manager.py): collection names and metadata include `chunkidv2` / `document-scoped-v2`, isolating the new chunk ID scheme from prior vectors.
- [reindex_documents.py](scripts/reindex_documents.py): dry-run is the default; application requires `--apply` and either explicit `--document-id` values or `--all`. Stale `processing` rows are excluded unless `--resume-stale` is provided, and are rechecked under a row lock against a minimum heartbeat age before processing. Direct script execution now resolves repository imports correctly.
- Regression tests: [test_embeddings.py](rag/tests/test_embeddings.py), [test_ingest_pipeline.py](rag/tests/test_ingest_pipeline.py), [test_chunking.py](rag/tests/test_chunking.py), [test_vectorstore.py](rag/tests/test_vectorstore.py), and [test_reindex_safety.py](rag/tests/test_reindex_safety.py).
- Usage/provenance documentation: [rag/README.md](rag/README.md), root [README.md](README.md), and an implementation addendum in [PROJECT_AUDIT.md](PROJECT_AUDIT.md). The earlier audit conclusions remain marked as historical.

No environment file, API key, existing upload, user database, or existing Chroma store was changed by this phase. All real-model integration used a temporary directory for both ChromaDB and the SQLite index/cache. `HF_HUB_OFFLINE=1` was set during local-model checks, and the already-cached model files were used.

## Local model and tokenizer checks

| Check | Observed result |
|---|---:|
| Configured embedding provider/model/dimension | `fastembed` / `BAAI/bge-small-en-v1.5` / 384 |
| FastEmbed package | 0.9.0 |
| Warm process model initialization with cached files | 0.534 s |
| First embedding of one unique warm-up string | 0.064 s |
| Same string on second call through SQLite cache | 0.009 s; vector identical; no model call needed |
| 3,935-token stress passage | Split to 9 overlapping chunks; maximum 512 tokens per chunk; unique-token span inspection found no character gaps; final marker preserved |

The tokenizer probe confirmed the underlying risk: a 500-word, highly subword-dense passage contained 3,002 full tokens, while the FastEmbed model tokenizer's configured input was capped at 512. After the fix, over-limit input is segmented before the ONNX embedding call. This preserves the source text across overlapping chunks instead of relying on tokenizer truncation.

## Isolated end-to-end PDF results

All PDFs and vector/index/cache storage were created under temporary paths and deleted after each run. The retrieval path instantiated the configured `ResearchRetriever` and used local query embeddings. It did not invoke `QueryPipeline`, Gemini, or any answer-generation model.

### 3-page and 16-page same-project fixtures (final document-scoped collection)

| File | Pages | Chunks | Total ingestion time | Max full-tokenizer chunk length |
|---|---:|---:|---:|---:|
| `same-project-small.pdf` | 3 | 3 | 1.239 s | 117 |
| `same-project-large.pdf` | 16 | 16 | 9.603 s | 512 |

Both documents used the same `paper_id` but separate `document_id` values. The resulting collection name included the FastEmbed model/version, dimension and `chunkidv2` marker. Counts were **19 Chroma records and 19 FTS5 rows**; each document had the expected individual count. This confirms the ID change prevents one document from overwriting another in the same project.

Retrieval checks:

| Question | Retrieved source | Page locator | Evidence check |
|---|---|---|---|
| Heliotrope-17 calibration temperature | `same-project-small.pdf` | Page 1 | Returned chunk contained `62 Celsius`. |
| Cobalt-Delta recovery time | `same-project-small.pdf` | Page 2 | Returned chunk contained `19 minutes`. |
| Quasar-Blue validation threshold | `same-project-large.pdf` | Pages 10–13 | Returned chunk contained `0.873`; the source statement is on page 11, within the cited range. |

The earlier isolated run also passed retrieved `[S1]` through `CitationMapper` and confirmed it retained the source filename and page locator. The current ID format changes the chunk ID only; the citation mapper remains unchanged and the RAG citation tests pass.

Re-ingesting the 16-page document left its Chroma count at **16 → 16**, its FTS5 count at **16**, and returned success. It did not create duplicate rows.

### Larger 40-page synthetic fixture and timings

A separate generated 40-page text PDF produced 135,564 extracted characters. It generated 80 token-safe chunks in 20 embedding batches. Maximum independently measured full-tokenizer length was 512.

| Stage | Measured time |
|---|---:|
| PDF extraction (40 pages) | 1.216 s |
| Chunking and page mapping | 2.709 s |
| Local embedding (first pass, 80 chunks) | 43.232 s |
| Chroma + FTS indexing | 2.451 s |
| Total ingestion | 49.610 s |

This synthetic document exceeded 30 seconds; the actual bottleneck was local CPU embedding of 80 unique chunks. A repeat pass over the same contents, using the persistent per-test embedding cache, completed in 6.717 s, with 0.061 s in embedding and 2.718 s in indexing. These measurements are machine- and fixture-specific; they do not predict timings for either previously reported user PDF.

## Failure, cleanup and retry

An isolated local run injected an error during the second embedding batch after one batch had reached both stores:

- First attempt failed with the injected error.
- Partial Chroma rows after cleanup: **0**.
- Partial FTS5 rows after cleanup: **0**.
- Retry with the same document ID: succeeded with **3 chunks**.
- Final Chroma/FTS counts: **3 / 3**.

The existing OCR-required behavior remains in place: image-only/scanned PDFs still fail explicitly with “scanned PDFs require OCR, which is not enabled.” No OCR code was added.

## Reindex safety review

The previous script would select all indexed and failed rows and begin mutation immediately; it had no dry-run/scope controls and excluded interrupted `processing` rows from restart selection. It is now safer by default:

```powershell
python scripts/reindex_documents.py --document-id <document-id> --dry-run
python scripts/reindex_documents.py --document-id <document-id> --apply
```

For deliberate all-document review, `--all` is explicit and defaults to listing only; mutation still requires `--apply`. `--resume-stale` is opt-in and rechecks the heartbeat under a row lock before reprocessing. The old embedding collection is not deleted. The new chunk ID format has a new collection namespace, so stored documents must be indexed into that namespace before queries can use them.

Verified: the script's `--help` runs from the documented repository-root invocation; unscoped invocation exits with an argument error; unit tests cover explicit selection, default dry-run and stale-age validation. **Not verified:** database-backed document selection, production DB dry-run output, actual stale-row resume, and applying any reindex. The configured database was not accessed.

## Test and command results

- `python -m pytest rag/tests -q` with `HF_HUB_OFFLINE=1`: **75 passed in 13.01 s** (final run).
- Focused subset before the final added document-ID regression cases: **27 passed in 9.56 s**.
- `python scripts/reindex_documents.py --help`: **passed**; no database connection made.
- `python scripts/reindex_documents.py` with no selector: **rejected as intended** (required explicit `--document-id` or `--all`).
- `git diff --check`: **passed**. Git printed existing working-tree LF→CRLF notices for unrelated frontend/backend files; no whitespace errors were reported.
- No frontend tests/builds, Docker commands, Gemini calls, paid APIs or full-corpus jobs were run; they are outside Phase 1's local RAG validation scope.

## Remaining limitations and full-reindex decision

- The actual Cormen and Horowitz source PDFs were not available as local files in this environment. The synthetic fixtures cannot verify their extraction quality. The earlier observed Horowitz PDF had no selectable text; it still needs OCR support to become searchable. The earlier Cormen document has not been re-embedded using the local provider here.
- The 40-page first-pass synthetic ingestion took 49.610 s; local embedding is currently the main measured cost. No chunk-size adjustment was made: the fix splits only chunks that exceed the model's real tokenizer limit.
- No DB-backed dry-run proves which records exist, whether original paths are available, or how many will fail (including scanned PDFs).
- The ID schema/collection namespace changed. Do not point a live app at the new namespace expecting old documents to be present until a controlled reindex has populated it and retrieval counts/provenance have been checked.

**Decision:** safe to proceed to a **small, explicitly selected reindex in a development copy** after verifying that document's original file and reviewing `--document-id <id> --dry-run`. Not yet safe to proceed with a full-corpus reindex. First validate one known text PDF (preferably Cormen) through the database-backed reindex path in a cloned environment, inspect exact chunks and retrieval citations, then expand in measured batches. Keep the old collection and originals until the migration is verified.

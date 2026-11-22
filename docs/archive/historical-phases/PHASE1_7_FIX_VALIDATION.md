# ResearchAssistant — Phase 1.7 Fix Validation

**Date:** 2026-10-26  
**Scope:** Lazy generation initialization and accurate reindex chunk counts only. No Phase 2 work, UI changes, or full-corpus reindex was performed.

## Root causes and fixes

### Local generation provider blocked ingestion

`QueryPipeline.__init__` previously constructed `GroundedGenerator` immediately. That called `LLMClientFactory.get_client()` even when `RAGClient` was being used only for document ingestion. `RAGSettings` accepts `LLM_PROVIDER=local`, while the generation factory supports Gemini, OpenAI, and mock and raises for `local`; consequently the reindex command failed before PDF extraction.

`QueryPipeline` now stores an injected generator as-is and initializes `GroundedGenerator` through a property only when sufficient retrieved evidence reaches the generation step ([query_pipeline.py:49](rag/pipelines/query_pipeline.py:49)). Local FastEmbed remains configured independently. Unsupported generation still raises the factory's explicit `ValueError`; [rag_gateway.py:20](backend/app/integrations/rag_gateway.py:20) preserves that actionable provider error as an API error. Gemini selection still uses the existing generator factory.

### Failed reindex retained stale `chunk_count`

The reindex utility previously left the old positive count in place while replacing indexes and copied the ingestion result count directly into the row without checking Chroma or FTS5. The ingestion pipeline can clean partial indexes after an exception, so a failed row could retain a count for chunks that no longer existed.

The utility now sets `chunk_count=0` when entering processing ([reindex_documents.py:120](scripts/reindex_documents.py:120)). A successful result is marked ready only when its positive reported count equals both stored index counts and the ID sets match ([reindex_documents.py:149](scripts/reindex_documents.py:149)). Failure paths attempt cleanup, verify the active document index state, preserve the primary failure, and leave the database count at zero. `VectorRepository` now reads Chroma and FTS5 IDs/counts for the active collection ([vector_repository.py:270](rag/vectorstore/vector_repository.py:270)); document cleanup always deletes matching FTS5 rows, including orphan rows when Chroma has none ([vector_repository.py:255](rag/vectorstore/vector_repository.py:255)).

## Files changed for Phase 1.7

- `rag/pipelines/query_pipeline.py` — lazy generator construction.
- `backend/app/integrations/rag_gateway.py` — preserve unsupported-provider errors and expose cleanup/index verification methods.
- `backend/app/integrations/rag_client.py` — expose active-store cleanup and count inspection.
- `rag/vectorstore/vector_repository.py` — compare Chroma and FTS5 IDs/counts; remove FTS5 orphans on document cleanup.
- `scripts/reindex_documents.py` — reset stale counts and verify both stores before success.
- `rag/tests/test_generation.py` — local provider deferral, explicit unsupported generation error, Gemini factory compatibility without a live API.
- `rag/tests/test_ingest_pipeline.py` — local FastEmbed PDF ingestion without generator construction.
- `backend/tests/test_rag_gateway.py` — explicit unsupported-provider error behavior.
- `backend/tests/test_reindex_consistency.py` — isolated DB + Chroma + FTS failure cleanup, retry, idempotency, and page provenance.
- `PHASE1_ISOLATED_REHEARSAL.md` — dated addendum; historical Phase 1.6 findings retained.
- `PHASE1_7_FIX_VALIDATION.md` — this report.

Existing unrelated worktree changes were preserved.

## Regression tests

The isolated backend regression creates a temporary SQLite database and temporary Chroma/FTS stores, uses a FastEmbed interface with deterministic local test vectors, seeds a positive prior document count, and injects an exception after both stores have accepted the new chunks. It verifies the failed state, zero database count, empty indexes, successful retry, stable repeated ingestion, and page 1/page 2 provenance. The provider test generates a synthetic PDF and exercises the FastEmbed ingestion path while `LLM_PROVIDER=local`; generation remains uninitialized. A generation request with sufficient evidence raises the unsupported-provider error instead of returning a mock answer. Gemini compatibility uses a stub factory client and does not make a network call.

Results:

- Full RAG suite: `python -m pytest rag/tests -q` — **78 passed**.
- Full backend suite: `python -m pytest backend/tests -q` — **95 passed**.
- Final focused run after the last reindex cleanup/error-preservation edit: `python -m pytest backend/tests/test_reindex_consistency.py backend/tests/test_rag_gateway.py rag/tests/test_generation.py rag/tests/test_ingest_pipeline.py -q` — **21 passed**.
- `git diff --check` — **passed (exit 0)**. Git emitted existing line-ending conversion notices for unrelated modified files.

The full backend run preceded the final small cleanup-error-message refinement and the additional gateway assertion; those paths were included in the final focused run. No frontend suite, lint, typecheck, or production build was requested for this backend/RAG-only phase.

## Isolated PostgreSQL rehearsal

### Isolation evidence

- Docker Engine `29.9.1` was reachable.
- A new container named `researchassistant-phase17-827f1ebe0f` ran `postgres:16-alpine`. Port `61379` was bound only to `127.0.0.1`. `docker inspect` showed `Mounts=[]`; PostgreSQL data was on a 512 MiB tmpfs.
- Before Alembic or record creation, the effective SQLAlchemy URL was inspected with password redaction and asserted to be `postgresql+asyncpg://phase17@127.0.0.1:61379/phase17`.
- Fresh resolved paths were all inside `%TEMP%\researchassistant-phase17-827f1ebe0f`: `uploads`, `chroma`, `embedding-cache\vectors.sqlite3`, and `model-cache`. The FTS5 database used the existing code's colocated path `chroma\researchlens_lexical.sqlite3`. The fresh index/cache/model paths were empty before the dry-run. Process-only environment overrides set `LLM_PROVIDER=local`, `EMBEDDING_PROVIDER=fastembed`, model `BAAI/bge-small-en-v1.5`, and dimension 384. No `.env` file was changed.
- Alembic applied the existing migrations `0001` through `0004` successfully to this disposable PostgreSQL database.

Key commands, with all storage/provider overrides set only in the invoking PowerShell process:

```text
docker run -d --name researchassistant-phase17-827f1ebe0f --publish 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data:rw,size=536870912 --env POSTGRES_USER=phase17 --env POSTGRES_DB=phase17 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
python -m alembic -c backend/alembic.ini upgrade head
python scripts/reindex_documents.py --document-id e3ff7e15-ebda-4745-a4b5-b20b3030e209 --dry-run
python scripts/reindex_documents.py --document-id e3ff7e15-ebda-4745-a4b5-b20b3030e209 --apply
docker rm --force researchassistant-phase17-827f1ebe0f
```

The failure rehearsal called `scripts.reindex_documents.reindex_documents([document_id], include_all=False, apply=True)` from an inline Python process after wrapping `VectorRepository.upsert_chunks` to complete its real write and then raise. The retry used the scoped CLI command above.

### Dry-run and selected apply

Created only synthetic user/paper/document records and a generated two-page PDF. The source filename was `phase17_known_facts.pdf`; its original path was inside the fresh upload directory. The dry-run selected exactly document `e3ff7e15-ebda-4745-a4b5-b20b3030e209`, status `failed`, and the expected filename. It did not change the row (`failed`, `chunk_count=17`) or create Chroma, embedding-cache, or model-cache entries.

The explicit scoped apply command ran with `LLM_PROVIDER=local`:

```text
python scripts/reindex_documents.py --document-id e3ff7e15-ebda-4745-a4b5-b20b3030e209 --apply
```

It completed `1 ready, 0 failed` using FastEmbed. The first run fetched the public FastEmbed model artifacts into the dedicated temporary model cache. This was a model-file download, not a Gemini or other paid generation/API call. No API key was printed or used.

### Counts, identity, provenance, timings

| Check | Verified result |
|---|---|
| Database row | `indexed`, stage `ready`, `chunk_count=2`, no error; original PDF present |
| Active collection | `reseaembed_BAAI_bge-small-en-v1_5_fastembed-0_9_0_chunkidv2_384` |
| Chroma | 2 chunks |
| SQLite FTS5 | 2 rows |
| ID consistency | Same two unique stable chunk IDs in both stores; no mismatch or duplicate count growth |
| Embedding batches | 1 batch for 2 chunks |
| Cold apply | 32.856 s total; extraction 1.719 s; chunk stage 30.676 s; embeddings 0.095 s; indexing 0.290 s |
| Warm repeated apply | 2.502 s total; extraction 1.751 s; chunk stage 0.574 s; embeddings 0.002 s; indexing 0.097 s |
| Local query retrieval | BLUEBIRD → original filename, page 1, `Results · passage 1`; 2039 → original filename, page 2, `Conclusion · passage 2` |
| Query time | 0.581 s and 0.040 s for the two warmed retrievals |

The cold chunk-stage measurement includes FastEmbed model/tokenizer initialization and the approximately 28-second model download; it is not the steady-state text chunking cost. Retrieval used `ResearchRetriever` and the same FastEmbed model/collection as ingestion, without constructing a generator.

### Failure cleanup and retry

During an actual call to the reindex function against the disposable PostgreSQL database, `VectorRepository.upsert_chunks` was patched to perform its real Chroma and FTS5 writes and then raise. The injection confirmed both indexes had received 2 chunks. Ingestion cleanup deleted those 2 Chroma chunks and FTS5 rows. The reindex operation returned `(0, 1)`; persisted status was `failed/failed`, the injected error remained visible, and `chunk_count=0`. Read-back showed Chroma=0, FTS5=0, and equal empty ID sets.

The explicit scoped CLI apply was then retried. It returned `1 ready, 0 failed`; final state again had 2 matching chunks, 2 unique IDs, and successful page-specific retrieval. A preceding successful repeated apply kept the count at 2.

The first fixture-record insert attempt used an invalid overlength document ID and PostgreSQL rejected it; the transaction rolled back. A valid UUID fixture was then created and used for all actual dry-run/apply/retrieval checks. All artifacts from both setup attempts remained in the disposable directory and were removed during cleanup.

### Cleanup

Closed Python/database processes, verified the exact temporary container ID and `Mounts=[]`, removed only `researchassistant-phase17-827f1ebe0f` with `docker rm --force`, and removed only the verified unique Phase 1.7 temp root. Final checks confirmed the container and temp root were absent. No Docker prune, existing container, configured application database, user file, existing collection, FTS index, or project `.env` file was touched.

## Decision

**GO for the next controlled selected-document migration rehearsal against a separately verified isolated clone.** The local-provider reindex path now works without generation construction, success depends on verified Chroma/FTS agreement, and injected failure/retry passed against disposable PostgreSQL. Review the clone's full dry-run, missing/scanned-file list, and selected scope before any broader apply. This synthetic run does not establish whether actual Cormen or Horowitz PDFs are present, text-based, or require OCR, and does not authorize a full-corpus reindex.


# ResearchAssistant — Phase 1.5 Migration Safety Report

**Date:** 2026-10-26  
**Scope:** Read-only inspection of migration code and environment wiring. No database connection, service start, migration, reindex, Gemini call, or index/file mutation was performed.

## Outcome and safety determination

**The database-backed dry-run and selected-document trial were not run.** The repository configuration does not establish that the target PostgreSQL database, uploaded originals, Chroma collection, and SQLite FTS index are isolated development copies. The compose configuration instead declares persistent named volumes, and no separate cloned database/storage paths were identified in the inspected configuration. Per the safety requirements, I stopped before connecting to PostgreSQL.

This is a verified safety blocker, not evidence that the migration itself failed. No document rows were enumerated, no Cormen record ID or original file availability was verified, and no before/after database or index counts are available. **Do not proceed to a larger migration** until a separate, explicitly identified development copy of the database and all associated storage is provided and verified.

## Reports read

- `PROJECT_AUDIT.md`, including the Phase 1 implementation addendum. It documents the namespace change and says the actual PDFs and current Chroma contents were not inspected during the audit.
- `PHASE1_VALIDATION.md`. It records 75 passing RAG tests and isolated synthetic-PDF checks, while explicitly stating that the database-backed dry-run, actual source PDFs, and selected apply were not verified. Its recommendation was to conduct the next trial in a cloned development environment.

These reports do not establish that the currently configured runtime database or persistent volumes are disposable or isolated.

## Environment and data-path inspection

| Area | Verified wiring | Safety implication |
|---|---|---|
| PostgreSQL | `infrastructure/docker-compose.backend.yml:14,26,58` defines PostgreSQL database `researchassistant` with persistent named volume `postgres_data`. `backend/app/core/config.py:15-17,26-28` loads backend settings from `backend/.env.local` and has a localhost database URL default. | No separate database copy or isolated volume is established by these files. I did not read or print local credential values and did not connect. |
| Original files | `backend/app/core/config.py:40,71` configures `UPLOAD_DIR` / `upload_path`; `backend/app/services/document_service.py:50-80` stores originals beneath that directory using generated document-ID filenames. Compose mounts `upload_data` at `/srv/storage/uploads` (`infrastructure/docker-compose.backend.yml:50,59`). | The persistent upload volume is not identified as a cloned development copy. Original-file existence and per-record `storage_path` values remain unknown. |
| Chroma | `rag/config/settings.py:25-28` defaults to local `.chroma`; compose mounts persistent `chroma_data` for the API (`infrastructure/docker-compose.backend.yml:51,60`) and Chroma service (`infrastructure/docker-compose.chroma.yml:8,16`). | No isolated Chroma path/volume was established. I did not open or count any existing collection. |
| SQLite FTS5 | `rag/vectorstore/vector_repository.py:158-160` places `researchlens_lexical.sqlite3` inside the active Chroma persistence directory. | It shares the Chroma storage safety boundary; no separate test copy was established or opened. |
| Reindex configuration | The reindex script calls `get_session_factory()`, which lazily creates an engine from configured `database_url` (`backend/app/database/session.py:22-32`). | Running even dry-run would connect to the configured database. That connection was intentionally not attempted. |

No secrets, keys, passwords, credential-bearing connection strings, or environment-file values are included in this report.

## Reindex behavior and collection namespaces

Verified by source inspection:

- `scripts/reindex_documents.py:39-60` selects explicitly requested IDs or, with `--all`, indexed/failed rows. `--resume-stale` can additionally include processing rows after a heartbeat-age predicate. The script requires an explicit selector and defaults to dry-run.
- `scripts/reindex_documents.py:63-88` creates a `RAGGateway` only for apply, queries `Document` joined to `Paper`, and in dry-run prints selected IDs, statuses and filenames without writing those rows or calling ingestion. The SQL read still requires a database connection; it was not run.
- In apply mode (`scripts/reindex_documents.py:90-170`), it checks original-file existence, updates document processing state, then calls RAG ingestion and writes the terminal document status/chunk count. Missing originals are marked failed. These are database writes.
- The active collection is model-namespaced when `chroma_namespace_by_embedding` is enabled. `rag/vectorstore/collection_manager.py:34-43` derives the name from provider, model, FastEmbed package version, `chunkidv2`, and configured dimension. The configured defaults are FastEmbed `BAAI/bge-small-en-v1.5` at 384 dimensions (`rag/config/settings.py:31-38`).
- SQLite FTS rows are keyed by collection name and chunk ID. Ingestion upserts the active Chroma collection and FTS index (`rag/vectorstore/vector_repository.py:158-160` and related upsert implementation). The reindex script does not explicitly delete an old collection. It also does not itself delete old-namespace records.

The exact old and new collection names and their record counts were not read from a live Chroma store. Source code establishes the new naming rule, but does not establish which collections exist in the uninspected persistent store.

## Dry-run selection results

**Not executed.** Since the target database was not confirmed isolated, there are no verified document IDs, filenames, statuses, original-file accessibility checks, selected-document counts, exclusion counts, scanned-PDF findings, or stale-processing findings. The Cormen document is not known to exist as a record or accessible original in an isolated copy.

No claim is made that dry-run non-mutation was empirically tested against a database in this phase. Source inspection shows the dry-run branch does not intentionally issue writes or instantiate the RAG gateway, but it must still connect and execute a read query.

## Selected-document migration and correctness checks

**Not executed.** There was no safe isolated target or verified document ID/file to pass to the scoped dry-run, so neither the scoped dry-run nor `--apply` was invoked. Consequently there are no before/after document statuses, chunk counts, duplicate/collision checks, Chroma/FTS consistency results, retrieval evidence, citation/page checks, or runtime retrieval-path verification from a database-backed migration.

The prior Phase 1 synthetic tests are not substitutes for this trial: they used generated PDFs and temporary Chroma/SQLite storage and did not exercise the application database repository path or actual user originals.

## Commands executed in this phase

Read-only commands executed from the repository root:

```text
Get-Content -LiteralPath PROJECT_AUDIT.md; Get-Content -LiteralPath PHASE1_VALIDATION.md; git status --short
Select-String -Path PROJECT_AUDIT.md -Pattern '^#|^##|^###|not verified|reindex|Chroma|FTS|database' | Select-Object -First 100 | ForEach-Object { $_.Line }
Select-String -Path PHASE1_VALIDATION.md -Pattern '^#|^##|^###|not verified|reindex|Chroma|FTS|database|safe' | Select-Object -First 100 | ForEach-Object { $_.Line }
Get-Content scripts/reindex_documents.py; Get-Content backend/app/core/config.py; Get-Content infrastructure/docker-compose.backend.yml
Get-Content rag/vectorstore/collection_manager.py; Get-Content rag/vectorstore/vector_repository.py
Get-Content backend/app/database/session.py; Get-Content backend/app/models/document.py; Get-Content backend/app/repositories/document_repository.py
Get-Content rag/vectorstore/lexical_store.py; Get-Content rag/config/settings.py; Get-Content backend/app/core/config.py | Select-String 'upload_dir|database_url|env_file' -Context 1,1; Get-Content docker-compose.yml
Get-Content backend/app/services/document_service.py | Select-String 'storage_path|upload_path|UPLOAD|unlink|remove' -Context 2,2; Get-Content rag/pipelines/ingest_pipeline.py | Select-String 'delete|cleanup|collection|chunk' -Context 1,1
Get-Content rag/vectorstore/chroma_client.py; Get-Content infrastructure/docker-compose.chroma.yml; Get-Content backend/app/integrations/rag_gateway.py
Select-String -Path PHASE1_VALIDATION.md -Pattern '^## Reindex safety review','^## Test and command results','^## Remaining limitations' -Context 0,8 | ForEach-Object { $_.ToString() }; Select-String -Path PROJECT_AUDIT.md -Pattern 'Phase 1 implementation addendum' -Context 0,5 | ForEach-Object { $_.ToString() }
rg -n "chroma_namespace_by_embedding|chunkidv2|researchlens_lexical|def build_selection|async def reindex_documents|if not apply|--apply|storage_path|upload_dir|DATABASE_URL|postgres_data:|upload_data:|chroma_data:" scripts/reindex_documents.py rag/vectorstore/collection_manager.py rag/vectorstore/vector_repository.py rag/config/settings.py backend/app/core/config.py backend/app/database/session.py backend/app/services/document_service.py infrastructure/docker-compose.backend.yml infrastructure/docker-compose.chroma.yml
```

One attempted `Get-Content rag/vectorstore/lexical_store.py` reported that the path does not exist; FTS5 implementation was located in `rag/vectorstore/vector_repository.py` instead. No reindex utility command was executed in this phase. In particular, neither the database-backed dry-run nor `--apply` ran.

## Exact blocker and next safe step

The configured compose setup points to persistent PostgreSQL, upload and Chroma volumes, and the FTS5 database shares the Chroma persistence directory. No existing isolated copy or independent storage paths were verified. A database name, a `development` default, or the fact that compose is labeled local development would not prove the data is safe to mutate.

Provide or designate a disposable development clone with all four components isolated together: PostgreSQL, original uploads, Chroma persistence, and its colocated FTS5 SQLite file. Then configure the process to use only those paths, verify the clone identity and volume mappings without contacting production/shared services, run the whole-corpus dry-run, and inspect its rows. After selecting a confirmed text-based PDF and recording baseline counts, run the document-scoped dry-run; only then consider the explicitly scoped apply trial. Keep the original database, uploaded files and old collection untouched.

**Recommendation:** do not run the selected-document migration or a larger migration yet. After isolation is established, one selected-document trial may be considered; this report does not authorize or claim that any migration ran.

## Files changed

Only this report, `PHASE1_MIGRATION_REPORT.md`, was created for the current task. Existing uncommitted modifications and untracked files were preserved; no application, configuration, database, upload, vector, or FTS file was changed.

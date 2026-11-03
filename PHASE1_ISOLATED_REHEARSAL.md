# ResearchAssistant — Phase 1.6 Isolated Migration Rehearsal

**Date:** 2026-10-26  
**Result:** The initial attempt stopped because Docker was unavailable; the resumed attempt completed the isolated PostgreSQL rehearsal. Results and limits are recorded below.

## Safety decision

The requested database-backed rehearsal did **not** run. The host has the Docker CLI, but the Docker Desktop Linux engine is not running/reachable. No local `psql`, `postgres`, or `pg_ctl` executable was found. The project Python virtual environment and required Python libraries are present, but they are not a PostgreSQL server.

I did not connect to any configured database, inspect the existing database, start a service, run Alembic, create records, invoke the reindex script, or write to any Chroma/FTS/cache/upload location. I did not substitute SQLite: although backend tests use SQLite, the requested rehearsal specifically requires PostgreSQL and its migration schema. There is therefore no safe effective database host/name to report for a test target; no target was configured or contacted.

## Prior reports and implementation inspected

Read `PROJECT_AUDIT.md`, `PHASE1_VALIDATION.md`, and `PHASE1_MIGRATION_REPORT.md` first. They establish that Phase 1's 75 RAG tests and synthetic PDF checks used isolated temporary stores, and that no database-backed reindex had yet been run.

Read the reindex utility, SQLAlchemy session/base/models, Alembic environment and revisions `0001`–`0004`, backend test DB fixture, and the relevant storage/collection implementation. The utility obtains its database from `get_settings().database_url`; apply mode uses `Document.storage_path` and the active RAG client. Chroma persistence, FTS5 SQLite, and embedding cache normally share the RAG persistence directory. The requested rehearsal would require overriding all of these to fresh isolated paths and using a separately provisioned PostgreSQL endpoint.

The existing schema revisions and ORM include PostgreSQL `JSONB` through a dialect variant and document progress columns. The test fixture's SQLite `create_all` is not evidence that PostgreSQL migrations or the actual PostgreSQL-backed script path work.

## Environment isolation evidence

| Check | Result |
|---|---|
| Project virtualenv | Present; `.venv\Scripts\python.exe` reports Python 3.12.15. |
| Required Python modules | `asyncpg`, `sqlalchemy`, `alembic`, `chromadb`, `fitz`, and `fastembed` are importable in that virtualenv. |
| PostgreSQL client/server binaries | `Get-Command psql, postgres, pg_ctl` returned no executables. |
| Docker client | Present. |
| Docker engine | `docker version` and `docker ps` failed to connect to `npipe:////./pipe/dockerDesktopLinuxEngine`; the named pipe is unavailable. No container listing or container creation succeeded. |
| Disposable DB and paths | Not created. No host/database, upload path, Chroma path, or FTS/cache path was configured for this rehearsal. |
| Existing environment/data | No existing `.env` was used as a target; no current database or persistent storage was accessed. Secrets and credential values were not printed. |

## Reindex results

| Requested check | Result |
|---|---|
| Create isolated PostgreSQL schema | Not run: no PostgreSQL server/runtime available. |
| Create synthetic multi-page PDF and matching DB records | Not run: stopped at the infrastructure blocker. |
| Scoped dry-run with synthetic document ID | Not run; no ID was created. |
| Explicit scoped apply | Not run. |
| Dry-run before/after data/index counts | Not available; no target state was created or queried. |
| Final status, Chroma/FTS counts, retrieval/page citations | Not verified in this phase. |
| Repeat ingestion idempotency and injected failure recovery | Not exercised through the DB-backed utility. Prior isolated RAG checks in `PHASE1_VALIDATION.md` cover lower-level synthetic ingestion behavior but do not prove this workflow. |
| Cleanup | No rehearsal resources were created, so no cleanup was needed. Existing user files, persistent stores, and collections were left untouched. |

## Commands executed

Commands were run from the repository root. Reads and environment probes only:

```text
Get-Content PROJECT_AUDIT.md | Select-Object -Last 24; Get-Content PHASE1_VALIDATION.md | Select-Object -Last 40; Get-Content PHASE1_MIGRATION_REPORT.md | Select-Object -First 100
Get-Content backend/alembic.ini; Get-Content backend/app/database/base.py; Get-Content backend/app/models/paper.py; Get-Content backend/app/models/user.py; Get-ChildItem backend/migrations/versions | Select-Object Name
Get-Command docker, psql, postgres, pg_ctl -ErrorAction SilentlyContinue | Select-Object Name,Source; python --version; python -c "import importlib.util as u; print({x: bool(u.find_spec(x)) for x in ['asyncpg','sqlalchemy','alembic','chromadb','fitz','fastembed']})"; git status --short -- PHASE1_ISOLATED_REHEARSAL.md scripts/reindex_documents.py
Get-Content backend/app/database/session.py; Get-Content backend/app/database/base.py; Get-Content backend/app/models/__init__.py; Get-Content backend/migrations/env.py; Get-Content scripts/reindex_documents.py
docker version --format '{{.Server.Version}}' 2>&1; docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>&1
Get-Content backend/migrations/versions/0001_initial_schema.py; Get-Content backend/migrations/versions/0002_usernames.py; Get-Content backend/migrations/versions/0003_document_processing_stage.py; Get-Content backend/migrations/versions/0004_document_ingestion_progress.py
Get-Content backend/tests/conftest.py | Select-String 'sqlite|DATABASE_URL|create_all|migration|engine' -Context 1,2; Get-Content requirements.txt | Select-String 'asyncpg|sqlalchemy|alembic|fastembed|chromadb|pymupdf'
.\.venv\Scripts\python.exe --version; .\.venv\Scripts\python.exe -c "import importlib.util as u; print({x: bool(u.find_spec(x)) for x in ['asyncpg','sqlalchemy','alembic','chromadb','fitz','fastembed']})"; Get-Command psql, postgres, pg_ctl -ErrorAction SilentlyContinue | Select-Object Name,Source
```

The plain `python` commands hit the Windows Store alias instead of an installed interpreter; the project virtualenv probe succeeded. Docker commands returned an engine-pipe error. No schema, migration, reindex, or data-changing command was executed.

## Decision and remaining requirement

**The database-backed reindex workflow has not passed or failed; it remains unvalidated.** The precise blocker is the unavailable Docker Desktop Linux engine and absence of a local PostgreSQL server. Start Docker Desktop (or provide a dedicated disposable PostgreSQL service) and rerun this phase with a uniquely named temporary database plus fresh upload, Chroma, FTS5, and cache paths. Before any migration command, verify the effective endpoint/database and all resolved storage paths are the rehearsal-only targets. Do not fall back to the application's `.env.local`, default localhost database, or existing compose volumes.

Only after that isolation check should the PostgreSQL schema be initialized, the synthetic records/PDF be created, and the document-scoped dry-run and apply be exercised. Keep actual-corpus migration gated on the resulting count, idempotency, failure-recovery, retrieval, and citation evidence.

## Files changed

For the initial attempt, only `PHASE1_ISOLATED_REHEARSAL.md` was created. No application code or existing user database/index/upload data was modified.

---

## Resume result — database-backed rehearsal (2026-10-26)

The earlier blocker is resolved for this rehearsal. Docker Engine was reachable (`docker version --format '{{.Server.Version}}'` returned `29.9.1`). The original local/shared environment remained untouched.

### Disposable environment and isolation evidence

- Created a unique temp root: `%TEMP%\researchassistant-phase16-mvow53llc5uga5w3`, with fresh `uploads`, `chroma`, `embedding-cache`, and `model-cache` directories. Each resolved under that root and was absent before creation.
- The disposable PostgreSQL target was `postgresql+asyncpg://phase16@127.0.0.1:63620/phase16`; the report records no password or secret. Effective SQLAlchemy settings were read back and asserted to have host `127.0.0.1`, port `63620`, and database `phase16` before migrations or row creation.
- Docker container: `researchassistant-phase16-mvow53llc5uga5w3`, image `postgres:16-alpine`, port published only to `127.0.0.1:63620`. PostgreSQL data used a 512 MiB tmpfs. `docker inspect` reported `Mounts=[]`, and `HostConfig.Tmpfs` showed `/var/lib/postgresql/data` on tmpfs.
- The first container attempt omitted explicit mounts but the PostgreSQL image attached an anonymous volume. No database commands ran against it. That uniquely named rehearsal container and its anonymous volume were removed with `docker rm -fv` before creating the tmpfs-backed container. The anonymous volume was later verified absent.
- Process-only overrides, with no `.env` edits: `DATABASE_URL`, `UPLOAD_DIR`, `CHROMA_PERSIST_DIR`, `EMBEDDING_CACHE_PATH`, `FASTEMBED_CACHE_DIR`, `EMBEDDING_PROVIDER=fastembed`, `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`, `EMBEDDING_DIMENSION=384`, and `LLM_PROVIDER` as described below. The Gemini/API key fields were given a non-credential sentinel so dotenv values could not be loaded; no Gemini or paid API call was made.
- Resolved uploads, Chroma, embedding cache, and model cache paths were each under the fresh temp root. The FTS5 file is created by current code at `chroma/researchlens_lexical.sqlite3`, so it was isolated within the fresh Chroma directory rather than having an independently configurable directory. The embedding-vector cache was separately placed at `embedding-cache/embedding_cache.sqlite3` and FastEmbed model files at `model-cache`.

### Schema, synthetic record, dry-run, and apply

Alembic initialized the disposable database successfully using the project's existing revisions: `0001`, `0002`, `0003`, and `0004`. No application migration or schema file was changed.

Created only synthetic records and a generated PDF:

- User ID: `40da3467-8f8d-4c52-8d89-7471924034a7`
- Paper ID: `de794f51-f1fc-4b7d-a274-8ca1c55c3bd9`
- Document ID: `c18e342c-8d38-40d1-b1ab-c927c156e6b6`
- Filename: `phase1_6_synthetic_facts.pdf`
- Original file: `%TEMP%\researchassistant-phase16-mvow53llc5uga5w3\uploads\c18e342c-8d38-40d1-b1ab-c927c156e6b6.pdf`
- Final fixture: 3 text pages, 565/503/502 words, with BLUE HERON on page 1, Meadowlark launch year 2037 on page 2, and checksum 7F3A-91C2 on page 3. Each page used a separate recognized section heading to make page-level citation checks meaningful.

The scoped command `python scripts/reindex_documents.py --document-id c18e342c-8d38-40d1-b1ab-c927c156e6b6 --dry-run` selected exactly that row (`failed`, `phase1_6_synthetic_facts.pdf`). Its original file existed. Before apply, the row remained failed with zero chunks, and both fresh index/cache directories were empty. No Chroma/FTS or row mutation was observed from dry-run.

The first apply attempt with `LLM_PROVIDER=local` failed before extraction/indexing. `RAGClient` constructs `QueryPipeline` at import time, and `LLMClientFactory` does not implement the `local` provider even though `RAGSettings` accepts it; the gateway logged a `ValueError`. No model/API request or chunks resulted. For the successful ingestion-only rehearsal, `LLM_PROVIDER=mock` was explicitly set to allow construction of the unused generation client. The reindex path invoked only `ingest_document`; no mock generation method or Gemini call ran. All document and query embeddings used FastEmbed.

With that explicit workaround, the document-scoped `--apply` completed: **1 ready, 0 failed**. Alembic and the utility connected only to the verified temporary endpoint. FastEmbed downloaded its model files from the public Hugging Face Hub into the temporary model-cache directory; this was not a paid API call. The cold small-fixture run took 31.018 seconds including model/tokenizer initialization/download. The final 13,251-character, 3-page fixture indexed in 7.629 seconds: extraction 1.743 s, chunking 0.644 s, embedding 5.032 s, indexing 0.127 s, 9 chunks in 1 embedding batch. A warm repeat logged 2.580 s; the final measured idempotency call took 1.244 s.

### Final counts, IDs, collection, and retrieval evidence

- Database document: `indexed`, stage `ready`, `chunk_count=9`, no error; the original file remained present.
- Active collection: `reseaembed_BAAI_bge-small-en-v1_5_fastembed-0_9_0_chunkidv2_384`, metadata confirms FastEmbed 0.9.0, 384 dimensions, and `document-scoped-v2` chunk IDs.
- Chroma count: **9**. SQLite FTS5 count for the document: **9**. The two stores contained the same nine unique chunk IDs. No collision or duplicate was observed.
- The configured `ResearchRetriever` (the retriever used by `QueryPipeline`) embedded each question with FastEmbed and retrieved evidence from this collection without invoking generation:

| Question fact | Retrieved filename | Locator | Exact original PDF page | Evidence matched source PDF |
|---|---|---|---:|---|
| BLUE HERON codename | `phase1_6_synthetic_facts.pdf` | `Introduction · passage 1` | 1 | Yes |
| Meadowlark launch year 2037 | `phase1_6_synthetic_facts.pdf` | `Methodology · passage 4` | 2 | Yes |
| Checksum 7F3A-91C2 | `phase1_6_synthetic_facts.pdf` | `Results · passage 7` | 3 | Yes |

- Repeated selected reindex preserved IDs and counts: Chroma **9 → 9**, FTS5 **9 → 9**, exact ID set unchanged. The utility returned 1 ready, 0 failed.
- A fault was injected immediately after an indexed Chroma+FTS upsert. The ingestion cleanup deleted **9** Chroma records and **9** FTS5 rows. The utility recorded the document as failed, and a subsequent selected CLI `--apply` retry restored `indexed/ready` with 9 chunks and successful retrieval.

### Defects observed; no source fixes applied

1. **`LLM_PROVIDER=local` blocks ingestion initialization.** The configured RAG settings allow `local`, but `LLMClientFactory` only handles Gemini/OpenAI/mock and throws for `local`. `RAGClient` eagerly constructs both pipelines, so even an ingestion-only command fails before ingestion. Proposed minimal fix: defer query/generator initialization until a query is requested, or provide a supported no-network generation client for local mode. No code was changed.
2. **Failed reindex can retain stale `documents.chunk_count`.** The injected failure occurred after a previous successful 9-chunk indexing. Chroma and FTS5 were correctly cleaned to zero and the document status became failed, but the database row still said `chunk_count=9`. A retry restored all nine. Proposed minimal fix: reset count when entering processing (or on failed terminal state) and only report a positive count when indexing is confirmed. No code was changed.
3. Script output includes `datetime.utcnow()` deprecation warnings on this Python version; this did not affect the rehearsal.

The fixture setup first attempted to insert user, paper, and document in one flush and hit a foreign-key violation due to unordered pending inserts. That transaction rolled back; the fixture was then inserted in dependency order. This was test harness setup, not an application/reindex defect. A read-only post-cleanup count probe initially used an unsupported Chroma `Collection.count(where=...)` signature; it was corrected to use `get(where=...)` and did not change data.

### Commands executed and cleanup

Key setup/validation commands (all other process configuration was set in the same PowerShell process; credential values were not printed):

```powershell
docker version --format '{{.Server.Version}}'
docker run -d --name researchassistant-phase16-mvow53llc5uga5w3 --publish 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data:rw,size=536870912 --env POSTGRES_USER=phase16 --env POSTGRES_DB=phase16 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
docker inspect --format '{{json .Mounts}}' researchassistant-phase16-mvow53llc5uga5w3
docker inspect --format '{{json .HostConfig.Tmpfs}}' researchassistant-phase16-mvow53llc5uga5w3
docker port researchassistant-phase16-mvow53llc5uga5w3 5432/tcp
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/reindex_documents.py --document-id c18e342c-8d38-40d1-b1ab-c927c156e6b6 --dry-run
.\.venv\Scripts\python.exe scripts/reindex_documents.py --document-id c18e342c-8d38-40d1-b1ab-c927c156e6b6 --apply
```

The explicit apply command was run first with `LLM_PROVIDER=local` (failed during client construction), then with `LLM_PROVIDER=mock` (successful; generation remained unused), and again for idempotency and recovery. The fault-injection pass called the same `scripts.reindex_documents.reindex_documents` function with `VectorRepository.upsert_chunks` patched to raise after its real upsert; it was scoped to this document only. Direct read-only checks queried the disposable PostgreSQL row, active Chroma collection, FTS5 rows, and the source PDF pages.

Cleanup removed the uniquely named tmpfs container, the first attempt's anonymous volume, and the entire unique temp root. Final checks confirmed: rehearsal container absent, initial anonymous volume absent, and temp root absent. No Docker prune, shared-volume deletion, existing collection access, or project `.env` edit occurred. Only this report was updated.

### Decision

**The PostgreSQL-backed reindex workflow passed the core isolated dry-run, selected apply, indexing, retrieval/provenance, idempotency, cleanup, and retry checks.** It passed with an explicit mock generation adapter solely because the configured `local` generation provider prevents `RAGClient` initialization; generation was never called and embeddings were local FastEmbed. Failure cleanup leaves a stale database chunk count, which the injected failure demonstrated.

This is sufficient evidence to proceed to further controlled migration planning, but **not a recommendation to migrate the actual corpus yet**. Before actual-corpus migration, resolve or explicitly configure the unsupported local generation-provider initialization and stale `chunk_count` behavior, then rerun the isolated rehearsal with the exact production-intended environment. Afterward, conduct a dry-run against an isolated clone containing the originals and associated indexes, inspect all selected records/missing/scanned files, then trial a small selected batch. Keep the original corpus and old collection untouched until those checks pass.

---

## Phase 1.7 addendum — local-provider and count-consistency fixes (2026-10-26)

The Phase 1.6 blockers were fixed and the PostgreSQL-backed rehearsal was repeated using a new temporary environment. This addendum preserves the Phase 1.6 results above.

### Isolation and command results

- Docker Engine `29.9.1` was reachable. The new container `researchassistant-phase17-827f1ebe0f` published PostgreSQL only on `127.0.0.1:61379`; its data directory was tmpfs and `docker inspect` showed `Mounts=[]`.
- Effective SQLAlchemy endpoint was `postgresql+asyncpg://phase17@127.0.0.1:61379/phase17`. The resolved upload, Chroma, embedding-vector cache, and FastEmbed model cache were all newly created below `%TEMP%\researchassistant-phase17-827f1ebe0f`; none overlapped project storage. Process overrides set `LLM_PROVIDER=local`, `EMBEDDING_PROVIDER=fastembed`, `BAAI/bge-small-en-v1.5`, and dimension 384. No `.env` file was changed.
- Alembic successfully applied revisions `0001` through `0004`. The synthetic fixture was a new two-page PDF named `phase17_known_facts.pdf`, with BLUEBIRD on page 1 and launch year 2039 on page 2.
- `python scripts/reindex_documents.py --document-id e3ff7e15-ebda-4745-a4b5-b20b3030e209 --dry-run` selected exactly the fixture. The source was present. Before/after the dry-run, the row remained `failed`, stage `failed`, `chunk_count=17`, and the Chroma, embedding-cache, and model-cache directories remained empty.
- The same scoped `--apply` under `LLM_PROVIDER=local` completed `1 ready, 0 failed`. This confirms reindex construction no longer initializes generation. FastEmbed downloaded its public model artifacts to the isolated model cache; no Gemini, other generation endpoint, or paid API was called.

### Counts, retrieval, timings, failure, and retry

- Apply indexed 2 chunks in 1 embedding batch. Database state was `indexed/ready`, `chunk_count=2`, no error, and the original PDF still existed. Chroma held 2 records and FTS5 held 2 rows; both stores had the same two unique deterministic chunk IDs in `reseaembed_BAAI_bge-small-en-v1_5_fastembed-0_9_0_chunkidv2_384`.
- The application's configured `ResearchRetriever` used FastEmbed query embeddings against that active namespace. It retrieved `BLUEBIRD` from `phase17_known_facts.pdf`, page 1, locator `Results · passage 1`, and `2039` from the same original filename, page 2, locator `Conclusion · passage 2`. Warm query times were 0.581 s and 0.040 s.
- Cold apply took 32.856 s: extraction 1.719 s, chunk stage 30.676 s, embedding 0.095 s, indexing 0.290 s; 2 chunks and 1 embedding batch. The cold chunk-stage time includes FastEmbed/tokenizer initialization and the model download (about 28 s); it is not representative of warm chunking. Warm repeat took 2.502 s (extraction 1.751 s, chunking 0.574 s, embedding 0.002 s, indexing 0.097 s). The repeat kept the count at 2 with no duplicate count growth.
- A fault was injected after the real Chroma and FTS5 upsert had each stored 2 chunks. Pipeline cleanup deleted both records; the actual reindex function recorded `failed/failed`, preserved the injected error, and set the database count to zero. Read-back confirmed Chroma=0, FTS5=0, and matching empty ID sets. A subsequent explicitly scoped CLI `--apply` succeeded; final read-back again showed `indexed/ready`, count 2, Chroma=2, FTS5=2, and successful page-specific retrieval.
- A first synthetic-record setup attempt used an invalid overlength document ID and PostgreSQL rejected it; the transaction rolled back. The fixture was recreated with a valid UUID. Both attempts and any generated files were contained in the disposable environment, which was removed after validation.

### Fixes and cleanup

`QueryPipeline` now creates its generator only when sufficient evidence reaches the generation step. Local FastEmbed ingestion can initialize and run with `LLM_PROVIDER=local`; a later question requiring generation still raises the explicit unsupported-provider error, which the backend gateway preserves. Selecting Gemini remains compatible with the existing factory; regression tests use a stub client and make no live request.

Reindex now sets `chunk_count=0` at the start of an attempt, verifies nonzero reported count against Chroma and FTS5 counts and ID sets before marking a document indexed, and cleans/verifies the active document records on unsuccessful attempts. Failures remain visible in status and error text. Document cleanup now removes FTS5 orphans even when Chroma has no matching records.

After all checks, the exact temporary container was removed with `docker rm --force`; its inspect result showed no mounted volumes. The unique Phase 1.7 temp root was removed. Final checks confirmed both were absent. No prune command, existing container, database, upload, collection, FTS file, or project environment file was touched.

### Decision

**The local-provider, selected-document PostgreSQL reindex workflow passed this isolated rehearsal, including dry-run safety, actual FastEmbed ingestion, count/ID agreement, page citations, idempotent repeat, failure cleanup, and retry.** Proceed with a reviewed dry-run and small selected-document trial against a separately verified isolated clone before any actual-corpus work. Do not treat this synthetic fixture as evidence about the contents or OCR needs of actual user PDFs.

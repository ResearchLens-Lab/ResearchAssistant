# Phase 1.8 — Real-Document Validation in an Isolated Clone

**Result: STOPPED SAFELY — no corpus clone, dry-run, or reindex was performed.** The available project state has two conflicting database candidates, and neither is currently paired with a verifiably consistent, complete set of original uploads and indexes. This report records the blocker rather than treating synthetic Phase 1.7 results as validation of the actual research PDFs.

## Scope and safety decision

The requested source inspection found only local development endpoints, not a known remote or production database. However, local/development status alone did not establish which endpoint held the current corpus or allow a complete consistent clone:

| Candidate | Verified configuration/state | Blocker |
|---|---|---|
| Host configuration | `backend/.env.local` names `localhost:5432/researchassistant`; `APP_ENV` is unset and the application default is `development`. `localhost` resolved to loopback. Windows service `postgresql-x64-18` is running with PostgreSQL data directory `C:\Program Files\PostgreSQL\18\data` (cluster version 18). | A read-only connection using the configured credentials failed authentication for user `postgres`; no database identity or rows could be read. The configured relative upload directory `storage/uploads` is absent at the repository root and under `backend/`. |
| Docker Compose candidate | The stopped `researchassistant-api-1` and `researchassistant-postgres-1` containers belong to Compose project `researchassistant`. The API container was configured for `postgres:5432/researchassistant`, `/srv/storage/uploads`, and Gemini embeddings (`gemini-embedding-001`, 768 dimensions). Its upload and Chroma paths are named volumes. The PostgreSQL 16 container and API are both exited. | This is a distinct, historical runtime configuration from the current host `.env.local` and root `.env` (FastEmbed, 384 dimensions). The Chroma volume is also mounted read-write by the still-running `researchlens-chromadb` container. |

The active Chroma server has the same `researchassistant_chroma_data` volume mounted at `/chroma/chroma`, publishes port 8001 on all interfaces, and had zero established host TCP connections at the inspection. The API container was stopped. Those observations do not prove that no client can write through the live server or that a raw copy of its Chroma and colocated FTS5 files would be a consistent snapshot. Stopping or quiescing the service was outside the request. The repository `.chroma` directory is another, separate local index (including `chroma.sqlite3`, `researchlens_lexical.sqlite3`, and an embedding-cache database); it cannot be safely paired with either candidate database without confirming the authoritative records and source files.

**Safety decision:** a complete source corpus and a consistent snapshot of its database, originals, Chroma, and FTS5 cannot be positively established from the available configuration. I stopped before copying source data, creating a test environment, running migrations, or invoking the reindex utility. No existing service was stopped or modified.

## Checks performed

Read the five requested historical reports: `PROJECT_AUDIT.md`, `PHASE1_VALIDATION.md`, `PHASE1_MIGRATION_REPORT.md`, `PHASE1_ISOLATED_REHEARSAL.md`, and `PHASE1_7_FIX_VALIDATION.md`. Their synthetic isolated validations remain historical evidence only; they do not establish the state or contents of the real corpus.

Read-only environment checks established:

- Docker Engine is reachable. `docker ps -a` showed the project API and PostgreSQL containers exited and the Chroma container running.
- Host PostgreSQL is a running local PostgreSQL 18 Windows service. Its data directory exists and has `PG_VERSION` 18.
- Current host settings resolve to a local development DB endpoint, but authentication failed before a transaction or query could run. The attempted connection was read-only in intent; no source rows were returned and no write transaction began.
- Current root RAG settings use `.chroma`, local persistence, FastEmbed `BAAI/bge-small-en-v1.5`, and 384 dimensions. The current backend upload setting is `./storage/uploads`; neither likely repository-relative upload location exists.
- The stopped Compose API container is configured differently (Gemini embeddings at 768 dimensions and Docker-mounted upload/Chroma volumes). Its PostgreSQL container uses a separate named volume. The live Chroma server shares the API's Chroma volume.
- `git status --short` showed extensive pre-existing modifications and untracked files from earlier work. No existing file was edited by this phase.

No API credentials, database passwords, or secret values were printed or added to this report.

## Corpus inventory and document availability

No source database inventory query succeeded, and the Compose PostgreSQL volume was not opened or copied. Therefore the following are **not verified**:

- Source document totals, statuses, chunk counts, duplicate records, or missing-file counts.
- Whether Cormen or Horowitz exists in either database or upload store.
- Original-file availability, PDF page count, extracted text, or OCR requirement for either book.
- Chroma collection identities, collection contents, FTS5 rows, or their relationship to either database candidate.

There is no basis to report a whole-corpus dry-run selection or excluded-record reasons. The requested `python scripts/reindex_documents.py --all --dry-run` was **not run**.

## Selected-document trial and verification

No document ID could be obtained from an authoritative source database. Consequently, no document-scoped dry-run or `--apply` was run. No real PDF was extracted, embedded, indexed, retrieved, or reindexed. Before/after counts, citation evidence, and idempotency results for real documents are **unavailable**, not failed or passed.

The Phase 1.7 test results cited in the historical reports use synthetic PDFs in disposable storage. They are not evidence that either uploaded book is extractable or retrievable.

## Commands and actions

The checks used read-only configuration parsing, service/process/port inspection, and Docker metadata inspection. The relevant commands were:

```text
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker volume ls --format '{{.Name}}'
Get-Service -Name postgresql-x64-18
Get-CimInstance Win32_Service -Filter "Name='postgresql-x64-18'"
Get-NetTCPConnection -LocalPort 5432,8001 -State Listen
Get-NetTCPConnection -LocalPort 8001 -State Established
docker inspect researchassistant-api-1
docker inspect researchassistant-postgres-1
docker inspect researchlens-chromadb
.\.venv\Scripts\python.exe -  # asyncpg read-only connection using Settings() from backend/.env.local
```

The final Python probe validated that the configured environment was development and resolved to loopback, then attempted to connect to `127.0.0.1:5432/researchassistant`; PostgreSQL rejected authentication for `postgres`. The probe did not print the connection string or password. No successful query followed. No reindex or migration command ran.

## Files, cleanup, and remaining prerequisites

- **Created:** `PHASE1_8_CORPUS_CLONE_VALIDATION.md` only.
- **Modified:** no existing project files.
- **Temporary resources:** none created; therefore none required cleanup.
- **Existing databases, Docker containers, volumes, `.chroma` files, uploads, and environment files:** not modified. No container was stopped, no volume was mounted by a helper, and no prune/delete operation ran.

Before resuming Phase 1.8, establish which local database is authoritative and make its matching original uploads and index state available in an isolated, consistent snapshot. For the host candidate, the configured DB credentials must be corrected or an authorized read-only snapshot/backup supplied, and the matching upload/index paths must be identified. For the Compose candidate, a safe snapshot of PostgreSQL, uploads, and the live shared Chroma/FTS state must be arranged without writing to the source; while Chroma remains live and potentially writable, its raw persistent volume cannot be assumed consistent. The current embedding namespace/configuration difference (historical Gemini 768 versus current FastEmbed 384) must also be accounted for in the clone; do not mix or overwrite collections.

Once those prerequisites are met, verify the clone's DB endpoint and every target path before writes, inventory all documents in the clone, dry-run `--all`, then trial at most one accessible text PDF with a document-scoped apply.

## Decision

**NO-GO for real-document validation or any corpus migration at this time.** The blocker is not an ingestion failure: the authoritative corpus source and a safe, consistent set of its database, original files, Chroma, and FTS5 indexes have not been established. No actual-document pipeline result can be claimed. The next required action is to provide/establish an authoritative local-development backup or safe snapshot that includes all four components, then repeat the clone-only workflow.

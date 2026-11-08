# Phase 4A — Ingestion Reliability Validation

Date: 2026-10-26

## Outcome

The isolated reliability checks pass for the current single-process ingestion architecture. The implementation now treats ingestion as complete only after Chroma and SQLite FTS5 agree on a non-empty, unique set of chunk IDs. Timeouts request cooperative cancellation, failed attempts clean partial indexes where possible, retries claim failed rows atomically, and deletion reports index-cleanup errors instead of silently removing the paper record and original files.

This is not evidence of multi-process or crash-proof job orchestration. Same-document exclusion is held in an in-process lock; multiple API worker processes do not share it. There is no durable job queue or persisted worker lease. A process crash can leave a `processing` row until the existing stale-status recovery path runs during a later status/list request.

## Verified defects addressed

- The async gateway used `wait_for(to_thread(...))`; a timeout abandoned the await while the synchronous worker continued. Retrying could overlap with the still-running operation. Ingestion calls now receive a cancellation event; the gateway requests cancellation on timeout or caller cancellation and observes the worker's eventual completion. The document lock remains held until safe cancellation and cleanup finish.
- The gateway's same-process busy response did not identify that an active attempt owned cleanup. It now reports `active_attempt`, allowing the service to avoid racing cleanup against that attempt. Deletion of an actively ingested document or paper is rejected in the same process.
- Upload status could become ready based on the pipeline response alone. The service now checks nonzero Chroma/FTS counts and exact unique-ID parity before setting the terminal indexed state.
- FTS write errors were suppressed, index counts could hide duplicate FTS IDs, and document cleanup could skip FTS cleanup when Chroma had no rows. Errors now propagate, parity checks account for uniqueness, and cleanup attempts both stores.
- A failed/retried document could retain stale chunk counts/progress. Failure, retry claim, and stale recovery now reset counts and progress to reflect the actual state.
- Paper deletion previously committed the database/file deletion before best-effort vector cleanup. It now removes index rows first and surfaces cleanup failure while retaining the database paper and original files.

## Changes made for this phase

- `backend/app/core/exceptions.py`: typed ingestion-timeout exception.
- `backend/app/integrations/rag_client.py`: cancellation propagation, active-attempt marker/tracking, same-process delete guard, safe lock lifecycle.
- `backend/app/integrations/rag_gateway.py`: managed worker await and cooperative cancellation on timeout/caller cancellation.
- `backend/app/services/document_service.py`: index parity gate, atomic retry claim, accurate terminal progress/count resets, cleanup handling.
- `backend/app/services/paper_service.py`: fail-safe ordering for index cleanup, database deletion, and original-file deletion.
- `rag/pipelines/ingest_pipeline.py`: cancellation at safe stage/batch boundaries, stale-ID reconciliation, parity verification, partial-index cleanup with primary error preservation.
- `rag/vectorstore/vector_repository.py`: visible FTS failures, unique-ID accounting, stale-ID reconciliation, comprehensive document cleanup.
- Focused tests: `backend/tests/conftest.py`, `backend/tests/test_documents.py`, `backend/tests/test_papers.py`, `backend/tests/test_rag_client.py`, `backend/tests/test_rag_gateway.py`, `rag/tests/test_ingest_pipeline.py`, and `rag/tests/test_vectorstore.py`.

The repository already contained extensive unrelated uncommitted work before this phase. It remains untouched and uncommitted; the file list above names only files changed for this reliability work.

## Validation performed

All tests used local/fake components and isolated temporary index storage. No Gemini or paid API was called. No real user corpus was reindexed.

| Check | Command | Result |
| --- | --- | --- |
| Targeted reliability tests | `.venv\Scripts\python.exe -m pytest rag/tests/test_ingest_pipeline.py rag/tests/test_vectorstore.py backend/tests/test_rag_client.py backend/tests/test_rag_gateway.py backend/tests/test_documents.py backend/tests/test_papers.py backend/tests/test_reindex_consistency.py -q` | **71 passed** in 50.85s |
| Full RAG/backend suite | `.venv\Scripts\python.exe -m pytest rag/tests backend/tests -q` | **201 passed** in 109.84s |
| Frontend tests | `npm.cmd test` (from `frontend`) | **18 passed** |
| Frontend lint | `npm.cmd run lint` (from `frontend`) | Passed |
| Frontend typecheck | `npm.cmd run typecheck` (from `frontend`) | Passed |
| Production build | `npm.cmd run build` (from `frontend`) | Passed; Next.js reported the existing warning that its ESLint plugin is not detected in the ESLint configuration |
| Patch whitespace check | `git diff --check` | Passed; Git emitted line-ending normalization warnings for pre-existing modified files |

Additional focused rerun of ingestion/gateway/client/document tests: **47 passed** in 31.52s.

These tests exercise simulated worker delays, timeout cancellation, immediate same-document retry exclusion, parallel different-document work, active deletion rejection, retry races, stale recovery, FTS/Chroma mismatch, partial cleanup, and repeated-ingestion reconciliation. They do not measure real PDF throughput or external provider latency.

## Operational semantics and limitations

- Ingestion checks cancellation between synchronous operations and embedding/index batches. A currently executing parser, model inference call, or database operation may not be interruptible; cancellation takes effect at the next safe boundary. The request can time out before that worker has completed cleanup, and an immediate retry may be reported as already active until the worker exits.
- The lock and active-paper map are process-local. With multiple API worker processes or hosts, concurrent jobs for the same document can still race. Production multi-worker use needs a database-backed lease/job record or a durable queue with ownership and heartbeat semantics.
- This is synchronous request-driven ingestion, not a durable background worker. Process termination cannot run cleanup. Existing stale-processing recovery is triggered by later reads rather than a startup sweeper; no automatic recovery time bound is guaranteed.
- Index deletion and relational database commit cannot be made atomic across the two systems. If the subsequent database transaction fails after successful vector cleanup, the original record/files remain but need reindexing.
- No actual PDF, Gemini behavior, multi-process race, forced process crash, or production storage was tested in this phase. No real-document readiness claim is made.

## Decision

**GO for continued isolated validation and a single-process local deployment** using the tested behavior. **NO-GO for claiming multi-worker production-grade ingestion reliability** until same-document ownership and recovery are durable across processes and restarts. Before production rollout, add a durable job/lease mechanism, a periodic stale-job recovery worker, and integration tests that use multiple API processes against isolated databases and indexes. Continue to require real-document validation separately.

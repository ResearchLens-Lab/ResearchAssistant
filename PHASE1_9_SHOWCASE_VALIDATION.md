# Phase 1.9 — Clean Showcase Environment and End-to-End RAG Validation

## Decision

**GO for the next phase of fresh local upload and retrieval work.** The authenticated FastAPI upload flow indexed a generated three-page PDF with local FastEmbed. The configured ResearchRetriever returned all three known facts with the correct filename, original page number, and locator. Failure and retry also worked through the API.

This validates a **synthetic showcase fixture only**. No actual research PDF, including Cormen or Horowitz, was tested.

## Isolation and configuration

A unique environment was created under:

%TEMP%\researchassistant-p19-40a9d6df9330a55d

The disposable PostgreSQL container was researchassistant-p19-40a9d6df9330a55d-postgres using postgres:16-alpine. Its data directory was on 512 MiB tmpfs, it had no mounted volumes, and Docker published its ephemeral port 61695 on 127.0.0.1 only. Before writes, the unique temp root and upload, Chroma, FTS5, embedding-cache, and model-cache paths were resolved and confirmed absent. These locations were separate from the repository and existing application storage.

Existing Alembic migrations 0001–0004 initialized this database. A read-back confirmed database phase19, the temporary PostgreSQL data directory, and revision 0004.

The API ran at 127.0.0.1:18765. Process-only overrides were used; no .env files were edited:

| Variable | Effective value |
|---|---|
| APP_ENV | development |
| DATABASE_URL | postgresql+asyncpg to 127.0.0.1:61695/phase19 (credentials omitted) |
| UPLOAD_DIR | unique temp uploads directory |
| CHROMA_PERSIST_DIR | unique temp chroma directory |
| FTS5 | CHROMA_PERSIST_DIR/researchlens_lexical.sqlite3 |
| EMBEDDING_CACHE_PATH | unique temp embedding-cache/vectors.sqlite3 |
| FASTEMBED_CACHE_DIR | unique temp model-cache directory |
| CHROMA_USE_HTTP | false |
| CHROMA_COLLECTION_NAME | phase19_showcase base name |
| EMBEDDING_PROVIDER / MODEL / DIMENSION | fastembed / BAAI/bge-small-en-v1.5 / 384 |
| LLM_PROVIDER | local |
| GEMINI_API_KEY, LLM_API_KEY | blank in API and validation processes |

The active collection was phaseembed_BAAI_bge-small-en-v1_5_fastembed-0_9_0_chunkidv2_384. Metadata confirmed FastEmbed 0.9.0, 384 dimensions, cosine distance, and the document-scoped chunk ID schema. No Gemini or paid embedding/generation endpoint was called. FastEmbed downloaded public model files from Hugging Face into the disposable model cache.

## Actual application flow exercised

The frontend documentsService sends multipart form data with file and paper_id and uses a bearer access token. The same supported API flow was exercised:

1. POST /api/v1/auth/register
2. POST /api/v1/auth/login
3. POST /api/v1/papers
4. Authenticated POST /api/v1/documents/upload
5. Authenticated GET /api/v1/documents/{id} and GET /api/v1/documents/{id}/file

Authentication and ownership checks remained enabled. DocumentService stored the file under a generated document ID, committed the row, and called RAGGateway. The gateway invoked the in-process RAGClient, which ran PDF extraction, chunking, FastEmbed, Chroma, and colocated FTS5. Upload waited for ingestion completion.

## Upload, indexing, and timings

The fixture was phase19_known_facts.pdf, a generated 2,501-byte, three-page text PDF. The API download endpoint returned the same bytes byte-for-byte. Reopening the stored PDF confirmed three pages and the correct page-specific facts.

Registration and paper creation returned HTTP 201; login returned HTTP 200. Upload returned HTTP 201 with document 063c7c49-9f47-49fd-8b05-bcf35c475d41, status indexed, stage ready, progress 100, 3 chunks, and no error. A subsequent status GET agreed. PostgreSQL confirmed the row and stored original.

Cold upload timings from API/RAG logs:

| Stage | Measured time |
|---|---:|
| Full authenticated upload request | 39.589 s |
| RAG gateway round trip | 39.483 s |
| Ingestion pipeline total | 34.805 s |
| PDF extraction (3 pages, 603 characters) | 1.781 s |
| Chunking (3 chunks) | 32.369 s |
| Embeddings (1 batch of 3 chunks) | 0.190 s |
| Indexing | 0.404 s (Chroma 0.353 s, FTS5 0.051 s) |
| Progress persistence | 7 commits, 0.1005 s aggregate commit time |

Cold chunking included first-use tokenizer/model initialization and model download. Warm same-document re-ingestion through RAGClient took 2.659 s and preserved the three chunk IDs and counts. The separate one-page retry took 0.246 s pipeline time.

## Counts and evidence retrieval

The configured ResearchRetriever was instantiated directly with the same local settings and FastEmbed query embeddings. No answer-generation method ran.

| Question | Retrieved fact | Filename | Original page locator |
|---|---|---|---|
| What is the calibration beacon named? | GLACIER-ORCHID-41 | phase19_known_facts.pdf | Page 1 — Introduction · passage 1 |
| Where was the observation station installed? | 73.25 degrees north and 142.6 degrees east | phase19_known_facts.pdf | Page 2 — Methodology · passage 2 |
| What bloom threshold did the study measure? | 17.6 milligrams per liter on 2025-04-19 | phase19_known_facts.pdf | Page 3 — Results · passage 3 |
| What was the recovery marker? | SILVER-MAPLE-88 | phase19_scanned_fixture.pdf | Page 1 — Header / Abstract · passage 1 |

Each returned passage contained the expected text, filename, document ID, and original PDF page. The first three checks were each repeated three times against the quiescent store; all passed. Their mean warm retrieval times were 0.014 s, 0.061 s, and 0.014 s. The retry-marker query averaged 0.011 s over three runs. Query vectors were 384-dimensional.

After retry, PostgreSQL held 2 indexed/ready documents with chunk counts 3 and 1. Chroma held 4 chunks and FTS5 held 4 rows. Both contained the same 4 unique chunk IDs; no duplicates were present.

## Failure and retry

A second authenticated upload used a generated blank one-page PDF. Upload returned HTTP 201, then the document reached failed with: “PDF contains no extractable text; scanned PDFs require OCR, which is not enabled.” It had zero Chroma and FTS5 rows.

To exercise the supported retry endpoint in the disposable environment, only that fixture’s temp original was replaced with a valid one-page text PDF containing SILVER-MAPLE-88. Authenticated POST /api/v1/documents/{id}/retry returned HTTP 200 and indexed/ready with one chunk. Chroma and FTS5 each had that chunk, and retrieval returned the correct filename and page 1. This tests retry with a corrected stored source; it does not claim scanned-PDF OCR works.

One immediate direct query after retry returned Chroma’s InternalError: “Error finding id”. A subsequent new-process query passed, and repeated queries against the quiescent store passed. The error was not reproducible, so its cause remains unconfirmed; no code change was made. It occurred during a separate direct probe while the API’s embedded Chroma client was also running, not during upload/indexing.

## Errors, changes, and tests

- The first fixture registration used the reserved .test domain and was rejected with HTTP 422. No account was created by that attempt; the fixture was rerun with example.com.
- Alembic succeeded. An initial verification probe incorrectly passed SQLAlchemy’s postgresql+asyncpg URL scheme directly to asyncpg. A corrected explicit local host/port query confirmed revision 0004.
- One verification command had a local variable-scope error after its three evidence checks had already passed. Idempotency and retrieval were rerun successfully in corrected probes.
- No application defect requiring a code fix was demonstrated. No application code or permanent regression test was added. The actual HTTP upload, failure, retry, and retrieval checks ran against the disposable environment.
- No existing project test suite was run in this phase.

## Cleanup and files changed

The temporary API process was stopped and port 18765 had no listener afterward. The exact disposable PostgreSQL container was removed; it had no mounts, and no Docker volume was created. The generated test password and email were removed from the temp fixture metadata before cleanup.

**Cleanup is partial:** the task’s temp directory remains at:

C:\Users\gorav\AppData\Local\Temp\researchassistant-p19-40a9d6df9330a55d

The automatic safety review rejected both recursive deletion and a file-by-file deletion command with the stated reason “blocked by policy”. I did not use another deletion mechanism. The directory contains only the synthetic PDFs, local model cache, Chroma/FTS/cache files, and validation metadata created here; it is separate from application data.

Manual cleanup command:

```powershell
Remove-Item -LiteralPath 'C:\Users\gorav\AppData\Local\Temp\researchassistant-p19-40a9d6df9330a55d' -Recurse -Force
```

No existing database, upload, collection, Docker service, environment file, or uncommitted project change was modified. **The only repository file created by this task is this report.**

## Readiness

**Fresh synthetic document upload and local retrieval are ready to proceed to the next phase.** Upload, local embedding, persisted status, Chroma/FTS parity, page provenance, same-document re-ingestion, and retry passed in isolation. Validate an accessible actual research PDF through the same isolated workflow before claiming real-document readiness. OCR remains unsupported for scanned PDFs. Investigate the one non-reproducible immediate Chroma query error during future concurrent-access testing.






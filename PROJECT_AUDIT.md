# ResearchAssistant / ResearchLens — Read-Only Project Audit

**Audit date:** 2026-10-26  
**Scope:** Source/configuration inspection only. No tests, builds, application services, database commands, Gemini requests, or paid API calls were run for this audit. The repository had extensive pre-existing edits and untracked files at audit start; they were preserved. This report is the only file created for this audit.

## Executive summary

ResearchAssistant is a monorepo for a document-grounded research application. It has a Next.js UI, FastAPI API and PostgreSQL persistence, an in-process Python RAG package using PyMuPDF/other parsers, ChromaDB plus a local SQLite FTS5 index, and a separate knowledge-graph boundary. The RAG flow already has section-aware chunks, page/file provenance, scoped multi-document retrieval, citation mapping, basic evidence sufficiency and answer/citation verification.

The current working tree reflects a partially implemented local-first transition. The root `.env` selects `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions) for embeddings and Gemini (`gemini-3.8-flash`) for generation. A local embedding cache and model-specific Chroma collection naming are present. This decouples document indexing from Gemini quotas when that configuration reaches the running API. However, the query pipeline still invokes a generative model for every answer, summary, or comparison with sufficient retrieved evidence. A new SQLite generation-cache/budget module exists but has no observed caller, and the configured `LLM_DAILY_CALL_BUDGET` is not declared in RAG settings or enforced by the LLM client. A clearly labelled local evidence-only answer path is not wired into the query pipeline.

**Current status:** useful RAG foundation and substantial UI/API features; ingestion is currently configured to be local-embedding-first, but end-to-end indexing with the selected provider has not been validated in this audit. OCR is not implemented. Real model quality, document answer quality, production reliability, and live quota/account state remain unverified. The current Gemini error screenshot/history indicates an embedding endpoint HTTP 429 with a quota/billing message, but does not identify the Google project, account tier, or exact exhausted metric.

## Repository map and responsibilities

| Path | Responsibility |
|---|---|
| `frontend/` | Next.js App Router application: auth, project/library, upload, research chat, citations, comparison, search, graph/trends/settings screens, API services, query hooks and state. |
| `backend/app/` | FastAPI routes, schemas, services, repositories, SQLAlchemy models, auth, database/session setup, RAG and graph adapters. |
| `backend/migrations/` | Alembic schema migrations; document processing stage/progress are represented by migrations 0003–0004 in this working tree. |
| `rag/` | Python RAG engine: settings, document loaders/normalization, chunking, embedders/cache, Chroma/lexical storage, retrieval/context, generation/citations, research orchestration and evaluation/tests. |
| `knowledge-graph/` | Neo4j-oriented graph models, Cypher/service and graph ingestion/API code. Backend README describes the graph integration boundary as a stub returning 503 until wired (`backend/README.md:52-57`). |
| `infrastructure/` | Docker Compose definitions for backend/PostgreSQL and related infrastructure, including persistent upload, Chroma and model-cache volumes. |
| `scripts/` | CLI ingest/query/evaluation/benchmark/reindex utilities. `scripts/reindex_documents.py` is present in the working tree; see migration notes below. |
| `docs/` | Architecture and RAG design, implementation notes and design assets. |
| Root files | `.env`/examples, dependencies, Docker Compose, project overview and workspace configuration. Secret values were not read into this report or printed. |

The project README describes the intended RAG functionality at `README.md:18-27`; the backend README describes the frontend → API → services → PostgreSQL/files and RAG/graph boundaries at `backend/README.md:5-16`.

## Current architecture and data flow

### Ingestion

1. The frontend uploads individual files or a batch to the authenticated document routes (`backend/app/routes/documents.py:15-42`). The backend validates and stores originals, creates document rows and processes each document independently (`backend/app/services/document_service.py:42-160`). Retry uses the stored original and rejects concurrent/ineligible retries (`backend/app/services/document_service.py:285-306`).
2. `DocumentService` calls the `RAGGateway`; the gateway moves synchronous RAG work to a thread and applies `RAG_INGEST_TIMEOUT_SECONDS` (`backend/app/integrations/rag_gateway.py:48-85`). It converts timeout to a generic RAG timeout error. A Python `asyncio.wait_for` timeout does not stop work already executing in the worker thread; therefore a timed-out ingestion may continue in the background unless the underlying pipeline finishes or is otherwise controlled. This creates a possible retry/duplicate-work race despite the per-document lock in `rag_client.py`.
3. `DocumentLoaderFactory` supports PDF, text/Markdown-like text, DOCX, CSV, XLSX, PPTX, JSON and HTML (`rag/ingestion/document_loader.py:173-198`). PDF uses PyMuPDF, extracts one page at a time, retains original 1-based PDF page numbers and reports page progress (`rag/ingestion/document_loader.py:35-95`). If no page has selectable text, it raises a clear “scanned PDFs require OCR” error (`rag/ingestion/document_loader.py:86-87`). No OCR provider or OCR pipeline was found. Normalization occurs through `DocumentNormalizer` after extraction.
4. The section-aware chunker is configured to 500 words with 80-word overlap (`rag/config/settings.py:52-54`, `rag/chunking/strategies.py:30-44`). It attempts to keep section and page provenance, splitting oversized text while maintaining page locators (`rag/chunking/strategies.py:90-180,196-255`). This is word-based chunking rather than tokenizer-budget chunking; FastEmbed's selected model has a finite input window, so pathological or token-dense text deserves explicit truncation/chunk-boundary validation.
5. Ingestion generates embeddings in configured batches (64 by default), then upserts each chunk batch into Chroma and SQLite FTS5. It logs extraction/chunk/embedding/index measurements and removes partial document chunks if a later batch fails (`rag/pipelines/ingest_pipeline.py:142-248`). Stable chunk IDs make same-collection upserts repeatable (`rag/vectorstore/vector_repository.py:46-76`).
6. The backend persists per-file stage, progress, elapsed timestamps, counters and terminal status from callbacks. Progress commits are throttled to 750ms and stages are persisted (`backend/app/services/document_service.py:177-216`); stale processing rows are eventually marked failed and retryable, with a minimum stale interval of 15 minutes (`backend/app/services/document_service.py:329-346`). The frontend renders stage/progress/elapsed state (`frontend/src/components/papers/DocumentProcessingProgress.jsx:7-44`).

### Retrieval, answer generation and citations

1. `QueryPipeline` applies explicit selected-paper scope and bounded query planning, including retrieval retries for missing terms (`rag/pipelines/query_pipeline.py:60-119`). `ResearchRetriever` embeds the query, performs filtered dense retrieval, then uses lexical results and fusion/ranking (`rag/retrieval/retriever.py:36-98`; `rag/vectorstore/vector_repository.py:86-155`). The lexical backend is SQLite FTS5; dense vectors are in Chroma.
2. The context builder budgets and formats retrieved sources (`rag/context/context_builder.py:20-`). The configured retrieval defaults are top-k 5 and maximum context 3,500 tokens (`rag/config/settings.py:56-60`). The reranker currently defaults to `IdentityReranker`, which preserves existing order rather than reranking semantically (`rag/retrieval/reranker.py:24-30`); settings disable reranking by default.
3. With sufficient evidence, the pipeline always calls `GroundedGenerator` for QA, summaries and comparisons (`rag/pipelines/query_pipeline.py:119-147`). It then validates citation tags and checks answer claims. Optional LLM judging is disabled by default, but claim repair is enabled and can add a generation call (`rag/pipelines/query_pipeline.py:154-170`). Metadata records model-call count (`rag/pipelines/query_pipeline.py:201-225`).
4. Citation objects retain source ID, paper/document/chunk IDs, filename, page start/end, section, locator and exact chunk text (`rag/citations/citation_mapper.py:13-33`). Page-range provenance is available to the UI. Citation-tag validity is checked, but claim support is largely a deterministic lexical/numeric heuristic (`rag/research/claim_verifier.py:71-160`), not a robust semantic entailment proof. It can miss paraphrases, accept coincidental word overlap, or misjudge numerical claims.

## Embeddings, Gemini, configuration and usage

### Verified local configuration

The root `.env` has `EMBEDDING_PROVIDER=fastembed`, model `BAAI/bge-small-en-v1.5`, dimension 384, and `LLM_PROVIDER=gemini`, model `gemini-3.8-flash`. A Gemini API key is present in the root environment file; its value is intentionally not included. The RAG settings defaults match these embedding and generation choices (`rag/config/settings.py:33-49`). The backend Compose service forwards `GEMINI_API_KEY`, the embedding/generation model variables, and local model-cache path/volume (`infrastructure/docker-compose.backend.yml:25-52`). This verifies configuration forwarding in source, not that a running container currently received the key or successfully authenticated.

`FastEmbedder` is implemented using FastEmbed/ONNX and uses a process-level model cache plus a SQLite vector cache keyed by FastEmbed version/model and content hash (`rag/embeddings/embedder.py:98-155`; `rag/embeddings/cache.py:13-89`). Chroma collection names are namespaced by embedding provider/model/dimension and FastEmbed version (`rag/vectorstore/collection_manager.py:23-43`). This protects dimension/model separation; already indexed data in a previous collection will not automatically appear in the new collection. Reindexing is needed to populate the active namespace.

**Incomplete local-first work:** the new embedding provider, cache, collection identity and Docker volume are present, but there was no end-to-end local-provider indexing/retrieval run during this audit. Prior to this audit request, a local FastEmbed model load/embedding smoke call was observed to return 384-dimensional vectors, taking about 45 seconds on first load while downloading model files. That is a cold-start observation, not an ingestion benchmark. No conclusion about warm full-document throughput follows from it.

### Gemini and the reported limit error

The Gemini generation client uses Google's `google-genai` SDK and calls `models.generate_content` / streaming (`rag/generation/llm_client.py:203-263`). Gemini embedding calls are separate and were used when the previous embedding provider was configured as Gemini (`rag/embeddings/embedder.py:219-304`). The app therefore has separable embedding and generation providers; this working tree now selects local embeddings, but does not yet make generation selective or local-first.

The screenshot/history supplied by the user showed an **HTTP 429 from Gemini embedding** with text that the current quota was exceeded and billing/quota should be checked. In an earlier observed ingestion attempt, the Cormen file reached the Gemini embedding stage and failed on the first embedding request; the prior logs showed an approximately 54.2-second request/roundtrip. The 28.5 MB Horowitz file produced zero extracted text in the prior run, consistent with the loader's scanned-PDF error. These are historical observations from before/around the provider transition, not results of the present read-only audit. No paid request was made during this audit.

This is evidence for a Gemini API project/model quota or billing limit, not a Codex/ChatGPT plan limit. Google Gemini API quotas are associated with the Google project/model and include rate/token/request limits; the precise active project, tier, model-specific quota, and whether the shown 429 was RPM, TPM, daily request quota, or billing state cannot be verified from the local repository. The key string does not reveal project quota state, and no Google console/API access was used. The screenshot's message leans toward a quota/billing condition; it is not enough to assert which limit metric is exhausted. The current code surfaces 429 details for embedding errors, but its handling does not provide a verified structured quota classification or project/model quota dashboard.

### Cost and call-count risks

- Local embeddings avoid per-chunk Gemini embedding requests and keep ingestion viable without Gemini once the FastEmbed path is successfully exercised in the running API. Cold model download/load remains a one-time latency/storage cost; persist the model volume and prewarm where appropriate.
- Retrieval still embeds every query locally or through the selected embedding provider. FastEmbed's local content-hash cache reduces repeat document embedding work; query cache behavior should also be validated under normalized equivalent queries.
- Every adequate-evidence query, summary or comparison currently uses Gemini generation. A repaired answer can call generation again. Optional LLM claim-judging can call it multiple additional times. Current metadata accounts calls but not input/output tokens, dollar usage, or provider-level daily limits.
- `rag/generation/local_state.py` defines a response cache and SQLite daily call reservation, but no call sites were found in the generator/client/pipeline. `LLM_DAILY_CALL_BUDGET=25` appears in root `.env` and Compose, but no corresponding setting/enforcement was found in `rag/config/settings.py` or `LLMClientFactory`. Treat this budget as **configured but ineffective** until connected and tested.
- Gemini SDK client setup supplies a timeout but no explicit retry policy (`rag/generation/llm_client.py:215-223`). SDK defaults may retry transient responses; actual retry count and quota behavior were not measured in this audit. Ensure quota-exhausted responses do not get repeatedly retried and are not transformed into mock success.

## Existing features and NotebookLM gaps

**Implemented or substantially represented:** accounts/auth; project/library CRUD; single/batch uploads with original-file storage; processing status/retry; PDF and common office/text parsers; page-aware section chunks; dense and lexical retrieval; paper-scope filters; multi-query research planning; summaries and cross-paper comparisons; citation source drawer with snippets/locators; answer verification metadata; knowledge-graph pages and API boundary; evaluation/test suites; Dockerized backend/PostgreSQL and persistent Chroma/model volumes.

**Incomplete or missing for a NotebookLM-like experience:** OCR for scanned PDFs; independent real-model end-to-end validation and benchmark fixtures; selective generative calls and useful local evidence fallback; enforced usage/token/cost budgets and response cache; actual semantic reranker; richer hybrid retrieval tuning and calibrated score thresholds; semantic claim-entailment verification and citation coverage evaluation; source-level page viewer/highlighting (citations are page locators/snippets, but this audit did not verify in-PDF highlight navigation); robust conflict resolution; ingestion job cancellation that interrupts work safely; durable distributed job queue for multi-worker production; and an end-to-end migration status view for previous vector collections. The knowledge graph is documented as unavailable/stubbed, so graph screens should not be interpreted as proof of a functioning backend graph service.

The main RAG test suite includes parser provenance, retrieval, generation, vectorstore, orchestrator and ingestion unit tests (for example `rag/tests/test_provenance_and_parsers.py`, `test_retrieval.py`, `test_generation.py`, `test_ingest_pipeline.py`). Those tests use fixtures and mocks in portions of the suite; their existence does not establish live Gemini quota behavior or real-document relevance.

## Prioritized findings

| Priority | Finding | Evidence / confidence |
|---|---|---|
| **P0 — ingestion blocker for scanned PDFs** | No OCR implementation was found. An image-only PDF has no searchable text and cannot be indexed by the current loader. | Verified in loader behavior (`rag/ingestion/document_loader.py:86-87`); prior Horowitz extraction result of 0 text is observed historical evidence. High confidence. |
| **P0 — previous Gemini embedding failure** | Prior Cormen ingest failed on Gemini embeddings with HTTP 429 and quota/billing text; local FastEmbed is now configured to remove this dependency, but integrated end-to-end success has not been verified. | User-provided screenshot/history; current provider config (`rag/config/settings.py:33-40`, root `.env`, Compose). High confidence for previous 429; low/unknown for present full-ingestion outcome. |
| **P1 — generation remains mandatory** | Evidence-based search is coupled to Gemini generation whenever sufficient evidence is retrieved; no generation-unavailable local evidence response is wired. | `rag/pipelines/query_pipeline.py:119-147`; Gemini factory/client. High confidence. |
| **P1 — budget/cache are not enforced** | A SQLite cache/budget module and env variable exist, but no production call path uses them and settings lacks a budget field. | `rag/generation/local_state.py`; config `rag/config/settings.py:42-50`; compose line 39. High confidence from source search. |
| **P1 — timeout may not cancel work** | The gateway wraps `asyncio.to_thread` in `wait_for`; timeout cancels the await, not the already-running Python worker thread. A user retry can overlap work after timeout if the lock is released before the worker exits. | `backend/app/integrations/rag_gateway.py:48-65`, lock path in `backend/app/integrations/rag_client.py`. High confidence; actual overlap depends on timing. |
| **P1 — correctness verifier limitations** | Lexical/numeric claim checks and valid citation tags are useful guardrails but cannot reliably establish semantic support or completeness. | `rag/research/claim_verifier.py`; `rag/pipelines/query_pipeline.py:154-170`. High confidence. |
| **P2 — retrieval ranking is basic** | Hybrid dense/FTS5 retrieval and bounded planning exist, but default reranker is pass-through and min-score defaults to zero. | `rag/retrieval/reranker.py:24-30`; `rag/config/settings.py:56-60`. High confidence. |
| **P2 — configuration/docs drift** | `rag/README.md:40-48` still documents Gemini embeddings as the setup default, while code/root config select FastEmbed. It also omits the newer cache, model version and effective generation policy. | README and current settings. High confidence. |
| **P2 — full-file test status unknown** | Local provider implementation and current working-tree changes have not been integration-tested in this audit. | No commands were run by design; tests do exist. High confidence. |

## Practical optimization opportunities

1. Keep extraction, normalization, chunking, local embedding, storage and retrieval independent of Gemini; verify that container environment selects FastEmbed and that a cold-start model download does not exceed upload request/job timeouts.
2. Move ingestion out of a long HTTP request into durable jobs. Persist a job ID, heartbeat and stage; make cancellation cooperative between parse pages, embedding batches and upserts. A timeout should not silently leave a thread working while a retry starts.
3. Add bounded page-aware OCR as an explicit opt-in capability for image-only pages, with OCR language/quality metadata and original page mapping. Do not overwrite originals or label OCR output as extracted PDF text.
4. For easy lookups, support deterministic extractive answers with quoted passages, filename/page and explicit “evidence only” labeling. Use Gemini only for synthesis/comparison/explanation or truly ambiguous questions. If Gemini is unavailable, return retrieved evidence and state that synthesis was unavailable.
5. Wire the existing budget/cache concept through the generation client. Count actual outbound calls, reserve budget atomically, include model/prompt/version/scope in cache keys, expire entries, and ensure quota exhaustion blocks retries and fallback does not claim an LLM answer.
6. Improve retrieval with query normalization, title/section and exact-term signals, calibrated dense+BM25 fusion, a measured local reranker, and per-project/document filters. Evaluate recall and citation accuracy before changing chunk sizes or model.
7. Add real fixtures/golden questions for supported document types and scanned/text PDFs. Evaluate extraction coverage, page locator accuracy, Recall@k, MRR/nDCG, answer claim support, citation precision/recall, latency, cache hit rate, embedding count and model-call/token usage.
8. Reconcile README and environment templates with the effective provider defaults, state which files Compose reads, document model cache persistence, and expose only safe provider/model/error diagnostics in health/status endpoints.

## Prioritized roadmap

### Phase 1 — Prove local ingestion and migration safety

- On a controlled environment, ingest one small text PDF and one representative large text PDF with the local model; record cold/warm time per stage, page/chunk/batch counts, cache hits and Chroma/FTS counts.
- Retrieve known questions using only the new collection and verify exact filename, PDF page and quote against source pages.
- Run `scripts/reindex_documents.py` on a small controlled corpus and inspect its selection/failure/resume semantics before using it against all stored documents. Keep the original files and old collection; verify no duplicate chunk counts across retries.
- Decide whether scanned-PDF OCR is in scope and implement it as a separate, provenance-preserving parser capability if required.

### Phase 2 — Make generation selective and budgeted

- Add deterministic extractive lookup/quotation/evidence-only response paths and explicit task selection.
- Wire a local response cache and atomic daily call budget into every outbound Gemini generation, repair and judge request. Track token usage when provider responses expose it.
- Classify invalid model/key, transient network/rate-limit, and exhausted quota separately; stop quota retries and preserve a clearly labelled evidence response.
- Test no-key, invalid-model, 429, transient error, cache-hit and budget-exhausted cases with fake SDK responses; do not call live paid APIs in regression tests.

### Phase 3 — Raise retrieval and answer quality

- Establish evaluation baselines with manually checked questions and source spans.
- Tune hybrid retrieval/score thresholds and add a local reranker only if metrics show benefit.
- Strengthen claim verification with entailment-oriented checks, conflict and “not found” handling, source-level citation coverage, numeric consistency, and user-visible explanation when evidence is weak.
- Add document/page navigation or quoted-span highlighting if required by the intended research workflow.

### Phase 4 — Production reliability and NotebookLM workflow

- Use durable background jobs with heartbeat, cancellation, idempotency keys and safe retry/recovery.
- Add OCR and additional file formats only with measurable parser coverage and page/slide/sheet locators.
- Complete graph service wiring only if graph capabilities are required; show unavailable state honestly until then.
- Validate auth/ownership isolation for every retrieval and citation endpoint, and benchmark multi-user latency and storage growth.

## Validation checklist for implementation phase

- [ ] Start API with no Gemini key; upload, parse, locally embed, index and query supported text documents successfully.
- [ ] Test cold and warm FastEmbed startup and ensure persistent model/cache volumes work in Docker.
- [ ] For representative PDFs, compare page count and extracted text coverage to source; confirm original page numbers and exact filenames in citations.
- [ ] Verify scanned PDF yields a precise OCR-required result unless OCR has been explicitly enabled; test OCR page provenance and confidence if enabled.
- [ ] Check selected collection identity includes provider, model/version and dimension; reject vector dimension mismatch; preserve old collection; resume reindex without duplicate counts.
- [ ] Inject failure after an embedding batch and after an index batch; assert partial chunks are cleaned or safely reconciled and file status becomes terminal/retryable.
- [ ] Cause a timeout and retry while the worker is still active; confirm jobs do not overlap and cancellation/recovery is deterministic.
- [ ] Confirm progress is persisted across reloads, based on actual page/chunk/batch counts where possible, and eventually terminal for success, parser failure, quota failure and worker death.
- [ ] Exercise deterministic extraction, local evidence-only fallback, Gemini synthesis, repair and optional verifier paths; ensure no mock response can appear in normal operation.
- [ ] Simulate 429 exhausted quota, transient rate limit, network error, missing key and invalid model; verify no inappropriate retries or provider switching.
- [ ] Verify cache key scope/version, cache invalidation, atomic call budget, token/call metrics and budget exhaustion for every outbound LLM path.
- [ ] Evaluate Recall@k/MRR/nDCG, claim support, citation precision/recall, conflict detection and unsupported-answer abstention on a gold set.
- [ ] Test access isolation across users/projects, duplicate upload/retry, deletes, and original-file preservation.
- [ ] Run backend/RAG/frontend tests, lint, typecheck and production builds after implementation; capture exact commands/results. None were run for this read-only audit.

## Audit limitations and source references

- No live project quota, billing tier, API key project, Google AI Studio state, container runtime configuration, current DB/index contents, or network health was accessible without external account/service calls. No such calls were made.
- The user-supplied earlier PDF timings and errors are reported as historical observations, not fresh measurements. The source PDF files and current Chroma contents were not inspected during this audit.
- Model model-ID validity and active Google rate limits should be checked against the official Gemini model and rate-limit documentation at implementation time: [Gemini models](https://ai.google.dev/gemini-api/docs/models), [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Gemini API errors](https://ai.google.dev/gemini-api/docs/api-errors). The repository alone cannot prove that a configured model is enabled for a particular project.
- Paths and line numbers in this report refer to the audited working tree; this workspace was already modified before the audit started.

## Phase 1 implementation addendum — 2026-10-26

The read-only findings above describe the pre-Phase-1 state. A later isolated Phase 1 validation confirmed and addressed additional local-ingestion blockers: FastEmbed's tokenizer truncates at 512 tokens while the existing chunk limit is word-based; `parallel=1` selects a multiprocessing worker pool that fails in Windows stdin/API-worker contexts; and chunk IDs scoped only to `paper_id` allow different files in the same project to overwrite one another. The current implementation splits over-limit chunks using an untruncated copy of the configured tokenizer before embedding, preserves page mapping, runs local inference in-process, and includes document identity in stable chunk IDs. It also versions the collection namespace to isolate the new ID scheme. Same-batch repeated text is deduplicated before inference. These changes passed local tests and temporary-store end-to-end checks; see `PHASE1_VALIDATION.md` for measured results and migration limitations.

The reindex utility finding is also historical: `scripts/reindex_documents.py` now defaults to dry-run, requires an explicit document ID or `--all` scope, requires `--apply` for mutation, and only resumes processing rows after a stale-heartbeat check when `--resume-stale` is supplied. This report's earlier statement about missing dry-run/scope/resume safety remains accurate for the audited source state on which the audit was originally written.

## Phase 2 implementation addendum — 2026-10-26

The generation path now bypasses model generation for an adequate direct lookup and returns an exact retrieved passage with the mapped filename and page citation. Insufficient evidence remains explicit and includes a source excerpt when one is available. Synthesis-required requests use the configured provider and are labeled separately from evidence-only responses; provider, credential, budget, quota, model, and transient failures return labeled evidence instead of a mock answer. The API persists answer mode and generation reason for saved messages, and the chat UI displays that mode.

The existing SQLite response cache is connected to verified generated answers. Cache keys include a versioned generation policy, selected model/provider, normalized question, user and selected-paper scope, conversation context, and identity hashes/locators for the retrieved passages. Cache hits return no outbound-call count or current-call token usage. Successful responses are cached only when citation identities are valid and claim checks have no unresolved unsupported/invalid/contradicted items; responses requiring repair are not cached. The cache remains stored alongside the configured embedding cache.

Every real generation, repair, judge, and stream call passes through the atomic SQLite daily budget. The reset is midnight UTC. The Google Gen AI SDK is configured for one attempt per application call to prevent its default retries from multiplying unaccounted requests; failures distinguish exhausted quota, transient rate limiting, credentials/access, invalid models, and transient provider failures. SDK-reported token counts are retained as measured usage where exposed; no token or cost estimate is substituted when the SDK does not report usage. See `PHASE2_VALIDATION.md` for exact changed files, test results, and remaining live-provider/Chroma limitations.

## Phase 2.5 quality audit addendum - 2026-10-26

An isolated, versioned synthetic evaluation now exercises the actual FastEmbed (`BAAI/bge-small-en-v1.5`, 384d), `ResearchRetriever`, Chroma/FTS5 repository, and `QueryPipeline`; it does not use real documents or a live generation API. The eight-case fixture achieved Recall@5 1.00, MRR 0.7778, cited-passage precision/recall 1.00, exact page-locator accuracy 1.00, and correct abstention/scope exclusion on 2/2 expected-abstention cases. These are small synthetic-set measurements, not a claim about real research-paper quality. See `PHASE2_5_QUALITY_REPORT.md` for definitions and limits.

The evaluation exposed two direct-answer issues: a broad lexical coverage score could label a question adequate while its key term was missing, and evidence-only output quoted only the first retrieved chunk. Direct factual routing now requires no missing query terms; evidence/fallback output selects a compact lexical set of relevant retrieved passages and preserves multiple excerpts needed for a multi-fact answer or conflicting papers. This remains a conservative lexical heuristic, not semantic entailment. The current sufficiency conflict detector only checks a fixed list of named metrics, so disagreements about unrecognized attributes, dates, or identifiers can remain undetected.

SQLite response and embedding cache connection helpers now commit/rollback and close each connection explicitly. The response cache prunes oldest entries above 10,000 rows; the usage-budget ledger remains outside pruning and its `BEGIN IMMEDIATE` reservation behavior is unchanged. Isolated tests validated cache eviction, file-handle closure, multi-instance concurrent budget limits, repeat indexing, and concurrent Chroma query/upsert/delete/retry with two clients. The historical Chroma `Error finding id` did not reproduce; no Chroma defect is claimed fixed. Backend ownership validation restricts chat scopes to user-owned papers, while the RAG index itself is globally addressed by paper ID and relies on that authenticated boundary.

## Phase 3 evidence-quality addendum — 2026-10-26

The synthetic Phase 3 validation confirmed and corrected a false conflict classification: different values from different systems/evaluation conditions were treated as a conflict based on metric name alone. Conflict detection now requires explicit matching subject, metric, unit, and conditions, and also checks contradictory repetitions within one document. The claim verifier now distinguishes exact numeric atoms/technical identifiers and only labels a numeric value contradicted when the same named metric has an explicitly different value; unrelated dates/counts no longer establish contradiction. These are conservative string-pattern checks, not general semantic entailment. The earlier Phase 2.5 fixture's Atlas/Boreal conflict label was corrected; its historical reported metrics remain as recorded in the Phase 2.5 report.

An isolated FastEmbed/Chroma/FTS5 synthetic test achieved Recall@5 1.00 and MRR 1.00 on three answerable paraphrase/fact queries, selected-evidence citation precision/recall 1.00, page accuracy 2/2, correct abstention 2/2, and correct handling of all four comparable/different-condition conflict cases. On the same four conflict cases, the old metric-only rule scored 2/4. The sample is deliberately small and does not validate live generation or real-paper semantic quality. No reranker, threshold, or rank-order change was made; the pass-through reranker was already perfect on this small answerable subset. See `PHASE3_QUALITY_VALIDATION.md` for exact methodology, test results, limitations, and go/no-go recommendation.

## Phase 4A ingestion reliability addendum — 2026-10-26

The Phase 4A reliability pass verified that the upload service now checks non-empty Chroma and SQLite FTS5 chunk counts and exact unique-ID parity before marking a document indexed. Ingestion cancellation is requested cooperatively at safe pipeline boundaries after gateway timeout/caller cancellation, with the in-process same-document lock retained through worker cleanup. FTS write/cleanup errors are surfaced, retries claim failed rows atomically, failure/stale states reset progress and chunk counts, and paper deletion performs index cleanup before deleting its relational record or original files. Focused regression coverage exercises cancellation, duplicate/retry races, partial index cleanup, Chroma/FTS mismatch, active deletion, and idempotent reconciliation. Validation passed: 71 targeted tests, 201 full RAG/backend tests, 18 frontend tests, frontend lint/typecheck/production build, and `git diff --check`; see `PHASE4A_INGESTION_RELIABILITY.md`.

This implementation still has a process-local lock, no durable queue or cross-process lease, and stale-processing recovery occurs on later status/list reads rather than through a scheduled sweeper. A running synchronous operation may only observe cancellation after its current parser/model/database call returns. Therefore the tests support isolated single-process reliability, not multi-worker or crash-recovery guarantees. No real document corpus or external API was used.

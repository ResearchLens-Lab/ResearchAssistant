# ResearchAssistant Phase 2.5 - RAG Quality, Reliability, and Release Readiness

**Date:** 2026-10-26  
**Decision:** **GO for isolated real-document validation; NO-GO for full-corpus migration or a claim of real-document answer quality.** The local retrieval/citation path passed a compact synthetic evaluation. The real PDF corpus was not accessed, and live generation quality was not measured.

## Scope and isolation

Read `PROJECT_AUDIT.md`, `PHASE1_VALIDATION.md`, `PHASE1_9_SHOWCASE_VALIDATION.md`, and `PHASE2_VALIDATION.md` before auditing. The working tree already contained extensive unrelated edits and untracked files. Those were preserved. No real uploaded files, configured PostgreSQL database, existing Chroma directory, Gemini endpoint, or paid API was accessed.

The evaluation used the already available local FastEmbed model cache (`BAAI/bge-small-en-v1.5`, FastEmbed 0.9.0, 384 dimensions) read-only. Each run used pytest temporary directories for Chroma, the SQLite lexical index, and the embedding/response-cache state. A fresh namespaced Chroma collection was created under each temporary directory. The versioned fixture consists of two synthetic two-page documents and four manually specified passages; page numbers and filenames in the fixture are the known provenance oracle. Synthetic chunks were embedded locally and indexed directly into the isolated vector repository so this audit measures retrieval and query behavior, not PDF extraction or upload/ingestion.

No real generation call occurred. The local provider produced evidence fallback excerpts for synthesis/conflict cases. One separate query-policy test used a deterministic fake client to verify that the comparison route invokes the configured generation adapter, preserves its citations, and labels the result according to the configured provider. That adapter test is not a Gemini quality measurement.

## Current path traced

1. `QueryPipeline.answer_question` applies explicit paper scope, creates a deterministic `ResearchPlan`, runs bounded retrieval queries, deduplicates chunks by stable chunk ID, assesses evidence, and retries once for missing terms when configured (`rag/pipelines/query_pipeline.py:60-145`).
2. `ResearchRetriever.retrieve` embeds the query, applies paper/metadata filters, queries Chroma and SQLite FTS5, fuses ranked lists with reciprocal-rank fusion, then applies the configured reranker (`rag/retrieval/retriever.py:36-98`). The default reranker is `IdentityReranker`, so no semantic reranking is active (`rag/retrieval/reranker.py:24-30`).
3. `VectorRepository` upserts stable chunk IDs to Chroma and FTS5, maps vector metadata to returned records, and deletes by paper/document (`rag/vectorstore/vector_repository.py:46-119,132-178,255-284`). The collection name includes the embedding provider, model/version, dimension, and chunk-ID schema (`rag/vectorstore/collection_manager.py:19-44`).
4. The query pipeline builds bounded context, routes adequate direct queries to verbatim evidence output, routes synthesis-required requests to the configured generator, and validates citation identity/scope and claims (`rag/pipelines/query_pipeline.py:147-425`; `rag/research/orchestrator.py:112-195`; `rag/research/claim_verifier.py:96-173`). Citation identity verification is deterministic but explicitly does not establish entailment.
5. At the authenticated backend boundary, chat requests must contain paper IDs and `ChatService` validates that each requested paper belongs to the user before passing paper IDs and user ID to the RAG gateway (`backend/app/schemas/chat.py:10-13`; `backend/app/services/chat_service.py:39-78`; `backend/app/services/paper_service.py:48-57,88-93`). The RAG index itself is globally addressed by paper/document metadata rather than user ID; the user isolation boundary is backend ownership validation.

## Verified findings and changes

| Severity | Finding | Evidence and action |
|---|---|---|
| **P1, fixed** | Direct factual lookup could be treated as adequate by the overall term-coverage ratio even when an answer-critical term was missing. The absent-recall fixture retrieved Atlas passages, whose overlap with `Atlas` and `benchmark` cleared the existing threshold although `recall` and `Zeta-404` were absent. | Direct routing now marks adequate/partial evidence insufficient when required query terms remain missing, without changing the configured coverage thresholds (`rag/pipelines/query_pipeline.py:115-139`). The fixture asserts an explicit insufficient-evidence response and no out-of-scope leakage. This remains lexical matching, not entailment. |
| **P1, fixed** | Evidence-only responses quoted only the first retrieved passage, omitting the second passage needed by a multi-fact question. Fallback responses could quote top-ranked passages that did not contain the metric being described. | Evidence and fallback output now greedily selects a compact set of retrieved passages covering query terms; conflict fallback retains evidence from distinct papers (`rag/pipelines/query_pipeline.py:151-228`). Regression cases verify both Atlas passages for the multi-passage question and both accuracy passages for a conflict. |
| **P2, fixed** | `with sqlite3_connection` commits/rolls back but does not close the connection. Both SQLite cache helpers returned connections to that construct without explicitly closing them. A local FastEmbed smoke run produced a Windows `PermissionError` when its temporary cache directory was cleaned up while the connection remained open. | Response-cache and embedding-cache connection context managers now close in `finally` while preserving the connection context's commit/rollback behavior (`rag/generation/local_state.py:39-49`; `rag/embeddings/cache.py:23-33`). Regression tests verify cache persistence and that the SQLite files can be renamed after use. |
| **P2, addressed** | Response-cache rows had no expiration or eviction, so successful generated responses could accumulate without a bound. | `SQLiteLLMState` now retains at most 10,000 response rows, evicting oldest rows on insertion. The budget table is not pruned (`rag/generation/local_state.py:20-28,68-79`). A reduced test cap verifies eviction and confirms the call ledger remains available. The cap bounds row count, not the maximum byte size of one response. |
| **P2, open** | Evidence sufficiency detects conflicts only for `accuracy`, `precision`, `recall`, `bleu`, `f1`, and `error rate`, and only when differing values occur across papers. | Verified in `rag/research/orchestrator.py:121-132`. Disagreements about arbitrary numeric fields, dates, identifiers, or multiple values within one paper may not be flagged. No thresholds or conflict rules were broadened in this phase. |
| **P2, open** | Claim support uses deterministic lexical/numeric overlap unless the optional LLM judge is enabled. Citation identity checks prove that an ID maps to an in-scope passage, not that the passage semantically entails the claim. | Verified in `rag/research/claim_verifier.py:1-4,96-173` and `rag/research/orchestrator.py:181-195`. This limitation is retained and is not represented as semantic verification. |
| **P3, not reproduced** | Historical Chroma `Error finding id` remains an intermittent, unconfirmed observation from Phase 1.9. | The isolated stress case ran concurrent retrieval from two clients while other workers repeated upserts and document delete/retry. No exception occurred; the expected final Chroma and FTS counts matched. This is evidence of non-reproduction only, not a fix. |

### Cache, budget, and collection lifecycle

- Cache keys in the generation path contain provider/model, prompt version, normalized question, user ID, selected paper IDs, retrieved document/source identities (including text hash, page, filename, and locator), and conversation context (`rag/pipelines/query_pipeline.py:263-277`). Existing regression coverage verifies repeat hits, different-user misses, and changed-source misses (`rag/tests/test_generation_policy.py:65-84`).
- The SQLite budget reservation uses `BEGIN IMMEDIATE`, increments only while below the daily limit, and commits the reservation atomically (`rag/generation/local_state.py:81-104`). Existing tests cover parallel worker reservations; the new Phase 2.5 test additionally uses six independent state instances against one isolated SQLite file and enforces a limit of five.
- The response cache and budget share a configurable SQLite path with other local state in normal configuration. Cache pruning is table-scoped and does not touch `llm_usage_budget`. The state is local to a host; a multi-host deployment still needs shared transactional state for a globally enforced budget.
- The Chroma factory caches one normal client but supports explicit independent clients with `force_new=True` (`rag/vectorstore/chroma_client.py:25-63`). The isolated run successfully queried through two persistent clients concurrently. All test Chroma data lived under pytest temporary directories.

## Evaluation fixture and method

The versioned gold set is `rag/tests/fixtures/phase2_5_quality_v1.json`. It contains Atlas and Boreal synthetic papers with exact passages, stable IDs, filenames, and original page numbers, and eight cases covering:

- One-passage identifier and numeric/date facts.
- A two-passage fact requiring passages from pages 1 and 2.
- Cross-document comparison and conflicting accuracy values.
- A missing recall value and absent benchmark.
- Similar identifiers (`AX-17A` versus `AX-17B`).
- An explicit Atlas-only scope where the requested Boreal answer exists only outside that scope.

The harness uses actual local FastEmbed embeddings and the actual `ResearchRetriever` and `QueryPipeline`. Answerable expected passage IDs are judged against the fixture; retrieval and citations are checked by immutable chunk IDs, and page accuracy is checked against the fixture's original page values. The synthetic corpus has four chunks, so these results are diagnostic and not statistically representative.

## Results

Final measured run: `python -m pytest rag/tests/test_phase2_5_quality.py -q -s`.

| Measure | Result | Sample / interpretation |
|---|---:|---|
| Recall@5 | **1.0000** | All 9 relevant passage instances retrieved across 6 answerable cases. |
| MRR | **0.7778** | Mean reciprocal rank across those 6 cases; first relevant rank was 1, 1, 1, 3, 3, and 1. |
| Citation precision | **1.0000** | 9 expected relevant citation instances; no extra cited chunks in the answerable cases. |
| Citation recall | **1.0000** | All 9 expected relevant citation instances were cited. |
| Exact page locator accuracy | **1.0000** | 9/9 cited expected passages retained the known original page number. |
| Expected abstention and scope exclusion | **2/2** | Absent recall and Atlas-only/Boreal-answer cases explicitly abstained; no Boreal passage leaked into the selected Atlas scope. |
| Conflicting evidence | **2/2 cases flagged** | Both conflicting accuracy and comparison cases were marked `conflicting`; evidence fallback cited Atlas p.2 and Boreal p.2. |
| Index consistency | **4 Chroma / 4 FTS5; IDs match** | Repeat upsert kept four chunks; FTS row count equaled unique chunk IDs. |
| Embeddings | **4 x 384 dimensions** | One document embedding batch for the four passages; cache warm vectors equaled cold vectors. |
| Local embedding timing | **Cold 0.5979 s; warm 0.0046 s** | Cold call includes model initialization in this test process; warm call reused cached content vectors. Environment-specific, not an ingestion SLA. |

Metrics were computed by `rag/tests/test_phase2_5_quality.py`, not estimated. The passage “citation” measure is identity-level agreement with manually labeled relevant chunks; it does not measure whether generated prose is semantically entailed. No real-generation answer-quality or provider cost claim is made.

## Routing and generation adapter checks

- A direct two-passage query retained the identifier and result excerpts with pages 1 and 2. A partial direct query returned an explicit insufficient-evidence response without needing a provider call.
- The absent-recall case verified why a single global coverage ratio is not enough for direct lookup: the old `adequate` score was caused by topical overlap. Direct routing now treats missing key terms as insufficient and gives the same status in result metadata.
- The cross-paper comparison and conflict cases ran with `LLM_PROVIDER=local`; output is labeled evidence fallback, quotes only the relevant result passages, and explains that synthesis is unavailable or the evidence conflicts. This validates fallback behavior, not a generated comparison.
- A deterministic adapter test verified that an actual comparison intent calls the injected configured generation client once and maps its output citations to `Atlas-Protocol.pdf` p.2 and `Boreal-Protocol.pdf` p.2. This is test-adapter routing only, not Gemini generation.
- Existing Phase 2 tests continue to cover cache hits/misses by user/source, zero-budget and missing-credential fallback, provider quota/rate-limit errors, and generation/stream/repair/judge budget enforcement.

## Chroma concurrency/recovery experiment

In a fresh temporary persistence directory, four stable chunks were repeatedly upserted while workers queried from two `PersistentClient` objects and repeatedly deleted/retried indexing the same document. The run had **zero captured operation errors**, did **not** reproduce `Error finding id`, and supported concurrent queries from the second client. After a final delete/reinsert recovery pass, Chroma contained 4 records and FTS5 contained 4 rows with 4 distinct IDs. This finite local stress run cannot rule out a lower-frequency or platform-specific Chroma defect.

## Exact files changed in Phase 2.5

- `rag/pipelines/query_pipeline.py` - require complete lexical key-term coverage before direct factual mode; select relevant, compact quoted evidence so multi-passage facts and conflicts retain supporting citations.
- `rag/generation/local_state.py` - close SQLite state connections, cap response-cache rows at 10,000, and leave budget rows untouched.
- `rag/embeddings/cache.py` - close SQLite embedding-cache connections while preserving transaction semantics.
- `rag/tests/fixtures/phase2_5_quality_v1.json` - versioned synthetic gold corpus and eight query cases.
- `rag/tests/test_phase2_5_quality.py` - local FastEmbed metrics, query-route/generation adapter, cache/connection lifecycle, independent budget concurrency, and two-client Chroma contention/retry coverage.
- `PHASE2_5_QUALITY_REPORT.md` - this report.
- `PROJECT_AUDIT.md` - dated addendum; earlier audit conclusions remain intact as historical context.

No existing database, project Chroma storage, uploads, `.env` file, or model-cache content was modified. Test-created Chroma, SQLite, and cache paths were pytest temporary paths; clients were closed in the test harness. One initial standalone FastEmbed smoke command left its own temporary SQLite file at `C:\Users\gorav\AppData\Local\Temp\p25_model_o1m6om8x\embed.sqlite` after its cleanup failed while the connection was open. I verified that directory contains only that 12 KB file. The environment rejected both cleanup attempts under its automatic execution policy, so this task-created disposable cache file remains outside the repository; no unrelated path was targeted.

## Commands and results

| Command | Result |
|---|---|
| `python -m pytest rag/tests/test_phase2_5_quality.py -q -s` | **5 passed**. Includes actual local-model evaluation and isolated cache/concurrency checks. The output recorded above was the final metric run. |
| `python -m pytest rag/tests -q` | **92 passed** after adding the independent-budget-concurrency test. |
| `python -m pytest backend/tests -q` | **96 passed**. |
| `npm.cmd test -- --run` from `frontend/` | **18 passed**. |
| `npm.cmd run lint` from `frontend/` | **Passed**. |
| `npm.cmd run typecheck` from `frontend/` | **Passed**. |
| `npm.cmd run build` from `frontend/` | **Passed**; Next.js reported that the Next.js ESLint plugin was not detected in the existing configuration. |
| `git diff --check` | **Passed**; Git emitted line-ending normalization warnings for pre-existing LF files. |
| Python linter/type-check discovery | No `pyproject.toml`, `ruff.toml`, `setup.cfg`, `tox.ini`, `.flake8`, or `mypy.ini` was found. The prior Phase 2 environment also recorded `ruff` unavailable. |

The full RAG suite result above predates the last added budget-across-independent-instances test (that test is included in the final five-test quality file run). No dependency was installed. No full browser walkthrough was performed.

## Remaining issues and release decision

1. **Proceed to isolated real-document validation only.** Use a representative text-based research PDF in a fresh temporary store, then compare extracted source passages and physical PDF pages against the original. This audit did not access or validate the Cormen/Horowitz files or any real research corpus.
2. Direct evidence sufficiency and excerpt selection are exact-token heuristics. Synonyms, morphology, OCR noise, and questions whose wording differs from the source may conservatively abstain or select incomplete support. The evaluation’s perfect scores are on deliberately controlled synthetic text.
3. Conflict detection is restricted to a few metric names. Broader conflicting findings and within-document disagreements remain open.
4. The claim verifier is a lexical/numeric heuristic, not semantic entailment. Citation IDs and page mappings are accurate in the test, but semantic answer grounding from a real Gemini model remains unverified.
5. Chroma's historic error was not reproduced under a small two-client contention run. Keep monitoring production logs; no fix is claimed.
6. Cache entries are count-bounded but have no TTL or byte-size limit. SQLite usage budgets remain per local database/host.
7. No Gemini call was made. Model availability, live provider answer quality, costs, rate limits, and token usage remain unmeasured.

**Release gate:** synthetic local retrieval passes; real-document validation may proceed in an isolated environment. Do not use this report as authorization or evidence for full-corpus reindexing.

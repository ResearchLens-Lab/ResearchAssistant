# Phase 2 Validation — Selective Generation, Cache, and Call Budget

**Date:** 2026-10-26

**Scope:** Phase 2 only. No document corpus, user database, Chroma collection, Gemini API, or paid API was used.

## Implementation

- Adequate `direct` factual lookups now return the exact first retrieved passage, with its filename, original page locator, and validated source ID. They skip generation and report `answer_mode=evidence_only`, `generation_reason=direct_factual_lookup`, and zero outbound calls.
- Insufficient-evidence results say that the passages do not support an answer. When a passage exists, it is included verbatim with its citation. Local-only mode and unavailable generation return a labeled evidence fallback and a user-readable reason.
- Synthesis-required requests use the configured model. Saved and streamed responses distinguish `generated`, `evidence_only`, `evidence_fallback`, and test-only `mock` modes. Mock mode is now restricted by the factory to `APP_ENV=testing`; it is never marked as a genuine generated answer.
- The existing SQLite response cache now stores only verified successful generated results with adequate evidence coverage, valid citations, and no claim whose verifier status is partial, unsupported, invalid, or contradicted. Its key uses the generation prompt version, model/provider, normalized question, user ID, selected paper/document scope, conversation context, and retrieved chunk/page/filename/locator/text identity. A hit returns `cache_hit=true`, zero current-call count, and no current-call token usage. A changed source, user, or selected scope misses the cache.
- The daily budget setting is parsed by `RAGSettings` as `LLM_DAILY_CALL_BUDGET` (default 25, minimum 0). The existing Docker Compose API service already forwards this variable. SQLite `BEGIN IMMEDIATE` reservations apply to provider generation, streaming, repair, and optional claim judging. Reservations are per provider and reset at 00:00 UTC. Missing credentials and local/mock evidence paths make no reservation.
- Gemini SDK retries are set to one total attempt so a single budget reservation cannot cause the SDK to retry 429/5xx responses invisibly. Failures are classified as missing credentials/access, exhausted quota, transient rate limit, invalid model, transient service/network failure, or other provider error. The configured provider is not changed on failure.
- Gemini response usage metadata is recorded as measured prompt/candidate/total tokens when returned by the SDK. Streaming records usage only if the SDK exposes it. No token/cost estimate is reported when measured usage is absent. A test-only fake SDK usage fixture verifies that the metadata is carried through; no live account usage was measured.
- The backend passes authenticated user identity into RAG cache scope and persists answer mode/reason, call count, cache status, and SDK-measured usage with the assistant message. Stream completion passes the answer fields to the client, where the assistant badge distinguishes direct evidence, generated synthesis, unavailable synthesis, and test responses.

The Google Gen AI Python SDK source documents its retry configuration and default retryable statuses; the implementation explicitly sets `HttpRetryOptions(attempts=1)`: [official SDK retry configuration](https://github.com/googleapis/python-genai/blob/main/google/genai/_api_client.py), [official SDK HTTP options](https://googleapis.github.io/python-genai/modules.html).

## Files changed for this phase

- Configuration and RAG: `rag/config/settings.py`, `rag/generation/local_state.py`, `rag/generation/llm_client.py`, `rag/generation/generator.py`, `rag/generation/budgeted_client.py` (new), `rag/generation/provider_errors.py` (new), `rag/pipelines/query_pipeline.py`.
- Tests: `rag/tests/conftest.py`, `rag/tests/test_generation_policy.py` (new), `rag/tests/test_generation.py`, `rag/tests/test_end_to_end_rag.py`.
- Backend/API: `backend/app/integrations/rag_client.py`, `backend/app/integrations/rag_gateway.py`, `backend/app/schemas/chat.py`, `backend/app/services/chat_service.py`.
- UI: `frontend/src/components/chat/MessageItem.jsx`, `frontend/src/hooks/useChat.js`, `frontend/src/lib/researchWorkspace.mjs`, `frontend/src/lib/researchWorkspace.test.mjs`.
- Configuration examples/docs: `.env.example`, `backend/.env.example`, `PROJECT_AUDIT.md`, and this report.

The worktree contained extensive unrelated changes before this phase. The following Phase 2 files were already dirty/untracked at the start and were preserved while extending them: `.env.example`, `backend/.env.example`, `PROJECT_AUDIT.md`, the two RAG integration adapters, `rag/config/settings.py`, `rag/generation/llm_client.py`, `rag/generation/local_state.py`, `rag/pipelines/query_pipeline.py`, `rag/tests/conftest.py`, `rag/tests/test_generation.py`, and the two frontend workspace helpers. Other listed files were first modified for Phase 2. `rag/generation/budgeted_client.py`, `rag/generation/provider_errors.py`, `rag/tests/test_generation_policy.py`, and this report are new. `infrastructure/docker-compose.backend.yml` already forwarded the budget variable, so no compose edit was needed.

## Validation results

All test storage used pytest temporary directories. The RAG autouse fixture directs response-cache/budget state to each test's temporary directory. Tests use fake local clients and fake SDK responses; no provider credentials or network calls are used.

| Command | Result |
| --- | --- |
| `& .\.venv\Scripts\python.exe -m pytest rag/tests -q` | **86 passed** |
| `& .\.venv\Scripts\python.exe -m pytest backend/tests -q` | **96 passed** |
| `npm.cmd --prefix frontend test` | **18 passed** |
| `npm.cmd --prefix frontend run lint` | **Passed** |
| `npm.cmd --prefix frontend run typecheck` | **Passed** |
| `npm.cmd --prefix frontend run build` | **Passed**; Next.js emitted the existing notice that the Next.js ESLint plugin is not detected. |
| `git diff --check` | **Passed**; Git printed line-ending normalization warnings for pre-existing LF files. |

Focused regression coverage verifies a direct fact does not invoke generation and preserves filename/page citations; generation uses a fake configured client; equivalent requests hit cache; user scope and source changes miss; budget reservations remain within the limit under concurrent workers; generation/stream/repair/judge all use the budget wrapper; missing credentials and zero budget return labeled evidence; a quota error counts its one outbound attempt; 429 quota and transient rate limiting classify separately; and fake Gemini SDK token counts remain labeled measured. The frontend stream test verifies final answer mode and fallback reason survive completion. Final focused RAG set: **22 passed**.

The first attempted frontend commands used `npm` and were rejected by the PowerShell script execution policy. The same checks were then run successfully using `npm.cmd`. `ruff` is not installed in the project environment (`No module named ruff`); no Python linter or type-check script is configured. No dependency was installed.

## Chroma observation

The Phase 1.9 report recorded one immediate `Error finding id` after a retry while the API and a direct Chroma probe shared the embedded client. It was not reproducible then. The isolated RAG/Chroma tests passed again in this phase, and no matching error was observed. This does not establish a concurrency fix; keep the historical intermittent observation open for a focused multi-client/concurrent-access reproduction if it recurs.

## Limits and remaining verification

- No live Gemini request was sent. Current account model access, key validity, actual quota state, latency, and real provider token telemetry remain unverified. Failure classification is covered by fake errors only.
- The configured SQLite cache and call budget are local persistent state, not shared across separate hosts. Deployments with multiple API hosts need a shared transactional store before expecting a single global budget.
- SQLite cache entries have no expiry/eviction policy; key changes prevent stale answers from being reused, but old rows may accumulate.
- The generation prompt version must be bumped whenever a meaningful generation/verification policy change should invalidate prior entries.
- No real PDFs or existing corpus were read, indexed, reindexed, or altered in this phase. The prior synthetic Phase 1.9 upload validation remains the only API-ingestion proof.
- A production configuration using `LLM_PROVIDER=gemini` still requires a valid `GEMINI_API_KEY` and enabled model. Without them, the application returns cited evidence and reports why synthesis did not run.

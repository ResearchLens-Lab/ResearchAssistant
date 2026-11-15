# ResearchLens local AI architecture

**Status:** Phase 1 improved; desktop model management and broad evaluation remain planned. This report describes the existing implementation, not the complete product vision.

## Current runtime

- The application uses Ollama at `127.0.0.1:11434` and the configured model `qwen3.5:0.8b` (from local environment settings). It does not switch to `qwen2.5:1.5b`.
- The app sends local chat requests with `think: false`, reads only `message.content`, reuses one pooled HTTP client, and serializes inference through one request slot. The context is capped at 4096 tokens and output at the configured `LLM_MAX_TOKENS` (currently 512 in the checked example configuration).
- At the latest local read-only check (2026-11-08), Ollama 0.40.15 responded, `qwen3.5:0.8b` was installed, and no model was loaded. This is an observed point-in-time state; Ollama loads the model on demand.
- The existing RAG path remains hybrid retrieval over local embeddings and keyword search, followed by evidence sufficiency checks, grounded generation, citation verification and claim checks. PostgreSQL, ChromaDB and SQLite indexes were not reset or migrated.

## Phase 1 changes in this implementation

- `OllamaLLMClient` now advertises its existing NDJSON content stream as streaming-capable. The Qwen branch forwards provisional content for answers, summaries and comparisons through the existing chat stream. The model's `thinking` property is never forwarded; the final persisted answer still passes the existing citation and claim verification path.
- `GET /api/v1/system/model` reports runtime availability, exact configured model installation/loading state, whether inference is active, generation limits, and the `manual_only` download policy. It does not run a prompt, load a model, or pull weights.
- Settings now polls that endpoint and displays local model state. Missing Ollama and missing model states include a clear next step.
- Qwen requests still use the same configured model and do not trigger automatic downloads. Cancellation is cooperative: the stream stops forwarding and closes its response when the consumer cancels; a provider operation already executing cannot be force-killed reliably.

## Provider and privacy boundaries

`BaseLLMClient` and `LLMClientFactory` already provide a provider interface, but parts of `QueryPipeline` still branch directly for Ollama, so this is only a partial provider abstraction. The default/local path is Ollama. Other cloud providers exist in the codebase; they are not required for the default path and must not be enabled for desktop use without an explicit user choice.

Uploaded documents remain in the existing local ingestion and retrieval stack. Model inference is sent to the configured Ollama URL. This configuration can be changed by the operator; deployments should keep it loopback-only unless the user deliberately selects a trusted local-network runtime.

## Model fit and limits

The 0.8B model is a low-resource profile, not an assurance of strong academic reasoning. It may omit qualifications, confuse related concepts, produce shallow follow-ups, or fail to follow long structured instructions. ResearchLens must treat retrieval and verifiable passages as the source of truth, show abstentions, and preserve citation/claim verification. No accuracy or calibrated confidence percentage is claimed here.

An initial local smoke evaluation was run against one passage-supported definition and one deliberately unsupported question; see `FINAL_IMPLEMENTATION_REPORT.md` for timings and observed responses. This is a smoke check, not a representative benchmark. The full manually adjudicated evaluation set and recall/citation metrics remain planned.

## Model registry and future work

The settings layer already distinguishes provider/model values, but there is no user-facing registry for profiles, model compatibility, RAM/VRAM estimates, import, download progress, checksum verification or cancellation. Add that as an explicit model-management service with provider adapters and a persisted, user-confirmed profile; do not make downloads part of startup or chat. Keep retrieval independent of the chosen generator.

The official Qwen3.5-0.8B Hugging Face card identifies Apache-2.0 licensing. Ollama's official source repository is MIT licensed. Before bundling anything, verify the exact Ollama model artifact's license/notice and all dependency licenses, and ship required notices. Current installations reuse the user's existing Ollama and model; this project does not redistribute either. [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-0.8B), [Ollama source](https://github.com/ollama/ollama), [Ollama model listing](https://ollama.com/library/qwen3.5).

## Regression evidence

- Focused backend/RAG generation and model-status suite: **22 passed** after these changes.
- Frontend regression suite: **25 passed**.
- Next.js production build: **passed**. Existing workspace lockfile-root and ESLint Next plugin warnings remain.
- Full backend/RAG regression suite: **236 passed**.

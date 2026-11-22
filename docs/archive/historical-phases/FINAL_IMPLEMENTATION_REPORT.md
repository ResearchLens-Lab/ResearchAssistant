# ResearchLens transformation — implementation report

**Report date:** 2026-11-08  
**Scope:** Phase 1 improvements, first DOI verification slice, desktop architecture evaluation, and regression checks. This work is incremental; it does not claim the complete desktop research platform is finished.

## Implemented in this pass

### Local AI integration

- Preserved the configured Ollama model `qwen3.5:0.8b`; no model pulls, provider switches, or database/index resets were performed.
- Enabled the existing Ollama NDJSON text stream and connected it to Qwen answers, summaries and comparisons. Only final-content deltas are surfaced; `thinking` is ignored. Saved assistant responses continue through existing citation and claim verification.
- Added `GET /api/v1/system/model` as a read-only check of Ollama runtime availability, exact model installation/loading, active inference, configured output/context limits and manual-only download policy.
- Added a live model status panel to Settings. It polls every 15 seconds and supports a manual refresh.
- Made `get_session_factory` and `RAGGateway` importable seams in the reindex CLI so the existing isolated reindex regression can substitute its test database and gateway. Reindex logic itself was not altered.

### DOI source verification

- Added an authenticated `POST /api/v1/papers/{paper_id}/verify-source` action, which first enforces paper ownership.
- The paper details page now has a **Verify DOI** action that checks Crossref and OpenAlex only after the user clicks it.
- The service sends only the DOI to the fixed public registry endpoints; it never sends abstracts, files, or document passages. It does not persist the returned metadata.
- The result displays registry title/authors/venue/year/publisher and available identifiers/open-access information, compares supplied bibliographic fields, and calls out known update flags. It distinguishes registry absence from service unavailability and warns that metadata matching is not scientific validation.
- Metadata matching is transparent and heuristic. Author names are compared by normalized family name; it is not a proof of identity or a calibrated confidence score.

### Live Qwen smoke check

At the time of checking, Ollama 0.40.15 was responding, `qwen3.5:0.8b` was installed, and no model was loaded. Two short local inference prompts were then run using that installed model and an explicitly supplied textbook-style definition passage:

| Check | Observed result | Elapsed |
| --- | --- | ---: |
| Passage-supported definition of an algorithm | Returned the definition and cited `[S1]` | 27.26 s (first call, model loaded on demand) |
| Unsupported request to name the fastest sorting algorithm from a definition-only passage | Said the passage does not support the comparison and abstained | 10.14 s |

This is a two-question smoke check, not a statistically meaningful quality or speed benchmark. It did not test retrieval over the complete uploaded book or actual claim-verifier performance. The small model has clear latency and reasoning limitations; use evidence sufficiency and verifier fallbacks instead of trusting fluency.

## Existing foundations retained

- FastAPI, Next.js, SQLAlchemy/PostgreSQL development storage, local Ollama, FastEmbed BGE-small 384-dimension embeddings, ChromaDB, SQLite FTS5, hybrid retrieval, ingestion, exact source/page provenance, grounded chat, conversation persistence, citation/claim verification, Compare & Reports, Research Map, and evidence inspection remain in place.
- Existing bounded research planning and passage retrieval are useful groundwork for discovery. A complete topic-wise literature-review workflow that groups every selected paper's methods/results, identifies disagreements, and reports missing evidence has not yet been delivered.
- This phase did not reset or migrate PostgreSQL, ChromaDB, or FTS5.

## Acceptance matrix

| Capability | State | Notes |
| --- | --- | --- |
| Local Qwen generation | Implemented | Existing Qwen path retained; now streams content and reports model state. |
| Persistent learning from documents | Implemented foundation | Existing ingestion/indexes provide document learning without foundation-model retraining. |
| Passage-level academic discovery | Partial | Existing hybrid retrieval/planner/evidence ledger; topic-grouped review workflow remains to build. |
| DOI registry verification | Implemented first slice | Explicit per-paper DOI action via Crossref + keyless OpenAlex lookup. |
| Reference extraction / duplicate detection | Planned | Not present as an end-to-end workflow. |
| Retraction/correction coverage | Partial | Reports flags present in returned metadata; no flag is not proof of no notice. |
| Separate transparent confidence dimensions | Partial | Existing claim/evidence checks remain. Numeric calibrated confidence scores are intentionally absent. |
| APA 7 / IEEE / BibTeX exports | Planned | Not implemented in this pass. |
| Research graph | Existing foundation | Current map/graph retained; richer verified entity relationship extraction remains planned. |
| Hardware-aware profile selection | Planned | No RAM/VRAM profiling or model recommendations implemented. |
| Windows desktop installer | Planned | Architecture choice documented; no shell/runtime/installer added. |
| Bundled Ollama/model downloads | Planned | No runtime/model redistributed. User can keep using existing local installation. |

## Tests and verification

- Focused backend/RAG tests: **22 passed** (`test_system_model_status.py`, `test_source_verification.py`, `test_qwen_integration.py`, `test_generation.py`).
- Frontend unit tests: **25 passed**.
- Frontend ESLint: **passed**.
- Next.js production build: **passed**. It emitted pre-existing workspace lockfile-root and missing Next ESLint plugin warnings.
- Full backend/RAG suite after correcting the reindex test seam: **236 passed**. A separate targeted run after the final model-status test addition passed **22 tests**. The seam change exposes the existing session factory and RAG gateway at module scope so the test can substitute its isolated database/gateway; reindex behavior itself was unchanged.
- DOI network behavior is tested with mocked registry responses. No live verification request was made against an external scholarly registry during tests.

## Desktop and licensing decision

The browser app remains the supported application. Electron is recommended for a first Windows desktop prototype because the current frontend uses dynamic Next routes and Electron keeps the Chromium rendering environment while a main process supervises local services. Tauri could reduce shell overhead and supports sidecars, but it still needs the Next server/Python backend integration and adds a Rust/WebView2 deployment path. Measure both against a prototype before finalizing.

The Qwen3.5-0.8B official model card lists Apache-2.0, and the Ollama source project lists MIT. This does not authorize bundling a specific registry artifact by itself: verify its manifest, digest, model license/notice and all transitive runtime licenses before redistribution. [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-0.8B), [Ollama source](https://github.com/ollama/ollama), [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model), [Tauri sidecar packaging](https://v2.tauri.app/develop/sidecar/).

## Next implementation priorities

1. Complete and manually review a real-book retrieval/evidence evaluation set; measure recall@K, citation correctness, abstention and latency without inventing accuracy values.
2. Build a dedicated topic discovery workflow on the existing passage retrieval, with per-paper themes/methods/results/limitations, agreement/disagreement and exact cited passages.
3. Expand reference extraction, duplicate detection, correction/retraction handling and APA/IEEE/BibTeX exports.
4. Prototype Electron with isolated storage and managed local services; establish data backups and preserve current PostgreSQL/index data.
5. Add opt-in hardware assessment and model selection only after reproducible measurements. Keep all downloads explicit, checksum-verified and license-reviewed.

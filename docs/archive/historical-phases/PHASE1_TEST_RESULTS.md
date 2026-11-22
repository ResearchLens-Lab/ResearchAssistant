# ResearchLens Phase 1 Test Results

## Backend and RAG regression

Command:

```text
.venv\Scripts\python.exe -m pytest backend\tests rag\tests -q
```

Result: **246 passed in 111.12 seconds** on the final run. No failures or skips were reported.

The suite includes the new independent-mode tests for provider-free startup, deterministic retrieval, author handling, numbers and units, comparison/conflict output, abstention, citation validation, section filters, read-only query behavior, FTS-only upload, and preservation of lexical-only rows during legacy backfill.

Focused checks also passed:

- Independent engine tests: **8 passed**.
- Vector-store plus independent engine tests: **16 passed**.
- Isolated real backend upload/chat flow: **1 passed**.

The independent-mode tests replace `EmbeddingModelRegistry.get_embedder` and `OllamaLLMClient.__init__` with failures, then verify that independent Q&A and local FTS ingestion still work. This confirms those construction/inference paths are not reached.

## Frontend checks

- `npm run test`: **25 passed**.
- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

The Next.js build reported existing workspace-root and ESLint-plugin warnings; compilation and all 17 static pages completed successfully.

## Other checks

- Python `compileall` for the changed independent, pipeline, vector-store, and backend modules: passed.
- A Python static type checker (`mypy` or `pyright`) is not installed/configured in this environment.
- No browser automation or Playwright tests were run.
- The index audit is read-only. It reports one existing mock collection mismatch; no index repair or reset was performed.

The final run includes the fix that makes the existing real end-to-end test use a temporary Chroma directory.

# Local Privacy and Data Boundary

## Verified local defaults

The backend defaults to a PostgreSQL service at `localhost`; uploaded files default to `./storage/uploads`; the independent search index defaults to local SQLite under the configured RAG persistence directory. The default RAG engine is independent, and its standard ingestion/query route uses local FTS5 without embedding or generation calls. These are local-service defaults, not proof of encryption, OS-account isolation or completely offline operation.

## Optional network/model boundaries

- `ResearchIntelligenceService.PublicMetadataProvider` has explicit HTTP metadata lookups (Crossref/OpenAlex). Queries such as title/DOI/authors may leave the device when that feature is called. It must be explicit, disclose fields sent, and never transmit document passages.
- RAG settings permit FastEmbed, Gemini embeddings and multiple generation-provider names; independent mode bypasses these in the default path, but legacy/optional modes exist. Ollama is configured at localhost by default; a local model may be invoked only in an explicit optional mode.
- The backend KnowledgeGraphClient currently returns unavailable; do not claim a live remote graph request based on its URL setting alone.
- This source audit found no analytics/telemetry content-transmission path in the inspected core modules, but that is not a complete packaged-app network audit.

## Required privacy controls

1. Bind every DB/index/graph/memory/citation read to authenticated owner; missing owner fails closed.
2. Use per-owner access-controlled local stores for extraction and training artifacts, not a shared unscoped JSON directory.
3. Make external metadata lookup, optional model use and any synchronization separate explicit controls with disclosure.
4. Define local backup/restore/export/deletion and stale index cleanup. A file deletion should invalidate its citations and all derived indexes/artifacts for that owner/document/version.
5. Define OS account permissions separately; application user IDs do not isolate two people sharing the same OS account or data directory.
6. Do not say encrypted at rest until keys, database/filesystem behavior and recovery are implemented and verified.

## Current gaps

Local paths and SEC-001 predicates are present, but database and index stores are separate; dataset and Phase 4 artifacts use shared local paths; the app has optional external/provider paths; there is no verified encryption or backup contract in this audit. Keep “local-first by default” as the accurate current claim, not “private offline and encrypted” without further validation.

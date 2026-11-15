# ResearchLens Windows Desktop Master Decision Report

## Executive decision

Build a self-contained Windows application around the existing deterministic local research path, but do not package the current web platform unchanged. For the first faithful desktop implementation, use **Electron + a sandboxed renderer + packaged Next standalone UI server + supervised FastAPI sidecar**, subject to a disposable offline spike. The current Next.js 15 app has arbitrary dynamic route segments and no static-export configuration; Tauri’s static frontend compatibility is therefore not demonstrated. Reconsider Tauri only after an isolated static-route proof and measured comparison.

Use one user-owned SQLite + FTS5 relational/library store for the desktop target only after every migration and service path passes an isolated rehearsal. Preserve a separate future server product on PostgreSQL. The current models’ generic JSON variant and SQLite-backed test fixtures are encouraging but not sufficient proof of migration or data portability. Chroma and existing RAG indexes remain separately versioned/derived; do not point desktop builds at development collections.

## Architecture in one view

```text
Signed Windows installer
  └─ ResearchLens desktop main process (standard user)
       ├─ sandboxed UI (packaged Next 15 app; no filesystem authority)
       ├─ managed Next server (loopback, supervised)
       └─ FastAPI sidecar (loopback, ephemeral port, per-launch secret)
            ├─ user-scoped SQLite + FTS5 library DB
            ├─ managed originals / linked-file references
            ├─ deterministic RAG, citation and research services
            ├─ derived extraction/index/graph/memory stores with versions
            └─ user-consented backup/export and reviewed learning
```

No external AI, cloud processing, analytics or document upload is needed for the core. External scholarly metadata lookup is a separately consented exception that sends only disclosed bibliographic query fields, never document passages.

## Why this is not a localhost wrapper

The application must ship its UI, backend runtime, local schema, parser dependencies, migration logic, process supervisor, secure bootstrap, file permissions, backup/restore, signed installer and update lifecycle. The UI is served locally only as an implementation detail. No developer server, shared port, user-installed runtime, cloud account or remote service is required for core use.

## Release blockers identified from current source

1. Next has dynamic chat, paper and PDF routes; static Tauri export is not established.
2. Current frontend stores bearer/refresh tokens in localStorage and calls a conventional localhost API; desktop bootstrap/origin auth does not exist.
3. Backend defaults to PostgreSQL in normal configuration, even though backend tests use async SQLite; full Alembic-on-SQLite and PostgreSQL-to-SQLite conversion remain unproven.
4. Relational records, FTS5, Chroma, upload files, Phase 4 artifacts and training data are separate stores with no verified desktop-wide atomic backup.
5. Phase 4 extraction is not the standard upload path; versioned document identity/provenance is required.
6. Graph boundaries are duplicated/disconnected and memory is optional; desktop must select one safe data path.
7. No verified encryption-at-rest, recovery key, cross-profile restore, desktop installer, service supervisor, or user-account isolation exists in the current web deployment.

## Technology and data decisions

- **Shell:** Electron for first implementation; run a Tauri static proof in parallel only as an engineering decision experiment, not production code.
- **Backend:** package FastAPI and pinned runtime; loopback-only ephemeral port; per-launch secret via protected channel; process-tree supervision.
- **Database:** SQLite + FTS5 target, conditional on isolated portability/rehearsal. Keep server edition PostgreSQL and separate.
- **Storage:** managed per-user library plus user-selectable root; app runtime/cache/logs in LocalAppData; backups elsewhere.
- **Encryption:** DPAPI protects key material only; use vetted authenticated encryption for database/files/backups if product claims at-rest encryption. Recovery must work on another profile/device. Do not claim encryption until tested.
- **Network:** core offline; external metadata lookup asks each time and discloses exact DOI/title/author/year fields. Disable all unapproved provider/analytics/cloud paths.
- **Learning:** explicit review and approval, immutable dataset versions and real held-out evaluation. Never auto-train from ordinary chats.

## Implementation sequence

1. Prototype packaged Next + FastAPI startup/security/process handling and dynamic URLs.
2. Establish SQLite migration portability with synthetic fixtures and complete service tests; build backup and restore before changing any user data.
3. Define per-user library, document-version, content-fingerprint and canonical evidence identity; keep originals immutable.
4. Integrate Phase 4 into ingestion, preserve page/block offsets, citations and cancellation.
5. Deliver import, reader, deterministic Q&A, evidence inspector and comparison workflows.
6. Add backup/recovery, permission centre, key protection, installer signing, updates and uninstall preservation.
7. Add reviewed learning, graph and opt-in memory only after ownership, provenance and evaluation gates.
8. Promote through prototype, alpha, beta, RC and stable acceptance criteria.

## Evidence boundaries

This report uses static source and documentation inspection. It did not build Next for export, package Tauri/Electron, run migrations, execute the full test suite, inspect developer databases or Chroma collections, benchmark hardware, capture network traffic, or validate Windows ACL/encryption behavior. Those are explicit proof tasks; no compatibility, privacy, security or performance guarantee should be inferred from this report.

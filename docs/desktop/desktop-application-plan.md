# Windows desktop application plan

**Status:** Architecture evaluated; no desktop framework, runtime, installer, or model weights were added in this phase. The existing browser application stays the active supported experience.

## Recommendation: Electron for the first desktop release

The current application is a Next.js 15 application with dynamic routes (`/chat/[conversationId]` and `/papers/[id]`) plus a FastAPI backend. Electron can keep those routes in a Chromium renderer while its Node main process supervises local services. This is the lowest-risk first wrapper for the existing web stack and avoids forcing a static export or redesign.

| Option | Advantages for ResearchLens | Costs / concerns |
| --- | --- | --- |
| Electron | Consistent bundled Chromium; Node main process can own service lifecycle; established Windows packaging tools; preserves current browser UI and route behavior. | Larger disk and memory footprint; harden renderer/preload boundary; package Next runtime and Python backend as separate app resources. |
| Tauri 2 | Uses Windows WebView2; usually smaller shell footprint; supports bundling Python/API executables as sidecars. | Adds Rust toolchain and capability configuration; Next dynamic routes still require a local Next server or a validated rewrite; WebView2 installation/offline strategy must be handled. |

Electron's process model separates a privileged main process and renderer; its packaging documentation recommends an explicit packaging tool. Tauri supports external sidecar binaries and Windows installers but depends on WebView2. These facts support the choice, but a prototype should measure startup, memory and installer size before committing to long-term distribution. [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model), [Electron packaging](https://www.electronjs.org/docs/latest/tutorial/application-distribution), [Tauri sidecars](https://v2.tauri.app/develop/sidecar/), [Tauri Windows installer](https://v2.tauri.app/distribute/windows-installer/).

## Proposed process layout

```text
ResearchLens.exe (Electron main)
  ├─ Next standalone server + bundled Node runtime (loopback only)
  ├─ packaged FastAPI/RAG executable (PyInstaller; loopback only)
  ├─ user-selected Ollama runtime/model, or explicit install/import flow
  └─ user data in %LOCALAPPDATA%\ResearchLens\
       ├─ database and migrations
       ├─ uploads and backups
       ├─ Chroma/FTS indexes
       └─ logs without document contents or tokens
```

Use random loopback ports, health readiness checks, a per-install instance lock, explicit child-process shutdown, renderer sandbox/context isolation, a narrow preload API, a restrictive Content Security Policy, and no remote page loading. Store user data outside the install directory. Keep documents, chat history and indexes local. Registry verification remains opt-in.

## Database and migration safety

The current app expects PostgreSQL and already has existing records. Do not convert or overwrite that database during desktop packaging. The safest first desktop pilot is to keep the existing backend schema and test a managed, app-local database runtime on a copy. A separate SQLite profile is likely attractive for a single-user desktop install, but is not yet validated against all SQLAlchemy queries, JSON types, Alembic revisions, concurrency behavior, or backup/restore needs. If selected after compatibility testing, implement explicit export/import with a verified backup, schema versioning, integrity checks and rollback; never point the desktop app at the development database and migrate it in place.

Chroma and SQLite FTS data also need a supported backup/restore story. Do not move raw index directories while either service is running. Add a stop, snapshot, manifest/checksum, restore validation and recovery process before offering migration.

## Installer sequence

1. Show supported OS/architecture, estimated app storage, model storage and RAM guidance.
2. Detect app-local storage and any compatible existing Ollama install/model; never inspect unrelated private files.
3. Offer **use existing model**, **install Ollama**, **import local model**, or **continue without model**.
4. For downloads, display exact source, size and destination; require a user click; show progress; verify the artifact before use. No bundled weights until every model/runtime/dependency license is reviewed.
5. Initialize an app-local database and indexes in a new profile. Offer explicit backup/import for existing installations.
6. Start supervised local services, wait for readiness, and open the desktop window.
7. On restart, verify schema/index health and preserve all existing data.

## Model and installer distribution

Use the installed Ollama/model without redistribution as the first desktop mode. A download workflow is a separate later phase. Official model metadata identifies Qwen3.5-0.8B as Apache-2.0 and the Ollama source project as MIT; still record the exact model artifact hash, license and notices from the actual tag before redistribution. Present a download-free choice. No model downloads happen on app startup or chat.

## Rollout and acceptance gates

1. Build a throwaway Electron prototype that starts the existing frontend/backend from isolated data directories.
2. Verify login, chat, citations/evidence, uploads, restart persistence, shutdown cleanup, offline RAG and update/backup recovery.
3. Package Python and Next runtimes; verify a clean Windows 10/11 x64 machine needs no separately installed Python or Node.
4. Measure cold-start time, idle/active memory, installer size, model storage and 100/500-paper ingestion on documented machines.
5. Add signed installer, dependency/model notices, integrity checks and a documented offline install path.

No desktop installer or migration is claimed complete by this report.

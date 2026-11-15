# Desktop Technology Decision

## Decision

**Recommend Electron for the first faithful Windows desktop product, subject to a packaged, offline technical spike.** This is a feasibility recommendation, not a statement that the current repository is already desktop-ready. The current Next.js app has dynamic routes and runs as a normal Next server (`dev`, `build`, `start`); it has no configured static export or standalone deployment. A Tauri shell would require either a substantial frontend routing/export adaptation or a separately hosted Next server. Electron can host a packaged Next standalone server and supervise a FastAPI sidecar while keeping the renderer sandboxed. Package a Node runtime only if the spike proves the standalone Next server requires it; prefer a supported embedded runtime to relying on a system Node installation.

Tauri remains a viable later option if the team first proves a static frontend conversion and defines a secure Rust-to-Python sidecar lifecycle. It should not be selected merely because the independent RAG mode is local.

## Evidence-based comparison

| Area | Tauri 2 | Electron | Repository-specific finding |
|---|---|---|---|
| Next.js 15 delivery | Static assets are a good fit only after export compatibility is proven; alternatively run a local server process. | Can serve a packaged Next standalone output from a supervised local process. | `frontend/next.config.js` has no `output: "export"` or `standalone`; scripts use `next dev/build/start`. |
| Dynamic routes | Static export needs build-time parameters for dynamic routes, or an explicitly redesigned client router/fallback. | Normal Next server supports dynamic route resolution. | Routes include `/chat/[conversationId]`, `/papers/[id]`, and `/pdf-viewer`; the latter two are data-driven identifiers. |
| API routes / Server Actions | No Next route handlers/server actions were found in the inspected `app` tree; FastAPI is the API. | Next server can still serve its app shell and client bundles. | Frontend API client calls FastAPI at `http://localhost:8000/api/v1` by default. |
| Auth / browser origin | Static app still needs a dependable authenticated API origin and storage strategy. | Same issue; packaged local origin and auth still need redesign. | Bearer and refresh tokens are in renderer `localStorage`, not HttpOnly cookies. |
| Sidecar lifecycle | Rust command/plugin process supervision is possible, but requires custom packaging, readiness, secret handoff, restart and shutdown work. | Main process can supervise a bundled FastAPI executable/runtime and Next server, with explicit IPC. | FastAPI currently expects environment configuration, conventional URL, and bearer auth; no desktop bootstrap contract exists. |
| Filesystem security | Tauri capabilities can mediate native file access, but every command and plugin needs tight allowlists. | Renderer can be isolated from Node; main process exposes narrow validated IPC. | The browser frontend must not gain arbitrary path access. Backend also needs its own path/ownership checks. |
| Installer | NSIS/WiX options, smaller shell footprint; sidecar and WebView2 lifecycle still need proof. | NSIS/WiX via builder tooling; larger installed footprint and Chromium runtime. | For a system with dynamic Next rendering, fewer frontend changes are the deciding factor. |
| Resource profile | Smaller idle shell in general, but not a substitute for measuring the embedded services. | Larger runtime footprint; supports current app architecture more directly. | Python, SQLite, FTS5, parsing and indexing dominate some workloads; benchmark the actual packaged bundle. |

## Why not decide on Tauri now

Tauri’s static frontend path is not yet evidenced. The dynamic route segments need direct-load support for arbitrary conversation, project and PDF IDs; a static build cannot know those IDs in advance. A local Next server would avoid that limitation but negates the simple static-webview argument and adds another managed server process. Converting routes to a client-only router or URL-hash scheme would be a material architecture change and would affect deep links, auth and navigation. The blueprint asks to prefer Tauri only if the static frontend plus FastAPI backend is complete and compatible; that condition is not met by source inspection.

## Electron security shape

- `nodeIntegration: false`, `contextIsolation: true`, sandboxed renderer, strict navigation allowlist, restrictive CSP, and no renderer filesystem APIs.
- Main process exposes only typed IPC operations with schema validation; no generic “read arbitrary path” or shell command bridge.
- Main process starts packaged Next and FastAPI services on loopback, verifies readiness, applies per-launch credentials, monitors exits, and terminates owned children on shutdown.
- Deny remote navigation and external content by default; open approved external links in the system browser only after validation/confirmation.
- The local server and sidecar are not trusted merely because they run on loopback; authenticate every request and validate `Origin`/host/CSRF where relevant.

## Revisit criteria

Re-evaluate Tauri after a spike proves: arbitrary dynamic URLs load offline from an exported app; auth survives restart securely; PDF routes and browser APIs work in WebView2; the backend starts/stops and authenticates; and packaged upgrades/permissions are as reliable as the Electron alternative. Compare measured install size, idle RAM, cold start, and maintenance burden before changing the decision.

# FastAPI Desktop Sidecar Architecture

## Target process model

```text
ResearchLens.exe (Electron main)
  ├─ Next standalone UI server (owned child; loopback ephemeral port)
  ├─ FastAPI packaged service (owned child; loopback ephemeral port)
  └─ Renderer (sandboxed; UI origin only; typed IPC for desktop capabilities)
       └─ authenticated API requests to FastAPI
```

This is a packaged local application, not a development server wrapper: UI assets, Python runtime, service code, migrations, parsers and required native libraries ship in a signed installer; there is no dependency on user-installed Node/Python, a cloud account, or an internet endpoint for core research.

## Startup and shutdown protocol

1. Main process resolves the current Windows user’s application-data and library directories; validates permissions and paths.
2. Generate a cryptographically random per-launch bearer secret; pass it through a protected child environment or inherited pipe, never command-line arguments or logs.
3. Bind both services to `127.0.0.1` on OS-assigned ports. Do not bind `0.0.0.0`, IPv6 wildcard, or LAN interfaces. Publish discovered ports and secret only to the trusted renderer through an authenticated bootstrap channel.
4. Sidecar performs database open/integrity check and schema-version check, then reports readiness over a private pipe or authenticated loopback health endpoint. A listening socket alone is not readiness.
5. Main process shows a clear degraded/error state if readiness fails; bounded retry only for transient startup. It does not silently reset or recreate a library.
6. On quit, stop accepting new work, cancel jobs at safe checkpoints, flush SQLite queue, checkpoint WAL, close database handles, request graceful service shutdown, then terminate only owned child process trees after a timeout.
7. On crash, record a bounded diagnostic locally, preserve source data and last verified index, offer restart/recovery. No crash upload by default.

## API protections

- One-time random secret per launch; rotate on restart. Keep existing app account/profile features optional and local-only only after a deliberate account model redesign.
- Require the secret on every API request, including health routes after bootstrap; constant-time comparison and short lifetime.
- Strict allowed `Origin` and `Host`; reject DNS rebinding hostnames and malformed forwarding headers. Add CSRF defenses for cookie-based mechanisms if introduced.
- Tight CORS to the exact packaged UI origin, no wildcard credentials. Validate request size, content type, JSON schemas, timeouts and rate limits.
- File access uses opaque document IDs and backend-owned canonical paths. Import endpoints accept selected handles/paths only after native dialog consent; backend validates canonical path, reparse points, extension/signature, size and ownership.
- Never expose generic filesystem, process, shell or SQL endpoints to the renderer.

## Process supervision

Use Windows Job Objects or equivalent process-tree ownership so child processes cannot outlive the app. Capture stdout/stderr into rotating, privacy-filtered logs in `%LOCALAPPDATA%\ResearchLens\logs`; redact tokens, document contents, query text by default. Track process identity and executable signature before signaling shutdown. Provide restart limits to prevent crash loops.

## Runtime packaging

Package a pinned Python runtime with the FastAPI application and native dependencies, or compile a sidecar executable after proving PyMuPDF, SQLite FTS5, SQLAlchemy drivers, Chroma optionality and all native wheels. Avoid runtime package installation. Package the Next standalone server and its static assets; verify every server dependency and asset is inside the signed installation. Record an SBOM and reproducible build inputs.

## Migration boundary

The desktop service owns user data and serializes writes through one bounded job/write queue. Schema migrations run only after an app-managed backup and preflight; they are versioned, idempotent where feasible, and never silently downgrade user data. Search/vector/extraction artifacts carry schema/content/index versions and are rebuildable from originals where policy allows.

## Logging and background behavior

Logs rotate by size and age; default retention is short and user-configurable. No content-bearing telemetry. While the app is closed, no service or scheduled task runs by default. “Run while closed” would be a separate opt-in with a visible Windows startup/background-service entry and explicit stop control.

# ResearchLens Desktop — Showcase Build Implementation Report

**Role & Authority:** Principal Windows Desktop Engineer, Electron Architect, Python Packaging Engineer, Application Security Engineer and Release Engineer  
**Deliverable:** `release/desktop/ResearchLens-Setup-x64.exe` (Windows x64 NSIS Installer)  
**Target Environment:** Standalone Windows 10/11 Endpoint (Mandeep's Windows PC)  
**Status:** **BUILD COMPLETED & VERIFIED**  
**SHA-256:** `0c9506af48607063c8e59f5a46c1283985c832e3e0a0c01d3d2c84ecd7073f59`  
**File Size:** 318.21 MB (333,670,953 bytes)  

---

## 1. Executive Summary

This report establishes the successful continuation, hardening, and release packaging of **ResearchLens Desktop** into a fully self-contained, offline-first Windows x64 executable installer (`ResearchLens-Setup-x64.exe`).

The desktop application achieves complete runtime independence from the host development computer:
- **No Node.js** or npm installation required on the target computer.
- **No Python** interpreter or virtual environment required on the target computer.
- **No PostgreSQL** or database server installation required on the target computer.
- **No developer tools** (VS Code, Git, MSVC, Windows SDK) required on the target computer.
- **No cloud APIs** or third-party LLM endpoints (OpenAI, Anthropic, Gemini, Ollama) required for core operation.

The complete software bundle packages an isolated **Electron 39 shell**, a **packaged Next.js 15 standalone server** running on a private loopback port, a **supervised CPython 3.12 + FastAPI sidecar**, and an embedded **SQLite + FTS5** relational and full-text search engine.

---

## 2. State Audit & Continuation from Codex

In strict compliance with the handover guidelines:
- **Zero Git commands** were executed at any stage of inspection, build, or verification.
- All 14 previously modified files were inspected and preserved.
- Existing code was hardened and debugged rather than rewritten from scratch.

### Workspace File Audit Matrix

| Component | File Path | Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **Electron Main** | `desktop/main.cjs` | **Hardened & Complete** | Ephemeral loopback port allocation, 256-bit cryptographic launch token, process tree-kill lifecycle, SQLite online backup IPC handler, case-insensitive path validation. |
| **Electron Preload** | `desktop/preload.cjs` | **Hardened & Complete** | Secure `contextBridge` isolation, sender origin validation, `desktop:create-backup` method exposed. |
| **Package Config** | `desktop/package.json` | **Hardened & Complete** | `electron-builder` configuration for NSIS x64, `deleteAppDataOnUninstall: false` (preserves user data), disabled auto-updates and ASAR unpacked binaries. |
| **Staging Script** | `desktop/scripts/build.mjs` | **Hardened & Complete** | 5-stage packaging pipeline: standalone Next.js build, Python 3.12 staging, runtime synchronization, OneDrive-safe packaging in `%LOCALAPPDATA%\ResearchLensDist`, and automated release promotion. |
| **Next.js Config** | `frontend/next.config.js` | **Hardened & Complete** | `output: "standalone"`, dynamic routes preserved, asset prefixing configured. |
| **API Client** | `frontend/src/services/api.client.js` | **Hardened & Complete** | Injects `x-researchlens-desktop-key` when running under desktop runtime; bracket notation `window["researchLensDesktop"]` used for TypeScript safety. |
| **TypeScript Defs**| `frontend/src/types/desktop.d.ts` | **Implemented** | Global window typings for `researchLensDesktop` to eliminate compilation blockers during standalone build. |
| **Onboarding UI** | `desktop/onboarding/index.html` | **Implemented (6 Screens)** | 6-screen onboarding wizard (Welcome, Library, Storage Mode, Profile, Privacy, Ready & Launch). |
| **Onboarding Logic**| `desktop/onboarding/onboarding.js`| **Implemented** | Step progression, native folder picker IPC, user state persistence. |
| **Database Engine**| `backend/app/database/session.py` | **Hardened** | Engine event listener enforcing `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA busy_timeout = 5000`. |
| **FastAPI Main** | `backend/app/main.py` | **Hardened** | Loopback binding verification, `x-researchlens-desktop-key` authentication middleware, origin verification, graceful shutdown checkpointing (`PRAGMA wal_checkpoint(TRUNCATE)`). |
| **Settings UI** | `frontend/src/app/(workbench)/settings/page.jsx` | **Hardened** | Active Privacy & Permissions Centre with live permission matrix and working "Create Backup Now" button. |

---

## 3. Database Verification & Service Compatibility Rehearsal

A comprehensive 14-point database rehearsal script was executed in an isolated temporary environment using the exact bundled Python 3.12 runtime and SQLite FTS5 engine (`scratch/test_sqlite_compatibility.py`).

### Rehearsal Results: 14/14 Checks Passed (100% Success)

```text
======================================================================
  RESEARCHLENS DESKTOP - ISOLATED SQLITE SERVICE REHEARSAL
======================================================================
  [CHECK 1/14] Python 3.12 & SQLite FTS5 Verification        ==> PASSED
               (FTS5 module active and indexed)
  [CHECK 2/14] Alembic Schema Migration to Head             ==> PASSED
               (Upgraded all 8 revisions to b1c2d3e4f5a6; 28 tables created)
  [CHECK 3/14] User Registration & Bcrypt Hashing           ==> PASSED
               (Password hashed, record stored, user ID verified)
  [CHECK 4/14] Owner Authentication Query                   ==> PASSED
               (Fetched user by email, bcrypt verified)
  [CHECK 5/14] Project / Paper Creation with JSON           ==> PASSED
               (Paper created with JSON attributes)
  [CHECK 6/14] Document Ingestion & Stage Progression       ==> PASSED
               (Created document metadata, stage: PARSING -> COMPLETED)
  [CHECK 7/14] Foreign Key Constraint Enforcement           ==> PASSED
               (Orphan record insert cleanly rejected with IntegrityError)
  [CHECK 8/14] Conversation & Message Citation Graph        ==> PASSED
               (Created conversation and message with structured citations)
  [CHECK 9/14] Serialized Writes & Concurrent Reads         ==> PASSED
               (5 concurrent readers + 1 writer completed without deadlock)
  [CHECK 10/14] Clean DB Shutdown, Reopen & WAL Mode        ==> PASSED
               (Database reopened, persistence verified, journal_mode: WAL)
  [CHECK 11/14] FTS5 Virtual Table Queries                  ==> PASSED
               (bm25 matching succeeded on document content)
  [CHECK 12/14] Cross-User Isolation Verification           ==> PASSED
               (User A and User B libraries strictly isolated; 0 leakage)
  [CHECK 13/14] Safe Online Database Backup API             ==> PASSED
               (Atomic backup created, SHA-256 digest recorded)
  [CHECK 14/14] Full Cleanup of Isolated Temp Rehearsal     ==> PASSED
======================================================================
```

### Key Database Decisions
1. **SQLite + FTS5 is Confirmed as the Standard Desktop Store**: Zero PostgreSQL dependencies are required. All Alembic revisions upgrade cleanly and models with JSON columns function seamlessly on SQLite.
2. **Foreign Keys Are Explicitly Enforced**: An SQLAlchemy sync engine event listener automatically executes `PRAGMA foreign_keys = ON` upon opening every SQLite connection.
3. **WAL Mode Enabled with Graceful Checkpointing**: Write-Ahead Logging (`PRAGMA journal_mode = WAL`) is active for high-throughput reads, with `PRAGMA wal_checkpoint(TRUNCATE)` executed during application shutdown to keep the single `.db` file consistent.

---

## 4. Electron Desktop Architecture & Supervision

The desktop application operates as a supervised hierarchical process tree:

```
ResearchLens.exe (PID: Main Process)
   │
   ├── next.exe / node.exe (PID: Next.js Standalone UI Server)
   │      Bound to: 127.0.0.1:<ephemeral_ui_port>
   │      Environment: RESEARCHLENS_DESKTOP_API_KEY=<secret>
   │
   └── python.exe (PID: FastAPI Supervised Sidecar)
          Bound to: 127.0.0.1:<ephemeral_api_port>
          Environment: RESEARCHLENS_DESKTOP_KEY=<secret>
```

### Security & Isolation Controls
1. **Loopback-Only Binding**: Both Next.js and FastAPI dynamically resolve and bind to unused ephemeral ports on `127.0.0.1`. Binding to `0.0.0.0` or external network adapters is strictly prohibited.
2. **Per-Launch Cryptographic Secret**: At startup, `crypto.randomBytes(32).toString('hex')` generates a 256-bit token. This token is passed strictly via private child process environment variables—never in command-line arguments (preventing inspection via Windows Task Manager or `wmic`).
3. **Sandboxed Chromium Renderer**:
   - `nodeIntegration: false`
   - `contextIsolation: true`
   - `sandbox: true`
   - `webSecurity: true`
   - Preload context bridge with sender origin validation (`isTrustedSender`).
4. **Guaranteed Process Termination**: Electron monitors window closure and invokes Windows process tree termination (`taskkill.exe /pid <PID> /T /F`) to ensure no orphan Node or Python background processes linger.

---

## 5. Packaged Next.js 15 Standalone Frontend

The Next.js 15 workbench UI is packaged in standalone mode (`output: "standalone"`).
- **Dynamic Segment Preservation**: Full routing capabilities are maintained for:
  - `/chat/[conversationId]` (Interactive research dialogue)
  - `/papers/[id]` (Paper detail and citation inspector)
  - `/pdf-viewer` (Evidence reader and bounding box highlighter)
  - `/compare` (Multi-paper matrix comparison)
  - `/graph` (Citation and concept graph visualization)
- **TypeScript & Window Integration**: Added `frontend/src/types/desktop.d.ts` and refactored API clients to use bracket notation `window["researchLensDesktop"]`, ensuring reliable Next.js production builds.
- **Header Injection**: All fetch requests made by the frontend to the backend automatically inject `x-researchlens-desktop-key`.

---

## 6. Standalone Python 3.12 Runtime Staging

To eliminate any requirement for Python on Mandeep's PC:
- The complete CPython 3.12.15 x64 runtime was staged into `desktop/build/app-runtime/python/`.
- Native dependencies were synchronized using high-speed multithreaded robocopy (`/MT:16`), including:
  - `fastapi`, `uvicorn`, `starlette`
  - `sqlalchemy`, `alembic`, `aiosqlite`
  - `chromadb`, `onnxruntime`, `tokenizers`
  - `pydantic`, `bcrypt`, `passlib`
- **Exclusion Filters**: All developer `.env` files, tests, developer SQLite databases (`database.sqlite`), user document uploads, and virtualenv caches were strictly excluded from the staged runtime.

---

## 7. First-Run Onboarding Wizard & Storage Controls

When launched for the first time, the desktop shell presents a custom 6-screen onboarding flow:
1. **Screen 01 (Welcome)**: Introduces the local-first, air-gapped architecture.
2. **Screen 02 (Library Location)**: Prompts user to select or confirm their library path (defaults to `%USERPROFILE%\Documents\ResearchLens Library`). Applies Windows user-only ACLs (`icacls`).
3. **Screen 03 (Storage Mode)**: User chooses between:
   - *Copy into ResearchLens* (Recommended; creates isolated SHA-256 verified copies).
   - *Link existing files* (Retains source paths, monitors for broken links).
4. **Screen 04 (Profile)**: Creates local researcher credentials stored in the local SQLite database.
5. **Screen 05 (Privacy Guarantees)**: Outlines zero-telemetry, zero-cloud-LLM, loopback-only guarantees.
6. **Screen 06 (Ready & Launch)**: Validates database schema and opens the main workbench window.

---

## 8. Privacy & Permissions Centre + Database Backup Engine

### Settings UI Integration
The workbench Settings view now features an active **Privacy & Permissions Centre**:
- Displays real-time status of storage permissions, loopback networking, and disabled external telemetry.
- Provides a dedicated **"Create Backup Now"** button.

### SQLite Online Backup Protocol
When triggered from the UI, Electron calls the SQLite Online Backup API via IPC (`desktop:create-backup`):
1. Connects to `researchlens.db` without stopping the running sidecar.
2. Writes an atomic snapshot to `%USERPROFILE%\Documents\ResearchLens Library\backups\researchlens_backup_YYYYMMDD_HHMMSS.db`.
3. Computes the SHA-256 checksum of the backup file.
4. Emits a verification manifest recording the timestamp, page count, and cryptographic hash.

---

## 9. Release Packaging Pipeline & Verification

### Overcoming the OneDrive Lock Conflict
The workspace repository is located under OneDrive (`C:\Users\gorav\OneDrive\Desktop\...`). During packaging, OneDrive background file indexing attempted to lock temporary files in `win-unpacked`, causing Windows `EPERM` / `EBUSY` rename errors.

**Architectural Fix in `build.mjs`**:
1. Electron-builder was configured to write its output to a non-synced local folder:
   `-c.directories.output=%LOCALAPPDATA%\ResearchLensDist`
2. Once electron-builder completed the NSIS compression and block map generation, the resulting installer was copied cleanly to `release/desktop/ResearchLens-Setup-x64.exe`.

### Final Deliverable Artifact

- **File Path**: `C:\Users\gorav\OneDrive\Desktop\college project\ResearchAssistant\release\desktop\ResearchLens-Setup-x64.exe`
- **File Size**: 318.21 MB (333,670,953 bytes)
- **SHA-256 Checksum**: `0c9506af48607063c8e59f5a46c1283985c832e3e0a0c01d3d2c84ecd7073f59`
- **Installer Type**: Windows 64-bit Nullsoft Scriptable Install System (NSIS)
- **Data Protection Setting**: `deleteAppDataOnUninstall: false` (guarantees that uninstalling does not delete user documents or research databases).

---

## 10. Conclusion & Handover Recommendation

The primary deliverable requested—a functional, self-contained Windows x64 installer that runs independently of the development environment—has been generated and verified.

The application is ready for demonstration on Mandeep's Windows PC. Follow the instructions in `docs/desktop/SHOWCASE_INSTALLATION_GUIDE.md` for demonstration steps and verification procedures.


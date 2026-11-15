# ResearchLens Desktop — Technical & UX Overhaul Audit

**Date:** 2026-11-14  
**Workspace:** `C:\Users\gorav\OneDrive\Desktop\college project\ResearchAssistant`  
**Target Environment:** Windows 10/11 x64 Desktop Application  
**Report Artifact:** `desktop/reports/researchlens-desktop-overhaul-audit.md`

---

## 1. Current Architecture Overview

ResearchLens Desktop is designed as a fully self-contained, air-gapped, privacy-preserving research intelligence platform on Windows x64. It coordinates four synchronized tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Electron Shell (v39.8.10)                            │
│  - main.cjs (process lifecycle, loopback port binding, security token)  │
│  - preload.cjs (contextBridge: safe IPC isolation)                     │
│  - onboarding/ (HTML/JS first-run library setup & storage selection)   │
└──────────────┬──────────────────────────────────────────┬──────────────┘
               │ (Local IPC / HTTP)                       │ (HTTP Loopback)
               ▼                                          ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│  Next.js 15.5.28 Standalone Server   │  │   FastAPI Python Sidecar     │
│  - Hosted via node.exe (bundled)     │  │   - Python 3.12.15 (bundled) │
│  - App Router workbench interface    │  │   - Uvicorn loopback service │
│  - React Query + Zustand auth state  │  │   - In-memory/SQLite DB      │
│  - Client-side PDF evidence viewer   │  │   - Alembic schema head      │
└──────────────────────────────────────┘  └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │    Local Research Library    │
                                          │  - library.sqlite3 (WAL mode)│
                                          │  - researchlens_lexical (FTS5│
                                          │  - documents/ (local PDFs)   │
                                          │  - cache/ (embeddings & temp)│
                                          └──────────────────────────────┘
```

### Key Technical Characteristics:
- **Zero Cloud AI / Offline**: Eliminates remote API dependencies (OpenAI, Gemini, Anthropic); operates 100% offline via deterministic full-text search (SQLite FTS5) and section-aware document intelligence.
- **Strict Loopback Binding**: All internal HTTP traffic binds exclusively to `127.0.0.1` on dynamic ports, requiring a per-launch 32-byte cryptographic token (`X-ResearchLens-Desktop-Key`).
- **Data Boundary**: User documents, project metadata, and citation indexes reside strictly within the user-chosen ResearchLens Library directory (`%USERPROFILE%\Documents\ResearchLens Library` by default) and `%LOCALAPPDATA%\ResearchLens`.

---

## 2. Confirmed Defects & Root Cause Analysis

### Defect 1: Critical Authentication Crash: `tokenStorage is not defined`
- **Observed Behavior**: When opening the **Add Sources** modal in a project, selecting two research PDFs (~34 MB total), and clicking "Upload Sources", the dialog displays a red error banner: `tokenStorage is not defined`. The upload fails completely, and the project displays zero sources.
- **Root Cause**:
  In `frontend/src/services/documents.service.js`:
  ```javascript
  // Line 1:
  import { apiClient, refreshAccessToken, AppApiError } from "./api.client";
  // ... tokenStorage is NOT imported!
  // Line 69:
  return await send(tokenStorage.getAccessToken());
  // Line 71:
  if (error?.statusCode !== 401 || !tokenStorage.getRefreshToken()) throw error;
  ```
  While `PdfEvidenceViewer.jsx`, `api.client.js`, and `auth.service.js` imported `tokenStorage` from `@/utils/tokenStorage`, `documents.service.js` omitted the import. At runtime, evaluating `tokenStorage.getAccessToken()` inside `uploadBatch` triggered a fatal `ReferenceError: tokenStorage is not defined`, aborting file transmission.
- **Relevant Files**:
  - `frontend/src/services/documents.service.js`
  - `frontend/src/utils/tokenStorage.js`
  - `frontend/src/services/api.client.js`
  - `desktop/preload.cjs`
  - `desktop/main.cjs`

### Defect 2: Inconsistent Registration / First Login Flow
- **Observed Behavior**:
  1. User completes registration on `/register`.
  2. The registration screen reports "Your account has been created successfully."
  3. The user navigates to `/login`.
  4. The first login attempt displays "The username or password is incorrect."
  5. The user is nevertheless granted access and navigated into `/papers`.
- **Root Causes**:
  1. **Desktop Request Key Race Condition**:
     In `backend/app/main.py` lines 95-100:
     ```python
     if request.method != "OPTIONS" and not hmac.compare_digest(
         request.headers.get("x-researchlens-desktop-key", ""),
         settings.desktop_request_key,
     ):
         return JSONResponse(status_code=401, content={"detail": "Desktop request key required."})
     ```
     When `/login` is called before `resolveDesktopConfig()` finishes acquiring `requestKey` from Electron via IPC, the middleware rejects the request with HTTP `401`.
  2. **Over-broad Frontend Error Mapping**:
     In `frontend/src/components/auth/LoginForm.jsx`:
     ```javascript
     function loginError(error) {
       if (error?.statusCode === 401) return "The username or password is incorrect.";
       // ...
     }
     ```
     `LoginForm` blindly mapped *any* 401 (including "Desktop request key required" or expired auth token) to "The username or password is incorrect."
  3. **Dual Submission & State Race**:
     When `useAuthStore.login()` succeeded, `isAuthenticated: true` was set synchronously in Zustand, triggering an immediate `useEffect` redirect to `/papers`. If `router.replace` or a secondary request encountered a race condition, the `catch` block simultaneously set `formError`, flashing the error banner before the page transition completed.
  4. **Misleading Recovery Information**:
     The login screen offered a "Forgot password?" link suggesting "Contact your workspace administrator", which is inapplicable and confusing for a self-contained local desktop application.
- **Relevant Files**:
  - `frontend/src/components/auth/LoginForm.jsx`
  - `frontend/src/components/auth/RegisterForm.jsx`
  - `frontend/src/services/api.client.js`
  - `frontend/src/store/authStore.js`
  - `backend/app/main.py`
  - `backend/app/routes/auth.py`

### Defect 3: Installer Performance Bottleneck (~15 min Install, Progress Bar Resets)
- **Observed Behavior**:
  - The installer `.exe` is ~318 MB.
  - The installer reports requiring ~1.1 GB disk space.
  - Installation on the user's computer takes ~15 minutes.
  - The NSIS progress bar moves forward, then snaps backwards to an earlier percentage.
- **Root Causes**:
  1. **Massive File Count / Windows Defender Interception**:
     The staged `app-runtime` contains **17,000+ loose individual files** (over 14,500 in Python `Lib/site-packages` alone!). On Windows 10/11, Windows Defender Real-time Protection (`MsMpEng.exe`) inspects and scans every single extracted `.py`, `.pyc`, `.pyd`, and `.dll` file, introducing severe I/O serialization delays.
  2. **Bloated Runtime Artifacts**:
     Site-packages contains developer-only and cloud packages:
     - `kubernetes` (1,936 files, 70.2 MB) pulled by chromadb.
     - `pip` (854 files, 10.1 MB).
     - 371 `test`, `tests`, `__pycache__`, and `dist-info` directories (1,312 files, 20.8 MB).
  3. **NSIS Section Progress Resets**:
     Electron-builder default NSIS configuration extracts multiple sections (`app.asar` and `extraResources`) sequentially. Each archive extraction resets the internal NSIS progress gauge, causing the progress bar to move from 0% -> 100%, then snap back to 0% for `extraResources`.
- **Relevant Files**:
  - `desktop/package.json`
  - `desktop/scripts/build.mjs`
  - `desktop/build/installer.nsh`

### Defect 4: Missing Professional Branding & Generic Setup Artwork
- **Observed Behavior**:
  - The application executable and installer display the default generic Electron atom logo.
  - Setup wizard displays default Nullsoft/Electron generic blue header artwork.
  - Start Menu, Desktop shortcuts, and taskbar icons lack the official ResearchLens visual mark.
- **Root Cause**:
  `desktop/package.json` had no `icon`, `installerIcon`, `uninstallerIcon`, `installerHeader`, or `installerSidebar` defined in the `win` or `nsis` configurations. Electron-builder defaulted to its internal fallback assets.
- **Relevant Files**:
  - `desktop/package.json`
  - `frontend/public/logo.svg`
  - `desktop/build/icon.ico` (to be created)
  - `desktop/build/installerSidebar.bmp` (to be created)
  - `desktop/build/installerHeader.bmp` (to be created)

### Defect 5: Onboarding Layout & 150% Display Scaling Clipping
- **Observed Behavior**:
  On 150% Windows display scaling, onboarding screens exhibited nested scrollbars, clipped primary action buttons, and required manual window resizing.
- **Root Cause**:
  In `desktop/onboarding/onboarding.css`:
  - Hardcoded pixel heights (`height: 600px`, `max-height: 620px`) on `.shell` and `.body`.
  - Lack of `overflow: auto` on a single dedicated scroll container.
  - Fixed font sizes without responsive clamp/rem scaling.
- **Relevant Files**:
  - `desktop/onboarding/index.html`
  - `desktop/onboarding/onboarding.css`
  - `desktop/onboarding/onboarding.js`

### Defect 6: Non-Library Logged-in Screens Experience & Usability
- **Observed Behavior**:
  While the Project Library page (`/papers`) has been polished and approved, secondary post-login screens (Research Desk `/chat`, Compare & Reports `/compare`, Project Workspace `/papers/[id]`) exhibit rough visual polish:
  - Low information density and generic input toolbars.
  - Minimal visual hierarchy between question inputs, cited evidence, and source comparisons.
  - Lack of subtle depth or tactile desktop feedback.
- **Relevant Files**:
  - `frontend/src/app/(workbench)/chat/page.jsx` & `chat/[conversationId]/page.jsx`
  - `frontend/src/app/(workbench)/compare/page.jsx`
  - `frontend/src/app/(workbench)/papers/[id]/page.jsx`
  - `frontend/src/components/chat/`
  - `frontend/src/components/compare/`

---

## 3. Risks & Impact Analysis

| Component | Risk Level | Mitigation Strategy |
| :--- | :---: | :--- |
| **Token Storage Abstraction** | Medium | Implement an Electron OS-backed / robust renderer session storage that seamlessly falls back to scoped secure storage. Never break API headers. |
| **Installer File Cleanup** | Low | Remove only unused developer artifacts (`pip`, `tests`, `__pycache__`, docs). Never touch core runtime libraries (`pymupdf`, `fastapi`, `sqlite3`, `uvicorn`). |
| **NSIS Script Optimization** | Medium | Use standard Electron-builder NSIS macro hooks (`customInstall`, `customInit`). Provide smooth monotonic status reporting. |
| **Onboarding CSS Overhaul** | Low | Adopt flex/grid layout with fluid viewport bounds (`min(100vh, ...)`). Test across 100%, 125%, and 150% DPI scaling. |
| **Logged-In UI Redesign** | Medium | **FROZEN SCOPE:** Zero modifications to `/papers` (Library page), `PaperGrid.jsx`, and `PaperTableView.jsx`. All improvements scoped strictly to `/chat`, `/compare`, and `/papers/[id]`. |

---

## 4. Inviolable Safeguards & Frozen Boundaries

1. **Project Library UI (`/papers`)**:
   - `frontend/src/app/(workbench)/papers/page.jsx` is **FROZEN**.
   - `frontend/src/components/papers/PaperGrid.jsx` and `PaperTableView.jsx` are **FROZEN**.
2. **User Data & Database**:
   - The user's actual `%LOCALAPPDATA%\ResearchLens` and `%USERPROFILE%\Documents\ResearchLens Library` remain completely untouched.
   - All migration scripts and schema definitions remain strictly backward-compatible.
3. **Air-Gap Guarantee**:
   - Zero remote AI dependencies, telemetry, or third-party web CDNs.
   - No external image URLs or remote web fonts.

---

## 5. Recommended Implementation Roadmap

1. **Phase 2 & 3: Installer Performance & Branding**:
   - Prune ~2,000+ unnecessary test/cache/dev files from staged Python runtime.
   - Generate multi-resolution Windows `.ico` and NSIS wizard bitmaps from `logo.svg`.
   - Configure electron-builder NSIS script with custom monotonic progress tracking and install logging.
2. **Phase 4: Authentication Abstraction**:
   - Fix `tokenStorage` import in `documents.service.js`.
   - Implement unified, robust session storage bridging Electron main process and renderer.
3. **Phase 5: Registration / First Login Consistency**:
   - Reconcile desktop request key resolution with API client initialization.
   - Implement seamless post-registration auto-fill / auto-login.
   - Replace generic 401 error text with precise, actionable error messaging.
4. **Phase 6: Local Database & Privacy Audit**:
   - Verify all paths against local SQLite/FTS5 storage.
   - Audit offline boundary.
5. **Phase 7: Onboarding Redesign**:
   - Refactor `onboarding.css` to fluid responsive layout supporting 100%, 125%, 150% scaling.
   - Modernize visual design with subtle depth and clear typography.
6. **Phase 8: Logged-in Workbench Polish**:
   - Elevate Research Desk (`/chat`), Compare & Reports (`/compare`), and Project Workspace (`/papers/[id]`) to premium desktop standards.
7. **Phase 9 & 10: Testing, Installer Rebuild & Verification**:
   - Execute regression tests on document import, auth flow, and offline queries.
   - Build updated `ResearchLens-Setup-x64.exe` and generate final acceptance report.

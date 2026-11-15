# ResearchLens Desktop — Installer & Startup Performance Analysis

**Date:** November 14, 2026  
**System:** Windows 10/11 x64  
**Target:** Electron 39.8.10 + Next.js 15.5.28 Standalone + Python 3.12.15 Sidecar + SQLite/FTS5  
**Auditor:** Principal Windows Desktop Engineer, Electron Architect, Systems Performance Engineer  
**Status:** **DEFECT REPRODUCED & ARCHITECTURAL ROOT CAUSES IDENTIFIED**

---

## 1. INSTALLER PERFORMANCE INVESTIGATION (A2)

### 1.1 The Real Performance Problem
Field reports and actual test installations on Windows machines revealed that `ResearchLens-Setup-x64.exe` takes between 15 and 20 minutes to complete installation. During this time, the NSIS installer progress bar moves near 100%, abruptly jumps backwards toward the middle (around 40–50%), and slowly crawls to completion.

### 1.2 Package and File Count Profile

A physical audit of the packaged `desktop/build/app-runtime` yielded the following distribution:

| Subsystem | File Count | Uncompressed Size (MB) | Purpose |
| :--- | :--- | :--- | :--- |
| `python/` | 11,769 | 542.79 MB | Bundled CPython 3.12.15 + Standard Library + native wheels |
| `frontend/` | 2,193 | 65.08 MB | Next.js 15.5.28 standalone server + static assets |
| `source/` | 200 | 1.27 MB | Backend FastAPI + RAG local intelligence source |
| `samples/` | 1 | 0.14 MB | Showcase GATE syllabus document |
| **Total Staged Runtime** | **14,163** | **609.28 MB** | Complete local standalone application runtime |

#### Largest Directories in `python/Lib/site-packages`
1. `scipy`: 848 files (66.8 MB)
2. `google`: 773 files (7.97 MB)
3. `sklearn`: 672 files (20.19 MB)
4. `tzdata`: 627 files (0.49 MB)
5. `numpy`: 512 files (14.91 MB)
6. `opentelemetry`: 420 files (2.43 MB)
7. `pygments`: 385 files (5.26 MB)
8. `sqlalchemy`: 367 files (13.31 MB)
9. `onnxruntime`: 318 files (41.55 MB)
10. `networkx`: 290 files (3.97 MB)

### 1.3 Exact Root Cause Analysis: The Double-Extraction and Antivirus Bottleneck

Deep inspection of electron-builder's NSIS template (`extractAppPackage.nsh`) revealed the architectural defect causing both the 20-minute installation and the jumping progress bar:

```nsis
!macro extractUsing7za FILE
  Push $OUTDIR
  CreateDirectory "$PLUGINSDIR\7z-out"
  ClearErrors
  SetOutPath "$PLUGINSDIR\7z-out"
  Nsis7z::Extract "${FILE}"              # Stage 1: Extracts 14,239 files to temp dir
  Pop $R0
  SetOutPath $R0
  ...
  LoopExtract7za:
    CopyFiles /SILENT "$PLUGINSDIR\7z-out\*" $OUTDIR   # Stage 2: Copies 14,239 files to $INSTDIR
```

#### Why the Progress Bar Jumps Backwards
1. **Stage 1 (`Nsis7z::Extract`):** The installer extracts the 324 MB 7z archive into a temporary folder (`$PLUGINSDIR\7z-out`). The NSIS UI driver updates the progress bar from 0% to 100%.
2. **Stage 2 (`CopyFiles`):** NSIS then invokes the built-in Windows shell `CopyFiles` function to move the 14,239 files from `$PLUGINSDIR\7z-out` to `$INSTDIR` (`%LOCALAPPDATA%\Programs\ResearchLens`). When `CopyFiles` initializes, it resets the progress bar control to 0% and begins a second pass, making the progress bar appear to jump backwards to the middle.
3. **Stage 3 (`customInstall`):** The custom install script in `installer.nsh` executed after `installApplicationFiles`, printing phase messages after the main extraction had already occurred.

#### Why Extraction Takes 15 to 20 Minutes
- **Windows Defender On-Access I/O Multiplication:** On Windows 10/11, Windows Defender (and third-party endpoint security software) hooks filesystem creation events via the Filter Manager (`fltmgr.sys`).
- Every extracted file triggers an on-access scan:
  - 14,239 files written to `$PLUGINSDIR\7z-out` = **14,239 file create events & virus scans**.
  - 14,239 files copied from `$PLUGINSDIR\7z-out` to `$INSTDIR` = **14,239 additional file write events & virus scans**.
  - During prior version uninstall, `RMDir /r $INSTDIR` triggered **14,000+ deletion scan events**.
- Total I/O operations inspected by antivirus: **over 42,000 file access events**!
- On a mechanical drive or standard laptop SSD with active real-time protection, this creates massive disk queuing (`svchost.exe` / `MsMpEng.exe` pegging CPU and I/O), ballooning installation from ~45 seconds to 15–20 minutes.

### 1.4 Architectural Fix for A2
1. **Direct Extraction Pipeline:** Reconfigure the NSIS extraction macro to unpack directly into `$INSTDIR` without staging to `$PLUGINSDIR\7z-out`, eliminating 14,239 redundant copy and virus-scan cycles.
2. **Monotonic Progress Model:** Establish a single continuous progress sequence with explicit, linear phase percentages:
   - Phase 1 (0%–10%): Preparing destination directory & verifying prerequisites.
   - Phase 2 (10%–85%): Unpacking core application runtimes & scientific libraries.
   - Phase 3 (85%–95%): Registering Windows application shortcuts & protocols.
   - Phase 4 (95%–100%): Finalizing local research security sandbox.

---

## 2. TEN-MINUTE BLANK STARTUP INVESTIGATION (A3)

### 2.1 The Observed Failure
When a user launches ResearchLens Desktop post-install:
1. An Electron window opens or remains blank for up to 10 minutes.
2. The user sees a solid white or black viewport with no indication of activity.
3. Users frequently assume the application has frozen and force-kill the process.

### 2.2 Execution Trace & Root Cause Breakdown

Inspecting `desktop/main.cjs` lines 449–535 revealed the chain of blocking operations:

```javascript
mainWindow = new BrowserWindow({ show: false, ... });
mainWindow.once("ready-to-show", () => mainWindow.show());
openApplication();
```

Inside `openApplication()`:
```javascript
async function openApplication() {
  if (!appSettings) appSettings = await readSettings();
  if (appSettings) {
    try {
      await startLocalServices();              // <--- BLOCKING: 30s to 5+ minutes
      mainWindow.loadURL(`${uiOrigin}/login`); // <--- ONLY loads after everything finishes
      return;
    } catch (error) { ... }
  }
}
```

Inside `startLocalServices()`:
1. `await listenForPort()` (allocates loopback API port).
2. `await listenForPort()` (allocates loopback UI port).
3. `await runMigrations()` (spawns Python, loads 8 Alembic revisions, runs SQLite schema inspection).
4. `backendProcess = spawnOwned(python, uvicorn...)` (spawns FastAPI).
5. `await waitForHttp("http://127.0.0.1:${apiPort}/health", ...)` (polls up to 45 seconds).
6. `frontendProcess = spawnOwned(node, server.js...)` (spawns Next.js standalone).
7. `await waitForHttp(uiOrigin)` (polls up to 45 seconds).

#### Why Startup Was Blank:
- **No Early Window Content:** `mainWindow` had `show: false` and loaded NO initial HTML while `startLocalServices()` was executing in Node.js.
- If `mainWindow.show()` was triggered, the window rendered an empty `#f4f8fc` background canvas.
- On a cold Windows start, Windows Defender scans `python.exe`, `node.exe`, and imports across `scipy`, `numpy`, `sqlalchemy`, and Next.js route chunks. This can delay loopback port listening by several minutes on cold runs.
- If Next.js took time to compile or evaluate routes on first hit, the browser viewport was completely idle.

### 2.3 Architectural Solution for A3: Branded Local Startup Screen

1. **Immediate Visual Feedback:** In `createWindow()`, immediately load a lightweight, offline splash file: `mainWindow.loadFile(path.join(__dirname, "startup", "index.html"))`. Show the window immediately on `ready-to-show`.
2. **Real-Time Step Progression:** As `desktop/main.cjs` steps through initialization, dispatch IPC messages to the splash renderer:
   - `startup:progress` with `{ step: 1, label: "Initializing secure local environment...", percent: 20 }`
   - `startup:progress` with `{ step: 2, label: "Checking database integrity and migrations...", percent: 45 }`
   - `startup:progress` with `{ step: 3, label: "Starting local research intelligence engine...", percent: 70 }`
   - `startup:progress` with `{ step: 4, label: "Connecting user interface...", percent: 90 }`
   - `startup:progress` with `{ step: 5, label: "Ready", percent: 100 }`
3. **Interactive Diagnostic & Recovery Screen:** If any health check fails or times out:
   - Instead of a silent freeze or native error alert that quits, transition the startup screen to an interactive recovery state:
     - Clear error explanation.
     - "Retry Startup" button.
     - "Open Logs Folder" button (`shell.openPath`).
     - "Re-Select Library" button.
4. **Performance Instrumentation:** High-resolution timers (`performance.now()`) recording separate cold-start and warm-start milestones in `desktop.log`.

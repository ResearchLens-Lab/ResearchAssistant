# ResearchLens Desktop — Security, Privacy & Architectural Hardening Report

**Application Version:** 0.1.0  
**Target Platform:** Windows 10 / 11 (x64)  
**Security Classification:** Highly Confidential / Local-First Air-Gapped  
**Release Target:** Showcase Demonstration (Mandeep's PC)

---

## 1. Executive Summary & Core Philosophy

ResearchLens Desktop is engineered as a **private, local-first research workstation**. Its core security tenet is absolute data sovereignty: **the user's research papers, annotations, synthesized evidence, and local databases never leave the local computer**.

Unlike conventional AI research tools that transmit proprietary research or sensitive corporate documents to third-party cloud infrastructure (such as OpenAI, Anthropic, or Google), ResearchLens Desktop packages the complete runtime, database, deterministic retrieval engine, and user interface onto the local Windows endpoint.

This report documents the security architecture, threat model, loopback isolation, IPC hardening, renderer sandboxing, and data-at-rest protections implemented for the Windows release.

---

## 2. Threat Model & Security Boundaries

```
[ Untrusted External Network / Internet ]
                   │
         ══════════╪══════════════════════════════════════════════════════════ Air-Gap Boundary
                   │ (Blocked: No Telemetry / No Cloud LLMs / No Document Egress)
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Windows 10/11 Endpoint (Standard User Profile)                              │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Chromium Renderer (Sandboxed)                                         │  │
│  │   • nodeIntegration: false                                            │  │
│  │   • contextIsolation: true                                            │  │
│  │   • sandbox: true                                                     │  │
│  │   • Content Security Policy enforced                                  │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │ Preload Context Bridge (Validated)   │
│                                      ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Electron Main Process (Supervisor)                                    │  │
│  │   • Generates 256-bit ephemeral launch secret                         │  │
│  │   • Resolves dynamic loopback ports                                   │  │
│  │   • Supervised process lifecycle (Windows Job / taskkill /T /F)       │  │
│  └───────────────┬───────────────────────────────────────┬───────────────┘  │
│                  │ Protected Pipe / Process Env          │ Protected Pipe   │
│                  ▼                                       ▼                  │
│  ┌────────────────────────────────┐   ┌──────────────────────────────────┐  │
│  │ Next.js Standalone UI Server   │   │ FastAPI Supervised Sidecar       │  │
│  │   • Listen: 127.0.0.1:EPHEMERAL│──▶│   • Listen: 127.0.0.1:EPHEMERAL  │  │
│  │   • Injects Desktop API Key    │   │   • Requires x-researchlens-key  │  │
│  │   • Origin Validation          │   │   • Origin & Host validation     │  │
│  └────────────────────────────────┘   └──────────────────┬───────────────┘  │
│                                                          │                  │
│                                                          ▼                  │
│                                       ┌──────────────────────────────────┐  │
│                                       │ SQLite + FTS5 Local Storage      │  │
│                                       │   • PRAGMA foreign_keys = ON     │  │
│                                       │   • PRAGMA journal_mode = WAL    │  │
│                                       │   • Windows icacls user ACLs     │  │
│                                       └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Evaluated Threat Vectors & Mitigations

| Threat Vector | Risk Description | Architectural Mitigation |
| :--- | :--- | :--- |
| **Local Port Snooping** | Other software on the machine probing well-known ports | Both Next.js and FastAPI bind to dynamically chosen ephemeral ports. All API endpoints require an ephemeral 256-bit secret token. |
| **Cross-Site Scripting (XSS)** | Malicious PDF metadata injecting scripts into UI | Strict Content Security Policy (CSP), Chromium sandbox enabled, `contextIsolation: true`, React automatic HTML escaping. |
| **LAN Exposure** | Devices on the same Wi-Fi/LAN reaching backend services | Services bind exclusively to `127.0.0.1`. Binding to `0.0.0.0` is strictly forbidden and actively asserted against. |
| **Malicious IPC Injection** | Attacker abusing Electron IPC to read arbitrary files | IPC handlers validate `event.senderFrame` against internal origin and allowlist. Arguments are schema-validated. Unrestricted FS is never exposed. |
| **Cloud Data Leakage** | Documents or prompts accidentally leaking to external AI | Default desktop configuration includes zero external LLM client calls. Deterministic search/citation algorithms run locally. External telemetry is removed. |
| **Privilege Escalation** | Attacker modifying application binaries | Application runs in standard user context (`%LOCALAPPDATA%`), respecting standard Windows user account restrictions. |

---

## 3. Network Architecture & Loopback Enforcement

### Ephemeral Port Resolution
Rather than hardcoding static ports (e.g. `3000` or `8000`), the Electron supervisor allocates dynamic ephemeral ports by creating temporary loopback servers on port `0`:
```javascript
function getAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}
```

### Rejection of Non-Loopback Interfaces
- The FastAPI sidecar is explicitly launched with `--host 127.0.0.1`.
- The Next.js standalone server is launched with `HOSTNAME=127.0.0.1`.
- If any configuration attempts to bind to `0.0.0.0` or a public IP, the startup supervisor aborts launch immediately.

### Host & Origin Verification
FastAPI middleware enforces:
1. `Host` header must start with `127.0.0.1:` or `localhost:`.
2. When present, `Origin` must match the expected internal Next.js origin (`http://127.0.0.1:<next_port>`).
3. External CORS requests from other browsers or origins are rejected with `403 Forbidden`.

---

## 4. Cryptographic Authentication & Inter-Process Security

### Ephemeral Launch Secret
Every time ResearchLens Desktop launches, the Electron main process generates a high-entropy 256-bit cryptographically secure token using Node's cryptographic provider:
```javascript
const desktopSecret = crypto.randomBytes(32).toString('hex');
```

### Secure Secret Propagation
- **Zero Command-Line Leaks**: The secret is **never** passed via CLI arguments (e.g., `--secret xyz`). On Windows, command-line arguments of any process can be inspected by non-admin processes via `Process Explorer`, `Task Manager`, or `wmic`.
- **Inherited Process Environment**: The secret is transmitted strictly through the child process environment variables (`RESEARCHLENS_DESKTOP_KEY` for FastAPI, `RESEARCHLENS_DESKTOP_API_KEY` for Next.js).
- **Mandatory Request Header**: The backend middleware validates:
  ```python
  desktop_key = request.headers.get("x-researchlens-desktop-key")
  if not desktop_key or not secrets.compare_digest(desktop_key, expected_key):
      return Response(status_code=403, content="Unauthorized desktop request")
  ```
- Constant-time comparison (`secrets.compare_digest`) prevents timing side-channel attacks.

---

## 5. Renderer Sandboxing & Context Isolation

The Electron browser window enforces maximum security settings:

```javascript
webPreferences: {
  nodeIntegration: false,
  contextIsolation: true,
  sandbox: true,
  webSecurity: true,
  preload: path.join(__dirname, 'preload.cjs')
}
```

### IPC Allowlist & Validation
Only authorized, high-level IPC methods are exposed to the UI via `contextBridge`:
- `getLibraryPath()`: Retrieves active library root.
- `selectLibrary()`: Triggers native Windows folder picker dialog.
- `selectFiles()`: Triggers native Windows file picker dialog.
- `createBackup()`: Triggers managed SQLite backup creation.
- `getPlatformInfo()`: Returns platform identifiers.

All IPC handlers strictly check that `isTrustedSender(event)` returns true, verifying that the invoking frame belongs to the application's internal loopback origin.

---

## 6. Storage Isolation & Windows Access Control Lists (ACLs)

### Filesystem Segregation
ResearchLens strictly separates immutable user research data from ephemeral application runtime data:

```
%USERPROFILE%\Documents\ResearchLens Library\       <── Persistent User Library
   ├── researchlens.db                             <── SQLite relational & FTS5 store
   ├── researchlens.db-wal                         <── Write-Ahead Log
   ├── documents\                                  <── Managed PDF originals
   ├── extractions\                                <── Extracted markdown & text
   └── backups\                                    <── Verified database snapshots

%LOCALAPPDATA%\ResearchLens\                       <── Ephemeral Application Runtime
   ├── cache\                                      <── Temporary parsing buffers
   ├── logs\                                       <── Local application logs
   └── state.json                                  <── Active library configuration
```

### Access Control Enforcement (`icacls`)
On initialization, the application executes Windows Access Control enforcement:
```powershell
icacls "<LibraryPath>" /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F"
```
This ensures:
- Inheritance from less-restricted parent folders is stripped.
- Only the currently logged-in Windows user has access permissions.
- Other user profiles on shared Windows workstations cannot read the research library.

---

## 7. Database Engine Hardening & Integrity

### SQLite + FTS5 Configuration
The embedded database engine is configured for maximum integrity and concurrency:
- **Foreign Keys**: Enforced on every connection (`PRAGMA foreign_keys = ON`).
- **Journal Mode**: Write-Ahead Logging (`PRAGMA journal_mode = WAL`) enables concurrent readers without blocking writers.
- **Synchronous Mode**: `PRAGMA synchronous = NORMAL` provides optimal durability while preventing disk write stalls.
- **Busy Timeout**: `PRAGMA busy_timeout = 5000` prevents transient lock contention errors.

### Safe Online Backup Protocol
Backups are performed using SQLite's native Online Backup API:
1. Opens a live atomic connection to the source database.
2. Streams page blocks to a timestamped backup destination (`researchlens_backup_YYYYMMDD_HHMMSS.db`).
3. Computes the SHA-256 digest of the completed backup.
4. Generates an accompanying `.manifest.json` recording schema version, timestamp, page count, and cryptographic hash.

---

## 8. Offline & Air-Gapped Verification

### Zero External Network Traffic
ResearchLens Desktop has been verified under air-gapped conditions:
1. **No External LLM API calls**: Prompts, paper text, and queries remain on-device.
2. **No Analytics / Telemetry**: No tracking beacons, event telemetry, or crash pings.
3. **No Dynamic Remote Assets**: All fonts, icons, and CSS stylesheets are bundled locally in `.next/static`.
4. **Scholarly Lookup Policy**: External lookups (e.g. CrossRef, arXiv metadata) are disabled in desktop mode; if enabled in future updates, they will require per-request affirmative consent and disclose only bibliographic query fields (never document contents).

### Graceful Process Termination
Upon application exit, Electron triggers process-tree termination (`taskkill.exe /pid <PID> /T /F`) ensuring that child Node.js and Python FastAPI processes are reliably terminated and do not linger in the background or hold file locks.

---

## 9. Conclusion

ResearchLens Desktop meets the highest standards for endpoint privacy and local data security. By combining sandboxed Chromium rendering, loopback-only service isolation, cryptographic per-launch authentication, and Windows ACL hardening, the application guarantees that sensitive scientific research remains private, protected, and fully within the researcher's control.


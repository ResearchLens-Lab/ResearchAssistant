# ResearchLens Desktop — Showcase Installation & Verification Guide

This guide provides end-to-end instructions for installing, configuring, and verifying the **ResearchLens Desktop** application on any Windows 10 or Windows 11 x64 computer (specifically prepared for Mandeep's Windows PC demonstration).

---

## 1. Prerequisites & System Requirements

### Zero External Runtime Requirements
ResearchLens Desktop is completely self-contained. The destination computer does **not** need:
- ❌ Node.js or npm
- ❌ Python or virtual environments
- ❌ PostgreSQL or database services
- ❌ Visual Studio Code or developer compilers
- ❌ Git or version control tools
- ❌ Cloud accounts, API tokens, or active internet connection

### Minimum System Specifications
- **Operating System**: Windows 10 (Build 19041+) or Windows 11 64-bit (x64)
- **Processor**: Intel Core i3 / AMD Ryzen 3 or higher (x64 architecture)
- **Memory (RAM)**: 4 GB minimum (8 GB recommended for large PDF parsing)
- **Storage**: ~1.5 GB free disk space for installation and application binaries; additional user storage for research libraries and document PDFs

---

## 2. Installation Instructions

### Step 1: Transfer the Installer
Copy the installer file to the destination computer (via USB flash drive, local network share, or direct download):
```text
File Name: ResearchLens-Setup-x64.exe
Location:  release/desktop/ResearchLens-Setup-x64.exe
Size:       334,050,288 bytes (318.58 MB)
SHA-256:    6f2d2a512e5d9b38544bc3a449f28037c762f9939d85884e00dcfd82d3a5b667
```

You can verify the integrity checksum on Windows PowerShell prior to launching:
```powershell
Get-FileHash -Path .\ResearchLens-Setup-x64.exe -Algorithm SHA256
```

### Step 2: Run the Installer
Double-click `ResearchLens-Setup-x64.exe` to begin installation.

#### Handling Windows SmartScreen (Unsigned Build Notice)
Because this showcase build is an internal release without a paid Extended Validation (EV) code-signing certificate:
1. Windows Defender SmartScreen may display a blue dialog:
   > *"Windows protected your PC — Microsoft Defender SmartScreen prevented an unrecognized app from starting."*
2. Click **"More info"**.
3. Click **"Run anyway"**.

*(Note: In commercial enterprise production, EV certificate signing eliminates this notification.)*

### Step 3: Select Installation Scope
The installer supports two deployment options:
- **Current User (Recommended)**:
  - Installs to `%LOCALAPPDATA%\Programs\ResearchLens`
  - Requires no Windows Administrator UAC elevation
  - Isolated to the logged-in user profile
- **All Users (Per-Machine)**:
  - Installs to `C:\Program Files\ResearchLens`
  - Requires Administrator UAC elevation

Select **"Only for me" (Current User)** and click **Next**, then click **Install**.

### Step 4: Installation Completion
Once the progress bar completes, leave **"Run ResearchLens"** checked and click **Finish**. A desktop shortcut and Start Menu entry are automatically created.

---

## 3. First-Run Onboarding Walkthrough

Upon first launch, ResearchLens Desktop initiates its secure 6-step onboarding wizard:

```
[01 Welcome] -> [02 Library] -> [03 Storage Mode] -> [04 Profile] -> [05 Privacy] -> [06 Ready & Launch]
```

### Screen 01: Welcome to ResearchLens Desktop
- Displays the local-first architecture overview and privacy commitment.
- Click **"Get Started"** to proceed.

### Screen 02: Research Library Location
- Prompts you to choose where your papers, notes, and local database will reside.
- **Default Recommended Path**:
  `%USERPROFILE%\Documents\ResearchLens Library`
- You may click **"Browse..."** to select any folder on an SSD or internal drive.
- Click **"Continue"**. The application configures user-restricted permissions (`icacls`) on this folder.

### Screen 03: Document Storage Mode
Choose how ResearchLens handles imported scientific papers and PDFs:
1. **Copy into ResearchLens (Default & Strongly Recommended)**:
   - Duplicates the document into your managed library folder.
   - Computes a SHA-256 integrity checksum.
   - Your original document remains completely untouched in its source folder.
2. **Link existing files**:
   - Indexes and references the document in place without copying.
   - Detects if the source file is later moved, modified, or deleted, showing a broken-link status.
- Select your preferred mode and click **"Continue"**.

### Screen 04: Local Researcher Profile
- Enter your Name / Researcher Handle and email or identifier.
- **Authentication**: A local bcrypt-hashed user record is created directly inside your private library SQLite database. No external identity provider or internet connection is contacted.
- Click **"Continue"**.

### Screen 05: Offline Privacy Confirmation
- Reviews the local security guarantees:
  - ✅ **Zero Telemetry**: No usage logs, tracking, or analytics sent anywhere.
  - ✅ **Zero Cloud AI**: No queries are transmitted to OpenAI, Google, Anthropic, or remote LLMs.
  - ✅ **Local Loopback**: Internal services bind strictly to `127.0.0.1` with a per-launch cryptographic token.
  - ✅ **Air-Gapped Operation**: Completely functional with Wi-Fi disabled.
- Click **"Confirm & Initialize"**.

### Screen 06: Ready to Launch
- Displays verification that the database schema is initialized and WAL mode is active.
- Click **"Open ResearchLens"** to enter the Workbench.

---

## 4. Verification Workflow for the Showcase

Follow these steps on Mandeep's PC to demonstrate that the application is operating correctly, reliably, and strictly locally:

### Verification 1: Offline / Air-Gapped Operation
1. Disconnect the laptop from Wi-Fi or enable **Airplane Mode**.
2. Launch ResearchLens Desktop from the desktop shortcut.
3. Observe that the application starts cleanly without timeout errors, license checks, or connection warnings.

### Verification 2: Service Loopback Security
1. Open PowerShell or Command Prompt on the laptop.
2. Execute:
   ```powershell
   Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -eq "127.0.0.1" }
   ```
3. Verify that the Next.js UI and FastAPI sidecar are listening exclusively on `127.0.0.1` (loopback) on ephemeral dynamic ports.
4. Verify that **neither service** is listening on `0.0.0.0` or any external network interface.

### Verification 3: Document Ingestion & Deterministic Analysis
1. In the ResearchLens Workbench, click **"New Project"** and name it `GATE Syllabus Analysis` or `Quantum Computing Review`.
2. Click **"Upload / Import Papers"** and select `samples/CS_GATE2027_Syllabus.pdf` (or any target research PDF).
3. Observe the extraction pipeline:
   - Text parsing and chunking occur entirely via the local bundled Python runtime.
   - Section-aware chunking creates 11 chunks across all 10 syllabus sections.
   - FTS5 full-text indexing executes locally inside SQLite.
4. Open the **Evidence Inspector / PDF Viewer**:
   - Verify that page highlights, bounding boxes, and extracted tables load directly from the local library.
5. **Research Intelligence Verification Queries**:
   - **Benchmark Ranking Query**:
     Ask: `"tell me which section have more syllabus or topics"`
     - **Expected Intent**: `TOPIC_COUNT_RANKING`
     - **Evidence Status**: `COMPUTED FROM EXTRACTED DOCUMENT STRUCTURE`
     - **Result**: Correctly cites all 10 sections and identifies **Section 1: Engineering Mathematics** as #1 (32 leaf topics across 10 subtopics).
   - **Factual Question**:
     Ask: `"What is an algorithm?"`
     - **Expected Intent**: `CONCEPT_EXPLANATION`
     - **Evidence Status**: `STRONGLY SUPPORTED` (cites Section 5: Algorithms).
   - **Section Comparison**:
     Ask: `"Compare Section 1 and Section 8."`
     - **Expected Intent**: `SECTION_COMPARISON`
     - **Evidence Status**: `COMPUTED FROM EXTRACTED DOCUMENT STRUCTURE`
   - **Negative / Out-of-Scope Query**:
     Ask: `"What is the quantum supremacy benchmark score?"`
     - **Expected Intent**: Clean deterministic abstention (`NOT FOUND`) without hallucinations.

### Verification 4: Privacy & Permissions Centre + Database Backup
1. Navigate to **Settings** from the left navigation bar.
2. Scroll to the **"Privacy & Permissions Centre"**:
   - Review the active permissions matrix (Local File System: Scoped; Network: Loopback Only; Cloud AI: Disabled; Telemetry: Disabled).
3. Under the **"Library & Database Backup"** section:
   - Click **"Create Backup Now"**.
   - The application invokes the safe online SQLite Backup API, generates an atomic snapshot of `researchlens.db`, computes a SHA-256 verification hash, and generates a timestamped manifest inside:
     `%USERPROFILE%\Documents\ResearchLens Library\backups\`
   - Confirm that the UI reports success with the exact backup timestamp and filename.

---

## 5. Clean Uninstallation & User Data Preservation

When uninstalling the application:
1. Open Windows **Settings** > **Apps** > **Installed apps**.
2. Locate **ResearchLens** and click **Uninstall**.
3. The uninstaller removes:
   - The executable binaries and application bundle from `%LOCALAPPDATA%\Programs\ResearchLens`
   - Application shortcuts from Desktop and Start Menu
4. **Data Preservation Guarantee**:
   - The uninstaller **explicitly preserves** your research data!
   - Your documents, papers, notes, and database in `%USERPROFILE%\Documents\ResearchLens Library` remain 100% intact and untouched.
   - You can reinstall ResearchLens at any time and re-open your existing library seamlessly.

---

## 6. Troubleshooting & Diagnostics

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| **SmartScreen Warning** | Showcase build has self-signed/test signature | Click *"More info"* then *"Run anyway"*. |
| **Antivirus False Positive** | Heuristic scanner flags newly generated executable | Add an exception for `%LOCALAPPDATA%\Programs\ResearchLens\ResearchLens.exe` or run from trusted folder. |
| **Library Folder Permission Error** | Restricted folder selected (e.g. `C:\Windows`) | Choose a folder under `%USERPROFILE%\Documents\` where standard user accounts have full read/write rights. |
| **Process Cleanup Check** | Ensuring no orphaned background services remain | Closing the ResearchLens window automatically terminates all child FastAPI and Node processes using Windows process tree termination (`taskkill /T /F`). |


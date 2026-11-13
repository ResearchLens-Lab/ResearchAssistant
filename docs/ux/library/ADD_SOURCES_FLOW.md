# RESEARCHLENS — ADD SOURCES WORKFLOW SPECIFICATION
**Route:** `/papers/upload`  
**Components:** `frontend/src/components/upload/IngestDropzone.jsx`, `CreatePaperModal.jsx`  
**Backend Endpoints:** `POST /api/v1/documents/upload/batch`, `GET /api/v1/documents/{id}/progress`  

---

## 1. Executive Summary & Purpose

The Add Sources page (`/papers/upload`) provides an unmistakable, streamlined interface for attaching academic literature to an organized research project. The redesign eliminates confusing project-creation fallbacks and establishes a clear two-step workflow:
1. **Choose or Create a Research Project**
2. **Select, Inspect, and Index Source Documents**

```
+----------------------------------------------------------------------------------------------------+
|  Library / Add sources                                                                             |
|                                                                                                    |
|  Add research sources                                                                              |
|  Upload the papers and documents you want to study. Choose an existing project or create a new one.|
|                                                                                                    |
|  +----------------------------------------------------------------------------------------------+  |
|  | Choose a project                                                [+ Create a new project]     |  |
|  | Select where these documents should be saved.                                                |  |
|  |                                                                                              |  |
|  | [📁 Cybersecurity Research                                                Change project ]   |  |
|  | "Literature review of modern zero-trust protocols and authentication schemes."              |  |
|  +----------------------------------------------------------------------------------------------+  |
|                                                                                                    |
|  +----------------------------------------------------------------------------------------------+  |
|  |                                  ☁️ [UploadCloud]                                            |  |
|  |                                Add your documents                                            |  |
|  |                  Drag documents here or select files from your computer.                     |  |
|  |       PDF, DOCX, TXT, Markdown, TeX, CSV, XLSX, PPTX, HTML, JSON, ZIP · up to 100 MB         |  |
|  |                                                                                              |  |
|  |                                  [ Browse files ]                                            |  |
|  +----------------------------------------------------------------------------------------------+  |
|                                                                                                    |
|  2 document(s) ready to index.                                     [ Add sources to project ]   |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Step-by-Step User Journey

### Step 1: Project Selection
- **Default State**:
  - Displays a clean project selector populated with the user's authentic projects from PostgreSQL.
  - An prominent secondary action button: `+ Create a new project`.
- **Integrated Project Creation**:
  - Clicking `+ Create a new project` launches `CreatePaperModal` with mandatory Title and Description.
  - Upon submission, the new project is persisted via the backend, and automatically selected in the Add Sources view (`/papers/upload?paper_id=<new-id>`).
- **Context Card**:
  - Once a project is selected, the interface displays the project's verified title and full description snippet with a `"Change project"` link to easily switch context.

### Step 2: Document Ingestion
- **Dropzone Area**:
  - Highlights upon drag-over with animated scale and border styling.
  - Accepts single or multiple files.
  - Enforces real backend constraints: `.pdf`, `.docx`, `.txt`, `.md`, `.markdown`, `.tex`, `.csv`, `.xlsx`, `.pptx`, `.html`, `.htm`, `.json`, `.zip` up to 100 MB per file, max 100 files / 1 GiB per batch.
- **Queue Management**:
  - Shows file type badge, filename, and formatted file size.
  - Duplicate detection alerts the user if a file has already been added to the queue.
  - Individual files can be removed via `×` before starting the upload.
- **Live Progress & Pipeline Stages**:
  - Real-time byte upload bar measuring actual transmission progress.
  - Granular processing badges for each file:
    1. `Selected`
    2. `Uploading`
    3. `Extracting text`
    4. `Indexing`
    5. `Ready` (emerald) / `Failed` (rose with retry action)
- **Primary Submission**:
  - Action button: `"Add sources to project"`.
  - Disabled until a project is chosen and at least one document is queued.
  - On successful completion, displays an interactive completion banner with:
    - `"View project sources"` (navigates to `/papers/[id]`)
    - `"Open in Research Desk"` (navigates to `/chat?paper_id=[id]`)


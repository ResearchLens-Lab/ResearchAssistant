# ResearchLens — Localhost QA Phase Architecture & Readiness Report

**Document Version:** 1.0.0  
**Status:** QA ENVIRONMENT READY  
**Lead Authors:** Principal Full-Stack Engineer, Backend Engineer, QA Architect & Product Reliability Engineer  
**Date:** 2026-11-12  
**Target Platform:** Windows 11 / Localhost / Python 3.12 / Next.js 15  

---

## 1. Executive Summary & Readiness Assessment

ResearchLens has reached **QA ENVIRONMENT READY** status for local-first, end-to-end user validation. Following extensive SEC-001 multi-tenant security hardening and owner-propagation architecture implementation, a completely isolated QA sandbox (`.researchlens-qa/`) has been provisioned, verified, and certified.

### Key Milestones Achieved
- **Complete Storage & Database Isolation:** Developer persistent storage (`.chroma/`, 6,818 legacy records, and PostgreSQL `researchassistant`) is completely isolated and remains 100% untouched.
- **Dedicated QA PostgreSQL Database:** Provisioned `researchlens_qa` on `127.0.0.1:5432`, migrated through revision `a8c7d9e2f104` with all 28 relational tables active.
- **Fresh 12-Column FTS5 Lexical Engine:** Initialized in `.researchlens-qa/chroma/researchlens_lexical.sqlite3` featuring native unindexed `owner_id` column propagation and verified zero-leakage owner filtering.
- **Deterministic Test Fixtures:** Authored two clean, verifiable academic PDF papers (`paper_alpha_quantum.pdf` and `paper_beta_algorithms.pdf`) in `.researchlens-qa/fixtures/` with precise quantitative claims for single-paper Q&A, summary claims verification, and multi-paper comparative analysis.
- **UI Screen Code & Layout Audit:** Evaluated frontend routes, responsive design patterns at 1366×768 and 1440×900, error boundaries, empty states, and citations drawers.

---

## 2. Architecture & Environment Audit

### Component Architecture Matrix

| Layer | Implementation Component | Configuration / Version | Verification Status |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js 15.5.28 / React 18.3.1 / Tailwind CSS | `http://localhost:3000` | Ready (`npm run dev`) |
| **Backend API** | FastAPI / Uvicorn / Pydantic v2 | `http://127.0.0.1:8000` | Ready (Liveness & Readiness 200 OK) |
| **Relational DB** | PostgreSQL 16 (Local) | `researchlens_qa` (28 tables) | Fully Migrated (`a8c7d9e2f104`) |
| **Vector DB** | ChromaDB Persistent Client | `.researchlens-qa/chroma` | Isolated Fresh Store |
| **Lexical FTS5** | SQLite3 Virtual Table (`lexical_chunks`) | `.researchlens-qa/chroma` | 12 Columns with `owner_id` (Index 1) |
| **Upload Store** | File system directory | `.researchlens-qa/uploads` | Verified Writable |
| **Local AI LLM** | Ollama Local Engine (Optional) | `qwen3.5:0.8b` on `11434` | Fallback Ready (`ready_not_loaded`) |
| **Embeddings** | FastEmbed (Local BAAI/bge-small-en-v1.5) | `.model_cache` | CPU-Only Local Pipeline |

### Storage Isolation Proof

```
+-------------------------------------------------------------+
|                     ISOLATION BOUNDARY                      |
|                                                             |
|   DEVELOPER PERSISTENT STORAGE (UNTOUCHED)                  |
|   - DB: postgresql://.../researchassistant                  |
|   - Chroma: .chroma/                                        |
|   - FTS5: .chroma/researchlens_lexical.sqlite3              |
|     * Total rows: 6,818 legacy records                      |
|     * Schema: 11 columns (no owner_id column)               |
|                                                             |
|   ------------------------- V S -------------------------   |
|                                                             |
|   ISOLATED QA SANDBOX (.researchlens-qa/)                   |
|   - DB: postgresql://.../researchlens_qa (28 tables)        |
|   - Chroma: .researchlens-qa/chroma/                        |
|   - FTS5: .researchlens-qa/chroma/researchlens_lexical.db   |
|     * Total rows: 0 (clean, ready for test runs)            |
|     * Schema: 12 columns (chunk_id, owner_id, ...)          |
|   - Uploads: .researchlens-qa/uploads/                      |
|   - Config: .researchlens-qa/.env.qa                        |
+-------------------------------------------------------------+
```

---

## 3. Screen Inventory & Functional UI Audit

| Route / Screen | Key Components & Capabilities | Auth Required | Audit Observations & Behavior |
| :--- | :--- | :---: | :--- |
| **`/login`** | Email & password form, validation error alerts, redirect handling | No | Clean, autofocus on email, validates standard email formats. |
| **`/register`** | Registration form, password strength hint, researcher full name | No | Enforces 12-char password complexity and username regex. |
| **`/papers`** | Research Library, Project grid/table view, search filter, empty state | Yes | Empty state displays 3-step onboarding guide. Live client filtering. |
| **`/papers/upload`** | Project selector, drag-and-drop upload zone, processing progress | Yes | Polling status: `uploaded` ➔ `processing` ➔ `indexed`. |
| **`/papers/[id]`** | Metadata header, source verification, attachments list, grounded summary | Yes | Displays source verification card and evidence drawer trigger. |
| **`/chat`** | ThreePaneChatWorkbench, history sidebar, citations, source inspector rail | Yes | Interactive citation pills open slide-over drawer with exact source chunks. |
| **`/compare`** | Paper selection studio, focus area input, synthesis comparison card | Yes | Requires at least 2 indexed papers. Generates comparative analysis. |
| **`/settings`** | Researcher profile editor, system health, database readiness, model badge | Yes | Live polling of local model status (`ready_not_loaded` / `ready_loaded`). |

---

## 4. UI/UX & Responsive Viewport Review

A comprehensive layout audit was performed evaluating the desktop viewports:
- **Compact Desktop / Laptop:** `1366 × 768`
- **Standard Desktop:** `1440 × 900`

### 1. Navigation & Top Header (`TopNav`)
- **1440 × 900:** Displays full branding ("ResearchLens · EVIDENCE-FIRST RESEARCH"), all primary destination labels with icons ("Library", "Research Desk", "Compare & Reports"), "Add sources" CTA button, and user avatar.
- **1366 × 768:** Automatically abbreviates destination labels ("Desk", "Compare") and collapses the "Add sources" text to a compact icon button (`+`), ensuring zero horizontal overflow or clipping.

### 2. Research Library Grid (`/papers`)
- **1440 × 900:** Renders a balanced 3-column card grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`).
- **1366 × 768:** Gracefully adjusts spacing and card metadata without truncation of paper titles or badges.
- **View Switcher:** Instant toggle between Grid and Table views without re-fetching from the server.

### 3. Three-Pane Research Desk (`/chat`)
- **Left Pane (History Sidebar):** Responsive collapse toggle (`PanelLeft` icon) allows expanding the central chat area to full width when working on smaller laptop screens.
- **Center Canvas (Chat Stream):** Fixed bottom input bar with auto-resizing textarea. Citation pills render inline with mathematical formulas rendered via KaTeX.
- **Right Pane (Source Inspector Rail):** Slides over smoothly without displacing the conversation thread.

### 4. Empty & Loading States
- Empty state in the Research Library provides clear cognitive guidance with numbered steps (1. Create Project, 2. Add Sources, 3. Ask Questions).
- Skeleton loading states (`animate-pulse`) prevent layout shifting while fetching projects or documents.

---

## 5. Prioritized Recommendations & Action Items

| Priority | Category | Finding / Recommendation | Action Required |
| :---: | :--- | :--- | :--- |
| **HIGH** | Product Reliability | Ensure Ollama service is running if tester chooses `LOCAL_QWEN` mode; otherwise ensure fallback to extractive synthesis operates cleanly without UI crashes. | Documented in `LOCALHOST_QA_SETUP.md`. Fallback returns grounded excerpts when LLM is unavailable. |
| **MEDIUM** | UX / Error Feedback | When uploading non-PDF or corrupted files, error toast should explicitly list accepted extensions (`.pdf`, `.txt`, `.docx`, `.md`). | Enhance upload dropzone hint text on `/papers/upload`. |
| **MEDIUM** | Accessibility | Keyboard navigation tab order in `ThreePaneChatWorkbench` should land on chat input immediately after conversation switch. | Add focus ref trigger in `useEffect` when switching `conversationId`. |
| **LOW** | Visual Polish | On 1366px screens, the breadcrumb trail in Paper Details can occasionally wrap if the paper title exceeds 70 characters. | Apply CSS `truncate max-w-md` to paper detail header title. |

---

## 6. Storage Isolation Certification

This certifies that:
1. The persistent developer storage directory `.chroma/` and SQLite database `.chroma/researchlens_lexical.sqlite3` have **NOT** been modified, deleted, migrated, or pointed to during this QA setup.
2. The developer PostgreSQL database `researchassistant` was not targeted; all migrations and QA operations were executed strictly against the dedicated `researchlens_qa` database.
3. The QA environment is self-contained, repeatable, and safe for comprehensive manual testing.

**Overall Certification:** ✅ **QA ENVIRONMENT READY**


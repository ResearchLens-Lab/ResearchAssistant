# ResearchLens — Localhost End-to-End QA Checklist

**Document Version:** 1.0.0  
**Testing Modality:** Manual Real-User Validation  
**Target Hosts:** `http://localhost:3000` (Frontend), `http://127.0.0.1:8000` (Backend)  
**QA Workspace:** `.researchlens-qa/` (Postgres DB: `researchlens_qa`)  

---

## Instructions for Tester

Execute the test suites in sequential order. Do not skip suites, as subsequent steps depend on documents and projects created in earlier steps. Record pass/fail status and observations in each section.

---

## Test Suite 1: Authentication & Session Lifecycle

### Test 1.1: New User Registration
- **URL:** `http://localhost:3000/register`
- **Actions:**
  1. Fill in Full Name: `QA Researcher Alpha`
  2. Fill in Username: `qatester01`
  3. Fill in Email: `qatester01@example.com`
  4. Fill in Password: `ResearchLens!2026`
  5. Click **"Create Account"**
- **Expected Result:**
  - Form validates successfully (no regex or complexity errors).
  - Backend creates user in `researchlens_qa.users` table with hashed password.
  - Redirects automatically to `/papers` (Research Library).
  - Top-right avatar shows initials **"QA"**.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 1.2: Session Persistence Across Page Refreshes
- **URL:** `http://localhost:3000/papers`
- **Actions:**
  1. Refresh browser window (`F5` or `Ctrl + R`).
- **Expected Result:**
  - User remains logged in without being kicked to `/login`.
  - JWT access token in `localStorage` or `HttpOnly` cookie is retained.
  - User profile persists in the top navigation bar.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 1.3: User Logout & Route Guard Enforcement
- **URL:** `http://localhost:3000/papers`
- **Actions:**
  1. Click top-right user avatar (`QA`).
  2. Select **"Sign Out"**.
  3. Observe redirection to `/login`.
  4. Attempt to navigate directly to `http://localhost:3000/papers` in address bar.
- **Expected Result:**
  - Token is cleared from storage.
  - User is immediately redirected back to `/login` by `AuthGuard`.
  - Protected pages cannot be accessed unauthenticated.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 1.4: Existing User Login
- **URL:** `http://localhost:3000/login`
- **Actions:**
  1. Enter Email: `qatester01@example.com`
  2. Enter Password: `ResearchLens!2026`
  3. Click **"Sign In"**
- **Expected Result:**
  - Login succeeds with HTTP 200 from `/api/v1/auth/token`.
  - Redirects to `/papers`.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 2: Research Library & Project Management

### Test 2.1: Library Empty State Verification
- **URL:** `http://localhost:3000/papers`
- **Actions:**
  1. Inspect the initial view of the library for a fresh user.
- **Expected Result:**
  - "Start with a Research Project" placeholder banner is displayed.
  - 3-step onboarding instructions are visible:
    1. Create a Research Project
    2. Add supported documents and wait for indexing
    3. Ask a question and inspect its evidence
  - A prominent "Create project" call-to-action button is visible.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 2.2: Create Research Projects
- **URL:** `http://localhost:3000/papers`
- **Actions:**
  1. Click **"Create project"**.
  2. In the modal, enter:
     - **Title:** `Quantum Cryptography Protocols`
     - **Authors:** `Dr. Elena Vance, Prof. Marcus Chen`
     - **Venue:** `IEEE Transactions on Quantum Engineering`
     - **Year:** `2025`
     - **Abstract:** `Experimental evaluation of decoy-state BB84 against E91 entanglement protocols.`
  3. Click **"Save Project"**.
  4. Repeat process for Project 2:
     - **Title:** `Graph Traversal & Routing Analysis`
     - **Authors:** `Dr. Sophia Ramirez, Liam Patel`
     - **Venue:** `Journal of Graph Algorithms and Applications`
     - **Year:** `2024`
     - **Abstract:** `Empirical latency and memory benchmarks for Fibonacci-heap Dijkstra algorithms.`
- **Expected Result:**
  - Both projects appear in the library grid with status badges.
  - Total projects badge updates to `2 projects`.
  - Card menus allow viewing, editing, or deleting.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 2.3: View Mode Switching & Search Filtering
- **URL:** `http://localhost:3000/papers`
- **Actions:**
  1. Click the Table view button (icon with list lines).
  2. Verify projects render in tabular rows with columns: Title, Authors, Venue, Sources, and Actions.
  3. Switch back to Grid view.
  4. In the filter box, type `Quantum`.
- **Expected Result:**
  - Table and Grid switch smoothly without re-fetching or flashing errors.
  - Search filter immediately restricts the view to only `Quantum Cryptography Protocols`.
  - Clearing the search input restores both projects.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 3: Document Ingestion & Safe Indexing

### Test 3.1: Upload Document to Project 1
- **URL:** `http://localhost:3000/papers/upload` (or via Project Card -> Add Sources)
- **Actions:**
  1. Select Project: `Quantum Cryptography Protocols`.
  2. Drag and drop `.researchlens-qa/fixtures/paper_alpha_quantum.pdf` into the upload zone.
  3. Click **"Upload & Process"**.
- **Expected Result:**
  - File is uploaded via multipart POST to `/api/v1/papers/{id}/documents`.
  - File is saved into `.researchlens-qa/uploads/`.
  - Processing badge transitions: `uploaded` ➔ `processing` ➔ `indexed`.
  - Status polling updates automatically without full page reload.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 3.2: Upload Document to Project 2
- **URL:** `http://localhost:3000/papers/upload`
- **Actions:**
  1. Select Project: `Graph Traversal & Routing Analysis`.
  2. Upload `.researchlens-qa/fixtures/paper_beta_algorithms.pdf`.
  3. Wait for status to transition to `indexed`.
- **Expected Result:**
  - File saved into `.researchlens-qa/uploads/`.
  - Chunks created and indexed into `.researchlens-qa/chroma/researchlens_lexical.sqlite3` with `owner_id` set to User 1's ID.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 4: Paper Details & Evidence Inspection

### Test 4.1: Inspect Paper Details Screen
- **URL:** `http://localhost:3000/papers` ➔ Click `Quantum Cryptography Protocols`
- **Actions:**
  1. Verify the layout of `/papers/[id]`:
     - Paper Metadata Header (Title, Authors, Abstract, Venue).
     - Action buttons: "Ask in Research Desk", "Add sources", "View Evidence Trail".
     - Source Verification Card showing verification status.
     - Document Attachments List showing `paper_alpha_quantum.pdf` with green `indexed` badge.
- **Expected Result:**
  - All metadata renders accurately without missing field warnings.
  - Document attachment shows file size, pages, and download/preview capability.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 5: Research Desk (Grounded Q&A & Evidence Trail)

### Test 5.1: Grounded Single-Paper Question Answering
- **URL:** `http://localhost:3000/chat`
- **Actions:**
  1. Ensure Paper Scope in the top or side rail has `Quantum Cryptography Protocols` selected.
  2. In the chat input, type:
     > *"What is the quantum bit error rate threshold and key rate reported for decoy-state BB84?"*
  3. Submit query.
- **Expected Result:**
  - Response streams or renders with verifiable facts directly from `paper_alpha_quantum.pdf`:
    - Secure key rate of **14.8 kbps over 50 km**.
    - Quantum bit error rate (QBER) threshold of **4.5%**.
    - Cutoff bound of **11.0% QBER**.
  - Interactive citation badge (e.g., `[1]`) is displayed next to the claim.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 5.2: Evidence Drawer Inspection
- **URL:** `http://localhost:3000/chat`
- **Actions:**
  1. Click the citation badge `[1]` in the assistant's answer.
- **Expected Result:**
  - The right-hand **Source Inspector Rail** drawer slides open.
  - Displays the exact matching snippet from `paper_alpha_quantum.pdf`.
  - Highlights the metadata: Page 1/2, Section 3 (*Empirical Key Rate Performance*), and document filename.
  - Drawer can be dismissed smoothly via close button or backdrop click.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 5.3: Ungrounded Fallback & Honest Refusal
- **URL:** `http://localhost:3000/chat`
- **Actions:**
  1. In the same scoped conversation, ask an ungrounded question:
     > *"What was the query latency of Dijkstra's algorithm with Fibonacci heaps in this paper?"*
- **Expected Result:**
  - The assistant refuses to invent facts or hallucinates information not present in `paper_alpha_quantum.pdf`.
  - It clearly states that the scoped quantum paper does not report Dijkstra algorithm benchmark results.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 6: Paper Executive Summary

### Test 6.1: Grounded Paper Summary Generation
- **URL:** `http://localhost:3000/papers/[quantum_id]`
- **Actions:**
  1. Scroll to the **Grounded Summary Card**.
  2. Click **"Generate Summary"** (or inspect pre-generated summary if present).
- **Expected Result:**
  - Generates a structured multi-paragraph summary:
    - Objective and methodology (Decoy-state BB84 vs E91).
    - Key findings (14.8 kbps key rate, 28 dB loss cutoff).
    - Security bounds (4.5% operational QBER, 11% theoretical maximum).
  - Contains clickable citation pills linking back to document evidence chunks.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 7: Multi-Paper Comparison Studio

### Test 7.1: Cross-Paper Comparative Synthesis
- **URL:** `http://localhost:3000/compare`
- **Actions:**
  1. In the paper selector rail, check both:
     - `[x] Quantum Cryptography Protocols`
     - `[x] Graph Traversal & Routing Analysis`
  2. Select preset: *"Compare objectives, methods, results, and limitations where the selected sources report them."*
  3. Click **"Run Comparison"**.
- **Expected Result:**
  - Comparison Synthesis Card generates structured analysis contrasting both papers.
  - Correctly attributes findings to each distinct paper:
    - Quantum paper: Focuses on physical-layer key exchange, QBER thresholds, fiber loss.
    - Graph paper: Focuses on algorithmic computational complexity, Dijkstra latency (92.4 ms), heap memory.
  - Multi-paper citations link to respective source papers in the Evidence Drawer.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 8: Persistence Across Application Restarts

### Test 8.1: Full Restart Verification
- **Actions:**
  1. Stop both backend and frontend processes (`Ctrl + C` in both PowerShell windows).
  2. Restart the backend using the QA startup command.
  3. Restart the frontend using `npm run dev`.
  4. Reload `http://localhost:3000` in the browser.
- **Expected Result:**
  - User session remains active (or logs back in seamlessly).
  - Both research projects are still in the Library.
  - Uploaded PDF documents remain in `indexed` status.
  - Past conversations and messages in Research Desk are completely preserved.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Test Suite 9: Cross-User Security & Isolation (SEC-001 Verification)

### Test 9.1: Register User 2 (Beta)
- **URL:** Open a **New Incognito / Private Window** ➔ `http://localhost:3000/register`
- **Actions:**
  1. Fill in Full Name: `QA Researcher Beta`
  2. Fill in Username: `qatester02`
  3. Fill in Email: `qatester02@example.com`
  4. Fill in Password: `ResearchLens!2026`
  5. Click **"Create Account"**.
- **Expected Result:**
  - User 2 is created and logged in.
  - Library displays **0 projects** (completely blank).
  - None of User 1's projects (`Quantum Cryptography Protocols`, `Graph Traversal`) appear in User 2's library.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 9.2: Direct URL Access Protection
- **URL:** In User 2's browser window, paste the direct URL to User 1's project:  
  `http://localhost:3000/papers/<USER_1_PAPER_ID>`
- **Actions:**
  1. Press Enter to load the page.
- **Expected Result:**
  - Page renders an error state: *"Paper not found"* or *"You may not have permission to view this paper."*
  - Backend returns HTTP 404/403.
  - User 1's paper title, abstract, and documents are NOT leaked to User 2.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

### Test 9.3: RAG & FTS5 Lexical Retrieval Cross-User Leakage Test
- **URL:** In User 2's browser window, navigate to `http://localhost:3000/chat`
- **Actions:**
  1. Ask: *"What is the quantum bit error rate threshold for decoy-state BB84?"*
- **Expected Result:**
  - User 2 has not indexed any papers.
  - The system does NOT retrieve User 1's indexed chunks from ChromaDB or SQLite FTS5.
  - Assistant responds that no research sources are available/indexed to answer the query.
  - Strict SEC-001 isolation is verified across both vector and lexical retrieval engines.
- [ ] **Pass / Fail:** ____________________
- **Notes:** ______________________________

---

## Summary of QA Execution

- **Total Test Cases:** 20
- **Passed:** _____
- **Failed:** _____
- **Tester Signature:** ____________________  
- **Date Completed:** ____________________  


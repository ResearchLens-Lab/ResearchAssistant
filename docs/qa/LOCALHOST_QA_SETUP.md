# ResearchLens — Localhost QA Environment Setup Guide

**Document Version:** 1.0.0  
**Status:** Certified Active & Ready  
**Date:** 2026-11-12  
**Target Environment:** Localhost (Windows 11 / PowerShell)  
**Security Boundary:** SEC-001 Isolated Sandbox  

---

## 1. Overview & Architectural Isolation

To validate ResearchLens following the SEC-001 owner-propagation and security hardening initiative without risking existing research data, an isolated sandbox environment has been provisioned under `.researchlens-qa/`.

### Strict Storage Boundaries

| Component | Persistent Developer Storage (Untouched) | Isolated QA Environment |
| :--- | :--- | :--- |
| **Relational Database** | PostgreSQL `researchassistant` | PostgreSQL `researchlens_qa` |
| **Alembic Revisions** | Migration chain through `a8c7d9e2f104` | 28 tables fully applied to `researchlens_qa` |
| **Vector Storage** | `.chroma/` (6,523 vectors) | `.researchlens-qa/chroma/` (fresh) |
| **Lexical SQLite FTS5** | `.chroma/researchlens_lexical.sqlite3` (6,818 rows, legacy 11 cols) | `.researchlens-qa/chroma/researchlens_lexical.sqlite3` (fresh 12 cols with `owner_id`) |
| **Document Uploads** | `uploads/` or `.uploads/` | `.researchlens-qa/uploads/` |
| **Configuration File** | `backend/.env.local` | `.researchlens-qa/.env.qa` |

> [!IMPORTANT]
> At no point does the QA environment read from or write to `.chroma/` or the developer database `researchassistant`. Developer research data remains 100% untouched.

---

## 2. Environment Configuration

The QA configuration is defined in `.researchlens-qa/.env.qa`:

```ini
# Isolated QA Environment Configuration for ResearchLens
APP_NAME=ResearchLens QA
APP_ENV=testing
DATABASE_URL=postgresql+asyncpg://postgres:Radhe%40123@127.0.0.1:5432/researchlens_qa
UPLOAD_DIR=.researchlens-qa/uploads
CHROMA_PERSIST_DIR=.researchlens-qa/chroma
FASTEMBED_CACHE_DIR=.model_cache
RAG_MODE=local
RAG_ANSWER_MODE=LOCAL_QWEN
RETRIEVAL_MODE=hybrid
LLM_PROVIDER=local
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:0.8b
CORS_ORIGINS=http://localhost:3000
JWT_SECRET_KEY=qa-secret-key-researchlens-testing-only
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## 3. Step-by-Step Launch Instructions

### Prerequisites
- PostgreSQL running locally on port `5432` with database `researchlens_qa` provisioned.
- Python virtual environment `.venv_stabilization` activated.
- Node.js (`v26.x`) and npm (`11.x`) installed.

---

### Step A: Start the Backend (Port 8000)

Open a new PowerShell terminal and run:

```powershell
# 1. Navigate to project root
cd "C:\Users\gorav\OneDrive\Desktop\college project\ResearchAssistant"

# 2. Activate Python virtual environment
.\.venv_stabilization\Scripts\Activate.ps1

# 3. Export QA Environment Variables
$env:APP_NAME = "ResearchLens QA"
$env:APP_ENV = "testing"
$env:DATABASE_URL = "postgresql+asyncpg://postgres:Radhe%40123@127.0.0.1:5432/researchlens_qa"
$env:UPLOAD_DIR = ".researchlens-qa/uploads"
$env:CHROMA_PERSIST_DIR = ".researchlens-qa/chroma"
$env:JWT_SECRET_KEY = "qa-secret-key-researchlens-testing-only"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:RAG_MODE = "local"
$env:RAG_ANSWER_MODE = "LOCAL_QWEN"

# 4. Launch FastAPI server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### Step B: Start the Frontend (Port 3000)

Open a second PowerShell terminal and run:

```powershell
# 1. Navigate to frontend directory
cd "C:\Users\gorav\OneDrive\Desktop\college project\ResearchAssistant\frontend"

# 2. Ensure API URL points to local backend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"

# 3. Launch Next.js development server
npm run dev
```

The frontend will be available at:  
👉 **`http://localhost:3000`**

---

## 4. Health & Verification Probes

Before beginning manual UI testing, verify backend health using PowerShell:

```powershell
# Check Liveness
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get
# Expected output: @{status="ok"; app="ResearchLens QA"; environment="testing"}

# Check Readiness (Database connectivity)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -Method Get
# Expected output: @{status="ready"; checks=@{database="ok"}}

# Check Local AI Engine Status
Invoke-RestMethod -Uri "http://127.0.0.1:8000/system/model" -Method Get
# Expected output: @{provider="local"; state="ready_not_loaded" or "ready_loaded"; model="qwen3.5:0.8b"}
```

---

## 5. QA Test Fixtures & Pre-configured Accounts

### Pre-configured QA Accounts

| User | Email | Password | Role | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **User 1 (Alpha)** | `qatester01@example.com` | `ResearchLens!2026` | Primary Researcher | Document upload, single-paper Q&A, summary, comparison |
| **User 2 (Beta)** | `qatester02@example.com` | `ResearchLens!2026` | Isolated Secondary Researcher | Cross-user isolation verification (cannot view User 1's papers or chunks) |

> [!NOTE]
> Passwords meet backend security complexity rules (minimum 12 characters, uppercase, lowercase, numeric, and special character). User 1 is pre-registered; User 2 can be registered via the `/register` UI to validate the registration flow.

### Prepared PDF Test Fixtures

Two structured academic papers have been created in `.researchlens-qa/fixtures/`:

1. **`paper_alpha_quantum.pdf`**
   - **Title:** *Quantum Key Distribution Protocols: Security Proofs and Practical Decoy-State Bounds*
   - **Authors:** Dr. Elena Vance, Prof. Marcus Chen
   - **Key Verifiable Facts:** Decoy-state BB84 achieves 14.8 kbps key rate over 50 km; QBER threshold is 4.5%; maximum channel loss tolerance is 28 dB; cutoff QBER is 11.0%.
   - **Use Case:** Single-paper grounded Q&A, summary claims verification, evidence drawer inspection.

2. **`paper_beta_algorithms.pdf`**
   - **Title:** *Comparative Asymptotic Efficiency of Graph Traversal and Shortest Path Algorithms*
   - **Authors:** Dr. Sophia Ramirez, Liam Patel
   - **Key Verifiable Facts:** Fibonacci-heap Dijkstra achieves 92.4 ms query latency on a 100,000-node graph (1.2M edges); 3.68x speedup over binary-heap Dijkstra; 18.5 MB peak memory overhead.
   - **Use Case:** Cross-paper comparative analysis in `/compare`, ungrounded fallback testing when queried against Paper 1.

---

## 6. Shutdown & Teardown Instructions

### Graceful Shutdown
In each PowerShell terminal, press `Ctrl + C` and confirm termination (`Y`).

### Resetting QA Data (Without Touching Production Data)
If you wish to reset the QA database and storage back to a pristine state:

```powershell
# 1. Clear QA Chroma & SQLite FTS5 database
Remove-Item -Path ".researchlens-qa\chroma\*" -Recurse -Force

# 2. Clear QA uploaded files
Remove-Item -Path ".researchlens-qa\uploads\*" -Recurse -Force

# 3. (Optional) Truncate QA PostgreSQL tables
& .\.venv_stabilization\Scripts\python.exe -c "
import asyncio, asyncpg
async def reset():
    conn = await asyncpg.connect(user='postgres', password='Radhe@123', database='researchlens_qa', host='127.0.0.1', port=5432)
    await conn.execute('TRUNCATE TABLE messages, conversations, documents, papers, users CASCADE;')
    await conn.close()
    print('QA Database truncated successfully.')
asyncio.run(reset())
"
```


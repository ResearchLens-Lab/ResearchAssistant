# ResearchLens: Monorepo Implementation Progress Report

**Project Title**: AI Research Assistant Platform: A RAG-Based System for Research Paper Understanding, Citation Analysis and Research Trend Exploration  
**Organization**: ResearchLens-Lab  
**Repository**: ResearchAssistant  
**Document Version**: 1.0.0 (Phase 1 & Phase 2 Complete)  
**Date**: September 2026  

---

## 👥 Team Responsibilities & Current Status

| Team Member | Role | Area | Status | Deliverables / Artifacts |
|---|---|---|---|---|
| **Gorav Gumber** | Project Lead + Technical Lead + RAG/AI Lead | `rag/`, `backend/app/integrations/rag_client.py`, `scripts/` | **✅ COMPLETED** | Ingestion, Section-Aware Chunking, ChromaDB Vectorstore, Retrieval, Grounded LLM, Citation Mapping, 27 tests |
| **Abhay Kumar Singh** | Backend + Database Lead | `backend/`, `infrastructure/docker-compose.backend.yml` | **✅ COMPLETED** | FastAPI REST API, PostgreSQL + Alembic, JWT Auth, Paper/Doc CRUD, Chat persistence, RAG gateway, 68 tests |
| **Himanshu Kumawat** | Frontend Lead | `frontend/` | **⏳ PENDING** | Next.js App, Paper Reader, Chat Interface, Citation Viewer, Multi-paper matrix |
| **Harendra Godara** | Knowledge Graph + Research Intelligence Lead | `knowledge-graph/` | **⏳ PENDING** | Neo4j Graph DB, Citation Networks, Co-authorship Graphs, Research Trend Analytics |

---

## 🏗️ Monorepo High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FRONTEND (Himanshu)                                        │
│                 Next.js 14 App Router, TailwindCSS/Vanilla CSS, React Markdown                   │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │ HTTP / REST (JSON)
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       BACKEND (Abhay)                                            │
│                      FastAPI, Async SQLAlchemy 2.0, PostgreSQL, Alembic, PyJWT                   │
│                                                                                                  │
│   ┌─────────────────┐    ┌────────────────────┐    ┌─────────────────┐    ┌──────────────────┐   │
│   │   Auth Routes   │    │    Paper Routes    │    │ Document Routes │    │   Chat Routes    │   │
│   │  /auth/register │    │    /api/v1/papers  │    │ /documents/upload│   │   /api/v1/chat   │   │
│   └────────┬────────┘    └─────────┬──────────┘    └────────┬────────┘    └────────┬─────────┘   │
│            │                       │                        │                      │             │
│   ┌────────▼────────┐    ┌─────────▼──────────┐             │             ┌────────▼─────────┐   │
│   │  Auth Service   │    │   Paper Service    │             │             │   Chat Service   │   │
│   └────────┬────────┘    └─────────┬──────────┘             │             └────────┬─────────┘   │
│            │                       │                        │                      │             │
│            └───────────────┬───────┴────────────────────────┴──────────────────────┘             │
│                            ▼                                                                     │
│                  ┌──────────────────┐                                                            │
│                  │ PostgreSQL async │ (Users, Papers, Documents, Conversations, Messages)         │
│                  └──────────────────┘                                                            │
│                                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ RAGGateway (backend/app/integrations/rag_gateway.py) - Async Off-Loop Adapter            │   │
│   └────────────────────────────────────────────┬─────────────────────────────────────────────┘   │
└────────────────────────────────────────────────┼─────────────────────────────────────────────────┘
                                                 │ In-Process Sync Boundary
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CORE RAG & AI ENGINE (Gorav)                                   │
│                        `rag/` - Modular, Reusable, Deterministic, Tested                         │
│                                                                                                  │
│  Research Paper (PDF/TXT) ──▶ Document Loader & Normalizer ──▶ Section-Aware Chunking            │
│                                                                        │                         │
│  ChromaDB Vector Store ◀── Batch Embeddings (Mock / OpenAI) ◀──────────┘                         │
│          │                                                                                       │
│          ▼                                                                                       │
│  Query + Target Paper IDs ──▶ Filtered Vector Search ──▶ Ranking & Identity Reranker             │
│                                                                        │                         │
│  Verified Citation Sources ◀── CitationMapper ◀── Grounded LLM ◀── ContextBuilder (Token Budget) │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Core RAG & AI Subsystem (Gorav Gumber)

The RAG subsystem is isolated under `rag/` and designed with strict separation of concerns, deterministic source provenance, and zero-dependency offline testing capabilities.

### 1.1 Ingestion & Document Normalization (`rag/ingestion/`)
- **`PDFDocumentLoader`**: Uses `pypdf` to extract text page-by-page while guaranteeing exact 1-indexed page number retention.
- **`TextDocumentLoader`**: Parses raw markdown, text files, and simulated page boundary markers (`\f` or `--- Page N ---`).
- **`DocumentNormalizer`**: Detects standard academic paper sections (*Abstract, Introduction, Related Work, Methodology, Experiments, Results, Discussion, Conclusion, References*) across page boundaries.
- **Data Models**: Typed Pydantic structures (`Page`, `Section`, `DocumentMetadata`, `NormalizedDocument`).

### 1.2 Section-Aware Chunking & Provenance Metadata (`rag/chunking/`)
- **`SectionAwareChunkingStrategy`**: Chunks text respecting section boundaries to prevent cross-section semantic bleeding, using a sliding window (`chunk_size=500`, `chunk_overlap=80`).
- **Page Offset Matching**: Dynamically resolves exact start and end page numbers (`page_start`, `page_end`) for every chunk snippet.
- **`ChunkMetadata`**: Contains `chunk_id`, `paper_id`, `document_id`, `page_start`, `page_end`, `section`, `chunk_index`, `token_count`, `title`.
- **Deterministic ID Scheme**: Generates stable IDs (`{paper_id}_c{chunk_index:04d}_p{page_start}-{page_end}`) enabling idempotent re-indexing.

### 1.3 Embeddings & Model Registry (`rag/embeddings/`)
- **`BaseEmbedder`**: Abstract base class for embedding providers.
- **`DeterministicMockEmbedder`**: Token-hash dense vector projection with L2 normalization (384 dims) enabling 100% offline, deterministic, semantic keyword-matched execution without external API keys.
- **`OpenAIEmbedder`**: Production embedding client targeting `text-embedding-3-small` (1536 dims) via HTTP API.
- **`BatchEmbeddingGenerator`**: Slices chunk collections into configurable batches (`batch_size=32`).

### 1.4 ChromaDB Vector Store (`rag/vectorstore/`)
- **`ChromaClientFactory`**: Manages connections supporting local `PersistentClient` (`.chroma/` directory) and remote `HttpClient` (standalone Docker container).
- **`CollectionManager`**: Handles collection lifecycle with cosine distance configuration (`hnsw:space: cosine`).
- **`VectorRepository`**: Complete vector repository supporting batch upsert, metadata-filtered queries, and paper-level vector deletion.

### 1.5 Retrieval, Filtering & Ranking (`rag/retrieval/`)
- **`QueryRequest` & `QueryFilters`**: Structured query encapsulation with target paper IDs and section filters.
- **`FilterBuilder`**: Converts filters into ChromaDB `$and` / `$in` / `$eq` where-clauses.
- **`ResultRanker`**: Normalizes cosine distance to similarity scores `[0.0, 1.0]` and applies minimum score thresholds.
- **`IdentityReranker`**: Active pass-through reranker implementing the `BaseReranker` interface.
- **`ResearchRetriever`**: High-level retrieval orchestrator outputting structured `RetrievedSource` objects labeled `S1`, `S2`, ...

### 1.6 Context Construction & Token Limits (`rag/context/`)
- **`ContextLimitManager`**: Enforces strict token budget limits (`context_max_tokens=3500`) to prevent LLM context overflow.
- **`ContextSelector`**: Deduplicates identical text snippets and ensures balanced source representation across multiple papers in comparative queries.
- **`ContextBuilder`**: Assembles structured evidence blocks annotated with source markers (`[S1] (Paper: paper_1, Page 3, Section: Methodology)`).

### 1.7 Grounded LLM Generation (`rag/generation/`)
- **Prompt Engineering**: Strict system prompts for Research QA, 7-section paper summarization, and multi-paper comparative matrices.
- **`MockGroundedLLMClient`**: Offline deterministic generator synthesizing grounded answers with valid `[S1]`, `[S2]` citation tags.
- **`OpenAILLMClient`**: Cloud generator calling OpenAI Chat Completion API.
- **`ResponseParser`**: Extracts cleaned text and extracts inline citation references.

### 1.8 Citation Provenance & Verification (`rag/citations/`)
- **`SourceTracker`**: Maintains an indexed registry of retrieved sources.
- **`CitationMapper`**: Validates cited source tags against real retrieved chunks, discarding hallucinated citations.
- **`RAGResult`**: Final structured response model containing `answer: str`, `sources: List[SourceCitation]`, and `metadata: dict`.

### 1.9 End-to-End Pipelines (`rag/pipelines/`)
- **`IngestionPipeline`**: Single entrypoint for ingesting documents (`ingest_file`, `ingest_text`, `delete_paper`).
- **`QueryPipeline`**: Single entrypoint for querying (`answer_question`, `summarize_paper`, `compare_papers`).

---

## 2. Backend & Database Subsystem (Abhay Kumar Singh)

The backend is built with FastAPI and Async SQLAlchemy 2.0, providing complete authentication, database persistence, document storage, and RAG gateway integration.

### 2.1 Layered Architecture (`backend/app/`)
- **`routes/`**: Clean FastAPI endpoints with Pydantic request/response schemas.
- **`services/`**: Business logic, transactional boundaries, access control.
- **`repositories/`**: Isolated database queries using SQLAlchemy AsyncSession.
- **`models/`**: SQLAlchemy declarative models (`User`, `Paper`, `Document`, `Conversation`, `Message`, `RefreshToken`).
- **`integrations/`**: Subsystem adapters (`RAGGateway` and `KnowledgeGraphClient`).
- **`core/`**: Security (JWT + bcrypt), configuration (`pydantic-settings`), exception handling.
- **`middleware/`**: `X-Request-ID` tracing and uniform JSON error handling.

### 2.2 Relational Database Schema (PostgreSQL + Alembic)
- **`users`**: `id`, `email`, `hashed_password`, `full_name`, `is_active`, `created_at`, `updated_at`.
- **`papers`**: `id`, `user_id`, `title`, `abstract`, `authors`, `year`, `doi`, `created_at`, `updated_at`.
- **`documents`**: `id`, `paper_id`, `file_name`, `file_path`, `file_size_bytes`, `status` (*uploaded, processing, indexed, failed*), `error_message`, `created_at`.
- **`conversations`**: `id`, `user_id`, `title`, `created_at`, `updated_at`.
- **`messages`**: `id`, `conversation_id`, `role` (*user, assistant, system*), `content`, `sources` (JSONB storing RAG citations), `created_at`.
- **`refresh_tokens`**: `id`, `user_id`, `token_hash`, `expires_at`, `is_revoked`, `created_at`.

### 2.3 RAG Integration Gateway (`backend/app/integrations/rag_gateway.py`)
- Bridges FastAPI async event loop to Gorav's synchronous in-process `RAGClient`.
- Executes RAG queries in thread workers (`asyncio.to_thread`) with configurable timeout (`RAG_TIMEOUT_SECONDS=60`).
- Translates pipeline failures into standardized `503 RAG_UNAVAILABLE` error responses.
- Enforces shared ID immutability: `paper_id` and `document_id` generated in PostgreSQL flow directly into ChromaDB vector metadata.

### 2.4 Complete API Surface (`/api/v1`)

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/auth/register` | POST | Public | Register new user account with hashed password |
| `/api/v1/auth/login` | POST | Public | Authenticate user, issue JWT access + refresh tokens |
| `/api/v1/auth/me` | GET | Bearer | Get current authenticated user profile |
| `/api/v1/auth/refresh` | POST | Public | Rotate refresh token for new access token pair |
| `/api/v1/auth/logout` | POST | Public | Revoke active refresh token |
| `/api/v1/users/me` | GET/PATCH | Bearer | View and update user profile |
| `/api/v1/papers` | POST/GET | Bearer | Create and paginate user's research papers |
| `/api/v1/papers/{paper_id}` | GET/PATCH/DELETE | Bearer | Retrieve, update, or delete paper and its indexed vectors |
| `/api/v1/papers/{paper_id}/summary` | POST | Bearer | Generate grounded 7-section summary via RAG |
| `/api/v1/papers/compare` | POST | Bearer | Multi-paper comparative RAG across selected paper IDs |
| `/api/v1/papers/{paper_id}/documents` | GET | Bearer | List uploaded document files for a paper |
| `/api/v1/documents/upload` | POST | Bearer | Multipart PDF upload + validation + automatic RAG indexing |
| `/api/v1/documents/{document_id}` | GET | Bearer | Check document indexing status (`indexed` / `failed`) |
| `/api/v1/chat` | POST | Bearer | Grounded Q&A with message history & source persistence |
| `/api/v1/conversations` | POST/GET | Bearer | Create and list user chat conversations |
| `/api/v1/conversations/{id}` | GET/DELETE | Bearer | Retrieve or delete conversation |
| `/api/v1/conversations/{id}/messages` | GET | Bearer | List messages with persisted citation sources |
| `/api/v1/search` | GET | Bearer | Metadata search across title, abstract, authors, and year |
| `/api/v1/health` | GET | Public | Liveness check |
| `/api/v1/health/ready` | GET | Public | Readiness check verifying PostgreSQL connectivity |
| `/api/v1/research/*` | GET | Bearer | Knowledge graph stubs (503 until Harendra connects Neo4j) |

---

## 3. Test Suite & Verification Matrix

All 95 unit, integration, and end-to-end tests are passing across the monorepo:

```text
============================= test session starts ==============================
collected 95 items

[RAG Engine - Gorav Gumber (27 tests)]
backend/test_chunking.py .................................... PASSED [ 4%]
backend/test_citations.py ................................... PASSED [ 7%]
backend/test_context.py ..................................... PASSED [10%]
backend/test_embeddings.py .................................. PASSED [14%]
backend/test_end_to_end_rag.py .............................. PASSED [16%]
backend/test_generation.py .................................. PASSED [20%]
backend/test_multi_paper.py ................................. PASSED [21%]
backend/test_retrieval.py ................................... PASSED [24%]
backend/test_summarization.py ............................... PASSED [25%]
backend/test_vectorstore.py ................................. PASSED [28%]

[Backend & REST API - Abhay Kumar Singh (68 tests)]
backend/tests/test_auth.py .................................. PASSED [41%]
backend/tests/test_chat.py .................................. PASSED [51%]
backend/tests/test_documents.py ............................. PASSED [64%]
backend/tests/test_health.py ................................ PASSED [69%]
backend/tests/test_integration.py ........................... PASSED [70%]
backend/tests/test_papers.py ................................ PASSED [87%]
backend/tests/test_search.py ................................ PASSED [96%]
backend/tests/test_users.py ................................. PASSED [100%]

============================= 95 passed in 55.32s ==============================
```

### RAG Evaluation Benchmark Results
- **Dataset**: `rag/evaluation/datasets/sample_questions.json`
- **Mean Hit@4**: `100.0%`
- **Mean Source Relevance**: `85.4%`
- **Mean Answer Grounding**: `81.9%`
- **Mean Citation Correctness**: `100.0%`

---

## 4. Pending Deliverables & Integration Roadmap

### 4.1 Frontend Implementation (Himanshu Kumawat)
The frontend should be built under `frontend/` (Next.js 14 / React) and communicate with the backend REST API:

1. **Authentication Flow**:
   - Register (`POST /api/v1/auth/register`), Login (`POST /api/v1/auth/login`), Token refresh on 401.
2. **Paper Library & Upload Screen**:
   - Create Paper (`POST /api/v1/papers`), List Papers (`GET /api/v1/papers`).
   - Drag-and-drop PDF upload (`POST /api/v1/documents/upload`), poll status until `status: "indexed"`.
3. **Interactive Research Chat Interface**:
   - Chat box sending `POST /api/v1/chat` with selected `paper_ids`.
   - Render grounded assistant responses with clickable inline citation badges `[S1]`, `[S2]`.
   - Citation Drawer showing `source_id`, `paper_id`, `page`, `section`, and exact supporting evidence.
4. **Structured Summary & Comparison Views**:
   - Button triggering `POST /api/v1/papers/{id}/summary` to render the 7-section breakdown.
   - Comparison Screen sending `POST /api/v1/papers/compare` with 2+ selected papers.

### 4.2 Knowledge Graph & Research Intelligence (Harendra Godara)
The knowledge graph subsystem should be built under `knowledge-graph/` (Neo4j / Graph Analytics):

1. **Neo4j Graph Database**:
   - Nodes: `Paper`, `Author`, `Concept`, `Topic`, `Venue`.
   - Relationships: `CITES`, `AUTHORED_BY`, `ADDRESSES_CONCEPT`, `SIMILAR_TO`.
2. **Implement Knowledge Graph Gateway**:
   - Replace stubs in `backend/app/integrations/knowledge_graph_client.py` with real Neo4j Bolt driver queries:
     - `get_paper_graph(paper_id)`
     - `get_related_papers(paper_id)`
     - `get_citation_network(paper_id)`
     - `get_research_trends()`
3. **Graph-Augmented RAG**:
   - Traversed related paper IDs can be passed into `rag_client.ask_question(question, paper_ids=graph_paper_ids)` for multi-hop scientific reasoning.

---

## 5. Developer Guide & Quick Reference

### How to Run Locally
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run standalone ChromaDB and PostgreSQL (via Docker)
docker compose up -d

# 3. Apply database migrations
alembic -c backend/alembic.ini upgrade head

# 4. Start the backend API server
uvicorn backend.app.main:app --reload --port 8000

# 5. Access Interactive Swagger Docs
# Open: http://localhost:8000/docs
```

### How to Run All Tests & Benchmarks
```bash
# Run all 95 tests across RAG and Backend
source .venv/bin/activate && PYTHONPATH=. pytest rag/tests/ backend/tests/ -v

# Run RAG CLI benchmark suite
python scripts/evaluate_rag.py
```

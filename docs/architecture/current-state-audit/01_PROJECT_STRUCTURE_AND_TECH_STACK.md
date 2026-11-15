# Project Structure and Technology Stack

**Document Version**: 1.0  
**Last Updated**: November 8, 2026

---

## Table of Contents

1. [Root Directory Structure](#root-directory-structure)
2. [Technology Stack Inventory](#technology-stack-inventory)
3. [Backend Architecture](#backend-architecture)
4. [Frontend Architecture](#frontend-architecture)
5. [RAG Module Architecture](#rag-module-architecture)
6. [Knowledge Graph Module](#knowledge-graph-module)
7. [Infrastructure & Configuration](#infrastructure--configuration)
8. [Important Files Reference](#important-files-reference)

---

## Root Directory Structure

```
ResearchAssistant/
├── .chroma/                    # ChromaDB persistent vector store
├── .claude/                    # Neon AI skills (Claude integration artifacts)
├── .git/                       # Git repository
├── .github/workflows/          # CI/CD workflows
├── .model_cache/               # FastEmbed model downloads
├── .pytest_cache/              # Pytest cache
├── .venv/                      # Python virtual environment
├── backend/                    # FastAPI backend application
├── docs/                       # Documentation
├── frontend/                   # Next.js frontend application
├── infrastructure/             # Deployment configurations
├── knowledge-graph/            # Knowledge graph module (PLACEHOLDER)
├── rag/                        # Core RAG engine
├── scripts/                    # Utility scripts
├── storage/                    # Uploaded document storage
├── requirements.txt            # Root Python dependencies
├── package.json                # Root npm workspace configuration
├── docker-compose.yml          # Docker services definition
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project overview
├── .env                        # Environment variables (not in repo)
├── .env.example                # Environment template
└── [Multiple *_REPORT.md files] # Implementation and validation reports
```

**Evidence**: Verified via `list_directory` tool, session start snapshot

---

## Technology Stack Inventory

### A. Frontend Technologies

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Framework** | Next.js | 15.5.28 | React framework with App Router |
| **Runtime** | React | 18.3.1 | UI library |
| **Language** | TypeScript | 5.7.3 | Type-safe JavaScript |
| **Routing** | Next.js App Router | 15.x | File-based routing in `src/app/` |
| **State Management** | Zustand | 5.0.0 | Lightweight global state |
| **Data Fetching** | TanStack Query | 5.59.16 | Server state management |
| **UI Components** | Radix UI | 1.x | Accessible headless components |
| **Styling** | Tailwind CSS | 3.4.14 | Utility-first CSS |
| **Typography** | @tailwindcss/typography | 0.5.15 | Prose styling |
| **Icons** | Lucide React | 0.453.0 | Icon library |
| **Markdown** | react-markdown | 9.0.1 | Markdown rendering |
| **Math Rendering** | KaTeX | 0.19.0 | LaTeX math rendering |
| **Build Tool** | Next.js compiler | Built-in | Webpack/Turbopack |

**Evidence**: `frontend/package.json` (lines 9-34)

**Component Architecture**:
- **Radix UI Components**: Checkbox, Collapsible, Dialog, Dropdown Menu, Hover Card, Popover, Scroll Area, Select, Slider, Switch, Tabs, Tooltip
- **Layout**: App Router with `(auth)` and `(workbench)` route groups
- **Styling Pattern**: Tailwind CSS with `class-variance-authority` for component variants

---

### B. Backend Technologies

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Framework** | FastAPI | 0.111.0+ | Async REST API |
| **Server** | Uvicorn | 0.30.0+ | ASGI server with standard extras |
| **Language** | Python | 3.10+ | Backend runtime |
| **ORM** | SQLAlchemy | 2.0.30+ | Async database ORM |
| **Database Driver** | AsyncPG | 0.29.0+ | PostgreSQL async driver |
| **Migrations** | Alembic | 1.13.0+ | Database schema migrations |
| **Validation** | Pydantic | 2.7.0+ | Data validation & serialization |
| **Settings** | pydantic-settings | 2.2.0+ | Configuration management |
| **Authentication** | PyJWT | 2.8.0+ | JWT token generation/validation |
| **Password Hashing** | bcrypt | 4.1.0+ | Secure password storage |
| **File Upload** | python-multipart | 0.0.9+ | Multipart form parsing |
| **Testing** | pytest | 8.0.0+ | Test framework |
| **Async Testing** | pytest-asyncio | 0.23.0+ | Async test support |
| **HTTP Client** | httpx | 0.27.0+ | Async HTTP for tests |
| **SQLite Testing** | aiosqlite | 0.20.0+ | In-memory test database |

**Evidence**: `backend/requirements.txt`, `backend/app/main.py`

**API Architecture**:
- RESTful design with `/api/v1` versioning
- Async/await throughout
- Dependency injection for database sessions, auth, RAG client
- Middleware: CORS, GZip, Request ID, Error Handling

---

### C. Database & Persistence

| Technology | Purpose | Storage Location | Configuration |
|-----------|---------|------------------|---------------|
| **PostgreSQL** | Primary relational database | External service | `DATABASE_URL` in .env |
| **SQLAlchemy** | ORM and query builder | N/A | Async engine with AsyncPG |
| **Alembic** | Schema migrations | `backend/migrations/versions/` | `backend/alembic.ini` |
| **ChromaDB** | Vector store | `.chroma/` | Persistent local storage |
| **SQLite FTS5** | Lexical search (via ChromaDB) | `.chroma/researchlens_lexical.sqlite3` | Managed by ChromaDB |
| **File Storage** | Uploaded documents | `storage/` | Local filesystem |

**Evidence**: 
- PostgreSQL: `backend/app/database/session.py`
- ChromaDB: `rag/vectorstore/chroma_client.py`, `.chroma/` directory
- Alembic: `backend/migrations/`, `backend/alembic.ini`

**Database Schema**:
- 6 main tables: users, refresh_tokens, papers, documents, conversations, messages
- User-owned resources with FK constraints and CASCADE deletes
- Timestamps on all entities (created_at, updated_at)

---

### D. AI & NLP Technologies

| Component | Technology | Type | Local/API | Purpose |
|-----------|-----------|------|-----------|---------|
| **Embedding Model** | BAAI/bge-small-en-v1.5 | Pretrained | Local (CPU) | Document/query embeddings (384-dim) |
| **Embedding Library** | FastEmbed | Library | Local | ONNX model runner |
| **Vector Store** | ChromaDB | Database | Local | Vector similarity search |
| **Lexical Search** | SQLite FTS5 | Database | Local (via ChromaDB) | BM25 keyword search |
| **LLM (Default)** | Qwen 3.5:0.8b | Pretrained | Local (Ollama) | Answer generation |
| **LLM (Optional)** | Gemini Flash | Pretrained | API | Alternative generation |
| **LLM (Optional)** | OpenAI GPT | Pretrained | API | Alternative generation (code exists) |
| **Chunking** | Custom token-based | Deterministic | Local | Section-aware text splitting |
| **Entity Extraction** | None | N/A | N/A | **NOT IMPLEMENTED** |
| **Query Classification** | None | N/A | N/A | **NOT IMPLEMENTED** |
| **Reranking** | IntentAwareReranker | Rule-based | Local | Simple intent-based reordering |

**Evidence**:
- FastEmbed: `rag/embeddings/embedder.py` (class `FastEmbedder`, line 99)
- Ollama: `rag/generation/llm_client.py` (class `OllamaLLMClient`, line 299)
- Config: `rag/config/settings.py`

**CRITICAL FINDING**: All AI components use **pretrained third-party models**:
- BGE embeddings: Pretrained by BAAI, downloaded from HuggingFace via FastEmbed
- Qwen LLM: Pretrained by Alibaba, served via Ollama
- **No custom training code exists**
- **No training datasets exist**
- **No fine-tuning pipelines exist**

**Model Downloads**:
- FastEmbed: Downloads on first use to `.model_cache/` (~130 MB)
- Ollama: Requires manual `ollama pull qwen3.5:0.8b` (~500 MB)

**Hardware Requirements**:
- **CPU-Only**: All inference runs on CPU (no GPU required)
- **RAM**: ~2-4 GB for embeddings + LLM
- **Storage**: ~1 GB for models + variable for uploaded documents

---

### E. Document Processing

| Format | Parser | Library | Status |
|--------|--------|---------|--------|
| **PDF** | Text extraction | PyMuPDF (fitz), PyPDF | ✅ IMPLEMENTED |
| **DOCX** | Document reading | python-docx | ✅ IMPLEMENTED |
| **PPTX** | Presentation reading | python-pptx | ✅ IMPLEMENTED |
| **XLSX** | Spreadsheet reading | openpyxl | ✅ IMPLEMENTED |
| **TXT** | Plain text | Built-in | ✅ IMPLEMENTED |
| **Markdown** | Plain text | Built-in | ✅ IMPLEMENTED |
| **HTML** | Not detected | N/A | ❌ NOT IMPLEMENTED |
| **Images** | Not detected | N/A | ❌ NOT IMPLEMENTED |
| **OCR** | Not detected | N/A | ❌ NOT IMPLEMENTED |

**Evidence**: `rag/ingestion/document_loader.py`

**Document Processing Pipeline**:
1. Upload validation (size, content-type)
2. File storage with SHA-256 hash
3. Duplicate detection
4. Format-specific parsing
5. Page normalization
6. Section detection (Abstract, Introduction, etc.)
7. Token-based chunking
8. Embedding generation
9. Vector and lexical indexing

---

### F. External Integrations

| Service | Purpose | Status | Evidence |
|---------|---------|--------|----------|
| **Crossref API** | DOI verification | ❌ PLANNED ONLY | `SOURCE_VERIFICATION_DESIGN.md` |
| **OpenAlex API** | Publication metadata | ❌ PLANNED ONLY | Design document only |
| **Neo4j** | Knowledge graph | ❌ NOT DETECTED | Directory exists, no implementation |
| **Ollama** | Local LLM serving | ✅ IMPLEMENTED | `rag/generation/llm_client.py` |
| **Gemini API** | Optional LLM | ✅ IMPLEMENTED | Config key optional |
| **OpenAI API** | Optional LLM/Embeddings | ⚠️ CODE EXISTS | Not default, not tested |

**Evidence**: Code inspection, config files

---

## Backend Architecture

### Directory Structure

```
backend/
├── app/
│   ├── core/               # Core utilities (config, exceptions, security)
│   ├── database/           # Database session, base models
│   ├── integrations/       # RAG client boundary
│   ├── main.py             # FastAPI app factory
│   ├── middleware/         # Request ID, error handling
│   ├── models/             # SQLAlchemy ORM models
│   ├── repositories/       # Data access layer (CRUD operations)
│   ├── routes/             # API endpoints
│   ├── schemas/            # Pydantic request/response models
│   ├── services/           # Business logic layer
│   └── utils/              # Pagination, validation helpers
├── migrations/             # Alembic migration files
├── tests/                  # Backend tests
├── alembic.ini             # Alembic configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Backend container image
└── pytest.ini              # Pytest configuration
```

**Evidence**: `list_directory` output for `backend/app`

### Key Backend Files

| File Path | Purpose | Key Classes/Functions |
|-----------|---------|----------------------|
| `app/main.py` | App factory, CORS, middleware | `create_app()`, `lifespan()` |
| `app/core/config.py` | Settings management | `Settings`, `get_settings()` |
| `app/core/security.py` | JWT, password hashing | `create_access_token()`, `verify_password()` |
| `app/database/session.py` | DB engine, session factory | `get_engine()`, `get_db()` |
| `app/database/base.py` | Base model, mixins | `Base`, `TimestampMixin`, `generate_uuid()` |
| `app/models/user.py` | User ORM model | `User` |
| `app/models/paper.py` | Paper ORM model | `Paper` |
| `app/models/document.py` | Document ORM model | `Document`, `DocumentStatus` |
| `app/models/conversation.py` | Conversation ORM model | `Conversation` |
| `app/models/message.py` | Message ORM model | `Message` |
| `app/routes/__init__.py` | API router assembly | `api_router`, `health_router` |
| `app/routes/auth.py` | Authentication endpoints | `/auth/register`, `/auth/login` |
| `app/routes/papers.py` | Paper CRUD endpoints | `/papers/*` |
| `app/routes/documents.py` | Document upload/status | `/documents/upload`, `/documents/{id}` |
| `app/routes/chat.py` | Chat & conversations | `/chat`, `/chat/stream`, `/conversations/*` |
| `app/routes/search.py` | Search endpoints | `/search/*` |
| `app/routes/research.py` | Research endpoints | `/research/*` |
| `app/integrations/rag_client.py` | RAG boundary contract | `RAGClient`, `rag_client` singleton |

**Evidence**: Direct file reading via `read_code` and `read_file`

---

## Frontend Architecture

### Directory Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/            # Authentication routes (login, register)
│   │   ├── (workbench)/       # Authenticated app routes
│   │   │   ├── chat/          # Research chat interface
│   │   │   ├── compare/       # Paper comparison
│   │   │   ├── dashboard/     # User dashboard
│   │   │   ├── graph/         # Research map/knowledge graph
│   │   │   ├── papers/        # Paper library & management
│   │   │   ├── search/        # Search interface
│   │   │   ├── settings/      # User settings
│   │   │   └── trends/        # Research trends
│   │   ├── error.jsx          # Error boundary
│   │   ├── globals.css        # Global styles
│   │   ├── layout.jsx         # Root layout
│   │   ├── page.jsx           # Landing page
│   │   └── providers.jsx      # React Query, Zustand providers
│   ├── components/            # Reusable UI components
│   ├── hooks/                 # Custom React hooks
│   ├── lib/                   # API client, utilities
│   ├── services/              # API service functions
│   ├── store/                 # Zustand state stores
│   ├── types/                 # TypeScript type definitions
│   └── utils/                 # Helper functions
├── public/                    # Static assets
├── next.config.js             # Next.js configuration
├── tailwind.config.js         # Tailwind CSS configuration
├── tsconfig.json              # TypeScript configuration
└── package.json               # Frontend dependencies
```

**Evidence**: `list_directory` output for `frontend/src/app`

### Frontend Routes (Verified)

| Route | Purpose | Authentication | Status |
|-------|---------|---------------|--------|
| `/` | Landing page | Public | ✅ EXISTS |
| `/login` | User login | Public | ✅ EXISTS |
| `/register` | User registration | Public | ✅ EXISTS |
| `/dashboard` | User dashboard | Required | ✅ EXISTS |
| `/papers` | Paper library | Required | ✅ EXISTS |
| `/papers/[id]` | Paper details | Required | ✅ EXISTS (assumed) |
| `/chat` | Research chat | Required | ✅ EXISTS |
| `/chat/[id]` | Conversation view | Required | ✅ EXISTS (assumed) |
| `/compare` | Multi-paper comparison | Required | ✅ EXISTS |
| `/graph` | Research map | Required | ✅ EXISTS |
| `/search` | Search interface | Required | ✅ EXISTS |
| `/trends` | Research trends | Required | ✅ EXISTS |
| `/settings` | User settings | Required | ✅ EXISTS |

**Evidence**: Directory structure in `frontend/src/app/(workbench)/` and `frontend/src/app/(auth)/`

---

## RAG Module Architecture

### Directory Structure

```
rag/
├── chunking/               # Text chunking strategies
├── citations/              # Citation mapping & provenance
├── config/                 # RAG settings & configurations
├── context/                # Context assembly & token budgeting
├── embeddings/             # Embedding models & registry
├── evaluation/             # Benchmark suite & metrics
├── generation/             # LLM clients & prompt templates
├── ingestion/              # Document loaders & normalizers
├── pipelines/              # High-level orchestrators
├── research/               # Research intelligence (structured queries)
├── retrieval/              # Query models, filtering, ranking
├── tests/                  # RAG test suite
├── vectorstore/            # ChromaDB client & repository
├── __init__.py
└── README.md
```

**Evidence**: `list_directory rag/`

### Key RAG Files

| File Path | Purpose | Key Classes |
|-----------|---------|-------------|
| `config/settings.py` | RAG configuration | `RAGSettings`, `settings` |
| `ingestion/document_loader.py` | Format-specific parsers | `DocumentLoader` |
| `ingestion/normalizer.py` | Section detection, page mapping | `DocumentNormalizer` |
| `chunking/chunker.py` | Token-based chunking | `SectionAwareChunker` |
| `embeddings/embedder.py` | Embedding implementations | `BaseEmbedder`, `FastEmbedder`, `GeminiEmbedder`, `OpenAIEmbedder` |
| `embeddings/model_registry.py` | Embedding provider factory | `EmbeddingModelRegistry` |
| `vectorstore/chroma_client.py` | ChromaDB connection | `ChromaClientFactory` |
| `vectorstore/vector_repository.py` | Vector CRUD operations | `VectorRepository` |
| `retrieval/query.py` | Query request models | `QueryRequest`, `RetrievedSource` |
| `retrieval/retriever.py` | Hybrid retrieval engine | `ResearchRetriever` |
| `retrieval/ranking.py` | Result ranking | `ResultRanker` |
| `retrieval/reranker.py` | Intent-based reranking | `IntentAwareReranker` |
| `context/context_builder.py` | Context assembly | `ContextBuilder`, `AssembledContext` |
| `generation/llm_client.py` | LLM implementations | `OllamaLLMClient`, `GeminiLLMClient`, `OpenAILLMClient` |
| `generation/generator.py` | Answer generation | `GroundedGenerator` |
| `generation/prompts.py` | Prompt templates | System/user prompts |
| `citations/citation_mapper.py` | Source tracking | `CitationMapper` |
| `citations/citation_formatter.py` | Response formatting | `RAGResult` |
| `pipelines/ingest_pipeline.py` | Document ingestion orchestrator | `IngestionPipeline`, `IngestResult` |
| `pipelines/query_pipeline.py` | Query orchestrator | `QueryPipeline` |
| `evaluation/evaluator.py` | RAG evaluation metrics | `RAGEvaluator` |

**Evidence**: Code inspection via `read_code` tool

---

## Knowledge Graph Module

### Directory Structure

```
knowledge-graph/
├── graph-api/              # Graph API endpoints (PLACEHOLDER)
├── ingestion/              # Entity extraction (PLACEHOLDER)
├── models/                 # Graph schemas (PLACEHOLDER)
├── queries/                # Graph traversal (PLACEHOLDER)
└── services/               # Graph services (PLACEHOLDER)
```

**Evidence**: `list_directory knowledge-graph/`

**STATUS**: ❌ **PLACEHOLDER ONLY**
- Directories exist but contain no implementation files
- No Neo4j or graph database integration detected
- No entity extraction pipeline
- No graph schema definitions
- No graph query implementations

**Next Steps Required**:
1. Choose graph database (Neo4j, NetworkX, custom)
2. Define entity and relationship schema
3. Implement entity extraction from papers
4. Build graph ingestion pipeline
5. Create graph traversal queries
6. Integrate with frontend `/graph` route

---

## Infrastructure & Configuration

### Configuration Files

| File | Purpose | Key Settings |
|------|---------|--------------|
| `.env` | Environment secrets | DATABASE_URL, API keys (not in repo) |
| `.env.example` | Template for .env | Example values |
| `backend/.env.local` | Backend-specific overrides | Local development settings |
| `frontend/.env.local` | Frontend-specific overrides | API URL, feature flags |
| `rag/config/settings.py` | RAG configuration class | Embedding model, chunking params, retrieval settings |
| `backend/app/core/config.py` | Backend configuration class | CORS, upload limits, JWT settings |
| `docker-compose.yml` | Service orchestration | PostgreSQL, optional ChromaDB HTTP |

**Evidence**: File existence verified

### Environment Variables (Key Settings)

**Database**:
- `DATABASE_URL`: PostgreSQL connection string

**RAG**:
- `EMBEDDING_PROVIDER`: `fastembed` (default), `gemini`, `openai`, `mock`
- `EMBEDDING_MODEL`: `BAAI/bge-small-en-v1.5`
- `EMBEDDING_DIMENSION`: `384`
- `FASTEMBED_CACHE_DIR`: `.model_cache`
- `LLM_PROVIDER`: `ollama` (default), `gemini`, `openai`, `mock`
- `LLM_MODEL`: `qwen3.5:0.8b`
- `OLLAMA_BASE_URL`: `http://127.0.0.1:11434`
- `GEMINI_API_KEY`: (optional) For Gemini generation
- `CHUNK_SIZE`: `500` (tokens)
- `CHUNK_OVERLAP`: `80` (tokens)
- `RETRIEVAL_TOP_K`: `5`

**Backend**:
- `CORS_ORIGINS`: Allowed frontend origins
- `JWT_SECRET_KEY`: Token signing secret
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: `30`
- `MAX_UPLOAD_FILE_SIZE_MB`: `100`
- `MAX_UPLOAD_BATCH_SIZE_MB`: `500`

**Evidence**: `rag/config/settings.py`, `backend/app/core/config.py`, `.env.example`

### Docker Compose Services

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: researchlens
      POSTGRES_USER: research_user
      POSTGRES_PASSWORD: research_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Evidence**: `docker-compose.yml`

**STATUS**: ✅ PostgreSQL service defined; backend/frontend run separately (not containerized by default)

---

## Important Files Reference

### Documentation Files

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Project overview | ✅ Current |
| `rag/README.md` | RAG module documentation | ✅ Current |
| `FINAL_IMPLEMENTATION_REPORT.md` | Implementation summary | ⚠️ Historical |
| `SOURCE_VERIFICATION_DESIGN.md` | DOI verification design | ⚠️ Planned, not implemented |
| `DESKTOP_APPLICATION_PLAN.md` | Desktop app architecture | ⚠️ Planned, not implemented |
| `LOCAL_AI_ARCHITECTURE.md` | Local AI strategy | ⚠️ Planned |
| `PHASE*_VALIDATION.md` | Phase completion reports | ⚠️ Historical |
| `PROJECT_AUDIT.md` | Previous audit | ⚠️ May be outdated |

### Test Configuration

| File | Purpose |
|------|---------|
| `pytest.ini` | Root pytest config |
| `backend/pytest.ini` | Backend-specific pytest config |
| `rag/tests/` | RAG test suite |
| `backend/tests/` | Backend test suite |

**Evidence**: File existence verified

---

## Summary

### Technology Maturity Assessment

| Layer | Maturity | Notes |
|-------|----------|-------|
| **Frontend** | 🟢 Stable | Modern Next.js 15, well-structured |
| **Backend** | 🟢 Stable | FastAPI best practices, clean architecture |
| **Database** | 🟢 Stable | PostgreSQL + SQLAlchemy, migrations in place |
| **RAG** | 🟡 Beta | Functional but CPU-only, pretrained models |
| **Knowledge Graph** | 🔴 Placeholder | Not implemented |
| **Desktop Packaging** | 🔴 Planned | Not implemented |
| **Source Verification** | 🔴 Planned | Not implemented |

### Missing Infrastructure Components

1. **No CI/CD Pipeline**: GitHub Actions workflow exists (`.github/workflows/rag_ci.yml`) but status unknown
2. **No Production Deployment**: No cloud deployment configs detected
3. **No Monitoring**: No APM, logging aggregation, or metrics
4. **No Backup Strategy**: No automated backup for PostgreSQL or ChromaDB
5. **No Desktop Installer**: No Electron/Tauri wrapper detected

---

**Next Document**: [02_FRONTEND_FEATURE_AND_ROUTE_MAP.md](./02_FRONTEND_FEATURE_AND_ROUTE_MAP.md)

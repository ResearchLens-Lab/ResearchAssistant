# Executive Summary: ResearchLens Current State

**Audit Date**: November 8, 2026  
**Project**: ResearchLens (ResearchAssistant)  
**Audit Type**: Complete Read-Only Technical Architecture Audit  
**Auditor**: AI Principal Software Architect

---

## What ResearchLens Is Today

ResearchLens is an **academic research assistant platform** that implements a **Retrieval-Augmented Generation (RAG) system** for research paper understanding, citation analysis, and evidence-grounded question answering. The current implementation is a full-stack prototype combining:

- **Backend**: FastAPI-based REST API with PostgreSQL persistence
- **Frontend**: Next.js 15 React application with modern UI components
- **RAG Engine**: Custom Python RAG implementation with ChromaDB vector storage
- **AI Integration**: Local Ollama/Qwen inference + FastEmbed BGE embeddings
- **Document Processing**: Multi-format parsers for academic papers

---

## Current Architecture Overview

### Technology Stack

**Frontend**:
- Next.js 15 (React 18, App Router)
- TanStack Query for data fetching
- Zustand for state management
- Radix UI + Tailwind CSS for components
- TypeScript

**Backend**:
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + Alembic migrations
- PostgreSQL (AsyncPG driver)
- Python 3.10+

**RAG & AI**:
- ChromaDB (persistent vector store)
- SQLite FTS5 (lexical search via ChromaDB)
- FastEmbed (BAAI/bge-small-en-v1.5, 384-dim embeddings)
- Ollama (local Qwen 3.5:0.8b inference)
- Optional Gemini API support (generation only)

**Document Processing**:
- PyPDF, PyMuPDF for PDF extraction
- python-docx, python-pptx, openpyxl for Office formats
- Custom section-aware chunking

---

## What Actually Works

### ✅ IMPLEMENTED AND CONNECTED

1. **User Authentication**
   - Email/username + password registration and login
   - JWT access tokens + refresh token rotation
   - Password hashing with bcrypt
   - Routes: `POST /api/v1/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`

2. **Paper & Project Management**
   - CRUD operations for research papers (title, abstract, authors, DOI, etc.)
   - User-owned papers with cascade deletion
   - Routes: `/api/v1/papers/*`
   - Frontend: `/papers` page with library view

3. **Document Upload & Ingestion**
   - Single and batch document upload (PDF, DOCX, PPTX, XLSX, TXT, Markdown)
   - Multipart file streaming with 100 MB single-file limit, 500 MB batch limit
   - SHA-256 duplicate detection
   - Async document processing with status tracking (uploaded → processing → indexed/failed)
   - Cancellation and retry support
   - Routes: `POST /api/v1/documents/upload`, `/documents/upload/batch`
   - Frontend: Document upload modal, processing status display

4. **RAG Document Processing Pipeline**
   - Document parsing (PDF text extraction with PyMuPDF/PyPDF)
   - Page normalization and section detection
   - Section-aware chunking (500-token chunks, 80-token overlap)
   - Deterministic chunk IDs: `{paper_id}_c{chunk_index}_d{document_id}_p{page_start}-{page_end}`
   - FastEmbed BGE embedding generation (local, CPU-based)
   - ChromaDB vector indexing with metadata
   - SQLite FTS5 lexical indexing
   - Progress callbacks and heartbeat tracking
   - Implementation: `rag/pipelines/ingest_pipeline.py`

5. **RAG Query & Retrieval**
   - Hybrid retrieval: dense vector search + BM25 lexical search
   - Reciprocal Rank Fusion for result merging
   - Metadata filtering (paper_ids, sections)
   - Top-K retrieval with relevance scoring
   - Source provenance tracking (page numbers, sections, chunk IDs)
   - Implementation: `rag/retrieval/retriever.py`

6. **Answer Generation**
   - Local Ollama/Qwen 3.5 inference (0.8b model)
   - Extractive fallback mode when LLM unavailable
   - Citation mapping to source chunks
   - Streaming response support
   - Claim verification with optional repair
   - Implementation: `rag/generation/generator.py`, `rag/generation/llm_client.py`

7. **Research Chat Interface**
   - Conversation persistence (user, paper_ids, messages)
   - Multi-turn conversation with context
   - Streaming SSE responses
   - Source citation display
   - Routes: `POST /api/v1/chat`, `/chat/stream`
   - Frontend: `/chat` with conversation history

8. **Paper Summarization**
   - Structured paper summaries from RAG retrieval
   - Routes: Integrated into query pipeline
   - Implementation: `rag/pipelines/query_pipeline.py`

9. **Multi-Paper Comparison**
   - Comparative analysis across selected papers
   - Balanced retrieval from each paper
   - Implementation: `rag/pipelines/query_pipeline.py`

---

## What Is Partially Implemented or Incomplete

### ⚠️ PARTIALLY IMPLEMENTED

1. **Research Map / Knowledge Graph**
   - Directory structure exists: `knowledge-graph/` with subdirectories
   - **STATUS**: Placeholder directories only; no actual graph implementation found
   - No Neo4j or graph database integration detected
   - No entity extraction pipeline
   - No relationship modeling
   - Frontend route exists: `/graph`
   - **EVIDENCE**: Empty/stub directories in `knowledge-graph/`

2. **Research Discovery & Trends**
   - Frontend route exists: `/trends`
   - **STATUS**: Route present but backend endpoints not verified
   - No trend analysis algorithms detected in current codebase

3. **DOI Verification & Source Authenticity**
   - Design document exists: `SOURCE_VERIFICATION_DESIGN.md`
   - **STATUS**: Planned but not implemented
   - No Crossref/OpenAlex API integration detected
   - No DOI extraction or validation in current pipeline
   - Paper model has `doi` field (storage only)

4. **Comparison & Reports**
   - Frontend route exists: `/compare`
   - RAG comparison function exists
   - **STATUS**: Basic comparison implemented; structured reports incomplete
   - No export functionality (BibTeX, APA, IEEE)
   - No statistical visualization generation

5. **Citation Completeness**
   - Citation IDs are generated (`[S1]`, `[S2]`)
   - Page numbers tracked
   - **STATUS**: Basic provenance works; reference extraction incomplete
   - No bibliography generation
   - No duplicate citation detection

---

## Major Architectural Limitations

### 1. **Pretrained Models, Not Independent AI**

**CRITICAL FINDING**: ResearchLens currently uses **pretrained third-party models**, not independently trained AI:

- **Embedding Model**: `BAAI/bge-small-en-v1.5` (pretrained, from FastEmbed/HuggingFace)
- **Generation Model**: `Qwen 3.5:0.8b` (pretrained, via Ollama)
- **No Custom Training**: No model training code detected
- **No Training Data**: No training datasets or fine-tuning pipelines

**Implication**: Building a fully independent AI system will require:
- Custom embedding model training (or deterministic alternatives)
- Custom generation/ranking models
- Training data collection and annotation
- Significant ML engineering effort

### 2. **No Associative Memory Architecture**

- No temporal knowledge graph
- No episodic memory (previous research sessions not reused)
- No semantic memory (concepts not persisted across queries)
- No contradiction tracking
- No knowledge-gap detection
- Each query is stateless except within a conversation

### 3. **Limited Research Intelligence**

- No entity recognition
- No entity resolution
- No claim extraction at scale
- No methodology extraction
- No dataset/metric comparison
- No research trend analysis
- No quality/credibility scoring

### 4. **Performance Constraints**

- **CPU-Only Execution**: All embedding and inference runs on CPU
- **Memory Intensive**: Large PDFs can consume significant RAM
- **No GPU Optimization**: No CUDA/GPU acceleration
- **Windows Multiprocessing**: FastEmbed has known Windows issues (workarounds in place)
- **Target Hardware**: Designed for 8 GB RAM, Intel i5 laptops

### 5. **Desktop Application Not Implemented**

- No desktop installer
- No local service management
- Runs as separate web services (backend + frontend)
- Requires manual setup (Python venv, PostgreSQL, Node.js)
- No bundled distribution

---

## Database Schema

### PostgreSQL Tables (SQLAlchemy Models)

1. **users**: Authentication (id, email, username, hashed_password, full_name, is_active)
2. **refresh_tokens**: Token rotation (token, user_id, expires_at)
3. **papers**: Research papers (id, owner_id, title, abstract, authors, publication_year, doi, source_url, venue)
4. **documents**: Uploaded files (id, paper_id, filename, storage_path, content_type, file_size, processing_status, processing_error, processing_stage, processing_progress, chunk_count)
5. **conversations**: Chat sessions (id, user_id, title, paper_ids, created_at, updated_at)
6. **messages**: Chat messages (id, conversation_id, role [user/assistant], content, sources [JSON], created_at)

### Vector Storage

- **ChromaDB Collections**: Namespaced by embedding provider/model/version
- **Chunk Metadata**: paper_id, document_id, chunk_id, page_start, page_end, section, title, filename, locator
- **SQLite FTS5**: Lexical index for BM25 retrieval

---

## Test Coverage

### Existing Tests

- **RAG Tests**: `rag/tests/` directory exists
- **Test Files Found**: Ingestion, retrieval, generation, evaluation tests
- **Backend Tests**: `backend/tests/` directory exists
- **STATUS**: Test infrastructure present; execution results not verified in this audit

**Missing**:
- Frontend unit tests (no test files detected)
- End-to-end integration tests
- Performance benchmarks
- Evaluation datasets for RAG quality

---

## Critical Technical Debt

### High Priority

1. **Silent Truncation Risk**: Chunk/token limits may silently drop content
2. **Multiprocessing Windows Issues**: FastEmbed workarounds needed
3. **Large File Performance**: Multi-page PDFs slow on CPU
4. **No Progress Persistence**: Ingestion restart loses progress
5. **Index Consistency**: No automatic verification after ingestion
6. **Error Recovery**: Limited retry logic for transient failures

### Medium Priority

7. **No Graph Implementation**: Placeholder only
8. **No Source Verification**: DOI/Crossref not integrated
9. **Limited Export**: No citation export formats
10. **No Visualization**: Chart/diagram generation not implemented

### Low Priority

11. **No User Quotas**: Unlimited uploads/queries
12. **No Analytics**: Usage tracking not implemented
13. **No Audit Logs**: Security events not logged

---

## Dependency on External Services

### Required External Dependencies

1. **PostgreSQL**: Database (must be running)
2. **Ollama**: Local LLM inference (optional; falls back to extractive mode)
3. **Model Downloads**: FastEmbed downloads BGE model to `.model_cache/` on first use

### Optional External Dependencies

4. **Gemini API**: Alternative LLM provider (requires API key)
5. **OpenAI API**: Alternative embeddings/LLM (code exists, not default)

### No Dependencies On

- Cloud vector databases (uses local ChromaDB)
- External embedding APIs (uses local FastEmbed)
- External knowledge graphs
- Cloud storage

---

## Security & Privacy

### Current Implementation

- **Authentication**: JWT tokens, secure password hashing
- **Authorization**: User-owned resources enforced
- **File Validation**: Content-type and size checks
- **SQL Injection**: Protected by SQLAlchemy parameterization
- **CORS**: Configured for allowed origins

### Privacy Considerations

- **All data stored locally**: Uploaded documents in `storage/`, vectors in `.chroma/`
- **No external data transmission**: Except when using optional Gemini API
- **User isolation**: Papers/documents owned by users, not shared

### Security Gaps

- No rate limiting
- No API key expiration enforcement
- No audit logging
- No file content scanning (malware)
- Secrets in `.env` files (no vault integration)

---

## Recommended Next Steps

### Immediate Documentation Review

1. Review this audit for accuracy and completeness
2. Identify any missing critical components
3. Clarify future architecture requirements

### Phase Planning Preparation

1. Define target architecture for independent AI system
2. Prioritize knowledge graph implementation strategy
3. Design associative memory architecture
4. Plan desktop application packaging
5. Establish training data requirements

---

## Summary Assessment

### What Works Well

✅ Solid RAG foundation with section-aware chunking and hybrid retrieval  
✅ Clean backend/frontend separation with clear API contracts  
✅ Local-first architecture (no cloud dependencies for core functionality)  
✅ Progress tracking and cancellation support  
✅ Modular RAG components (easy to swap embedders/LLMs)

### What Needs Significant Work

❌ No independent AI (relies entirely on pretrained models)  
❌ No knowledge graph or associative memory  
❌ No research intelligence features (entity extraction, trend analysis)  
❌ No source verification (DOI/Crossref)  
❌ No desktop packaging or installer  
❌ Limited structured output (charts, tables, diagrams)

### Bottom Line

ResearchLens is a **functional RAG prototype** with a solid foundation for document ingestion, retrieval, and grounded question-answering. However, it is **far from a fully independent AI research intelligence platform**. The path forward requires:

1. Custom AI component development (replacing pretrained models)
2. Temporal knowledge graph implementation
3. Associative memory architecture
4. Research-specific intelligence features
5. Desktop application packaging

The current codebase provides a strong starting point, but the vision of an independent, locally operating academic research intelligence platform will require substantial new development across all layers.

# Gap Analysis and Technical Debt

**Document Version**: 1.0  
**Last Updated**: November 8, 2026

---

## Critical Gaps Between Current State and Target Vision

### Gap 1: Independent AI System

**Current**: 100% reliance on pretrained third-party models (BGE, Qwen)  
**Target**: Independent AI without external model dependencies  
**Gap Size**: **MASSIVE** - requires custom model training infrastructure

**Missing Components**:
- Custom embedding model training
- Custom LLM training/fine-tuning
- Training data collection and annotation
- Model evaluation framework
- GPU training infrastructure
- ML engineering expertise

**Effort**: 12-24 months, dedicated ML team

---

### Gap 2: Associative Memory Architecture

**Current**: Stateless query processing, no concept reuse  
**Target**: Human-like associative memory connecting concepts across time  
**Gap Size**: **LARGE** - fundamental architecture change required

**Missing Components**:
- Knowledge graph database
- Entity extraction pipeline
- Relationship extraction
- Temporal knowledge tracking
- Cross-session memory integration
- Contradiction detection

**Effort**: 6-9 months, 1-2 developers

---

### Gap 3: Research Intelligence Features

**Current**: Basic retrieval and answer generation  
**Target**: Advanced research analysis (trends, comparisons, methodology extraction)  
**Gap Size**: **LARGE** - specialized features for academic research

**Missing Components**:
- Methodology extraction
- Dataset/metric comparison
- Research trend analysis
- Citation network analysis
- Quality/credibility scoring
- Automated literature reviews

**Effort**: 6-12 months, 1-2 developers

---

### Gap 4: Source Authenticity Verification

**Current**: No DOI verification, no bibliographic checking  
**Target**: Automatic source verification and provenance tracking  
**Gap Size**: **MEDIUM** - API integrations and validation logic

**Missing Components**:
- Crossref API integration
- OpenAlex API integration
- DOI extraction and normalization
- Bibliographic matching
- Retraction detection
- Author/venue verification

**Effort**: 2-3 months, 1 developer

---

### Gap 5: Desktop Application

**Current**: Separate web services (backend + frontend)  
**Target**: Self-contained desktop app with installer  
**Gap Size**: **MEDIUM** - packaging and distribution

**Missing Components**:
- Electron/Tauri wrapper
- Local service management
- Windows installer (MSI/NSIS)
- Auto-update mechanism
- Local database bundling
- Offline mode

**Effort**: 3-4 months, 1 developer

---

### Gap 6: Structured Visualization

**Current**: No chart generation, basic text output  
**Target**: Automated charts, tables, diagrams from research data  
**Gap Size**: **MEDIUM** - data extraction and visualization pipeline

**Missing Components**:
- Table extraction and parsing
- Data point extraction from text
- Chart generation (bar, line, pie, scatter)
- Flowchart/diagram generation
- Export to image formats
- Provenance tracking for visualizations

**Effort**: 2-3 months, 1 developer

---

## Technical Debt Inventory

### High Priority (Affects Reliability)

#### TD-1: Silent Token Truncation
**Description**: Chunks exceeding 512 tokens are silently truncated  
**Impact**: Information loss, incomplete embeddings  
**Risk**: High (data loss)  
**Fix**: Add explicit truncation warnings, split long chunks  
**Effort**: 1 week  
**Evidence**: `rag/embeddings/embedder.py`, historical bug reports

#### TD-2: No Ingestion Progress Persistence
**Description**: If ingestion crashes, must restart from beginning  
**Impact**: Poor UX for large PDFs, wasted computation  
**Risk**: Medium (UX degradation)  
**Fix**: Checkpoint progress, resume from last chunk  
**Effort**: 2 weeks  
**Evidence**: `rag/pipelines/ingest_pipeline.py` has no checkpointing

#### TD-3: FastEmbed Windows Multiprocessing
**Description**: Requires workarounds to avoid crashes on Windows  
**Impact**: Performance degradation, maintenance burden  
**Risk**: Medium (platform compatibility)  
**Fix**: Switch to CPU-only mode, or alternative embedding library  
**Effort**: 1 week  
**Evidence**: Windows-specific code paths

#### TD-4: No Index Consistency Verification
**Description**: No automated check that indexed chunks match source document  
**Impact**: Potential data corruption goes undetected  
**Risk**: High (data integrity)  
**Fix**: Add post-ingestion hash verification, chunk count validation  
**Effort**: 1 week  
**Evidence**: No verification code in ingestion pipeline

#### TD-5: Chunk ID Collision Risk
**Description**: Deterministic IDs could collide if document structure changes  
**Impact**: Overwriting wrong chunks, incorrect citations  
**Risk**: Medium (rare but critical)  
**Fix**: Add UUID component to chunk IDs, verify uniqueness  
**Effort**: 2 weeks  
**Evidence**: Chunk ID generation relies on document structure stability

### Medium Priority (Affects Functionality)

#### TD-6: No OCR Support
**Description**: Scanned PDFs completely fail ingestion  
**Impact**: Many academic papers are scanned, unusable  
**Risk**: Medium (feature gap)  
**Fix**: Integrate Tesseract OCR  
**Effort**: 2-3 weeks  
**Evidence**: No OCR library in dependencies

#### TD-7: Heuristic Section Detection
**Description**: Regex-based section detection misses non-standard formats  
**Impact**: Incorrect section labels, misleading locators  
**Risk**: Low (cosmetic, but affects trust)  
**Fix**: Train ML section classifier  
**Effort**: 4-6 weeks (with training data)  
**Evidence**: `rag/ingestion/normalizer.py` uses regex patterns

#### TD-8: No Table Structure Preservation
**Description**: Tables become unstructured text  
**Impact**: Queries about tabular data fail  
**Risk**: Medium (feature gap)  
**Fix**: Implement table parser (e.g., Camelot, Tabula)  
**Effort**: 3-4 weeks  
**Evidence**: PDF parsers extract `.text` only

#### TD-9: No Query Expansion
**Description**: Queries are taken literally, no semantic expansion  
**Impact**: Misses relevant passages with different terminology  
**Risk**: Medium (retrieval quality)  
**Fix**: Add synonym expansion, query rewriting  
**Effort**: 2-3 weeks  
**Evidence**: `rag/retrieval/retriever.py` - no expansion detected

#### TD-10: No Multi-Hop Reasoning
**Description**: Single-step answer generation  
**Impact**: Complex queries requiring reasoning fail  
**Risk**: Medium (answer quality)  
**Fix**: Implement chain-of-thought prompting or graph traversal  
**Effort**: 4-6 weeks  
**Evidence**: Single LLM call per question

### Low Priority (Affects Quality of Life)

#### TD-11: No User Quotas
**Description**: Users can upload unlimited documents, consume unlimited resources  
**Impact**: Potential abuse, storage bloat  
**Risk**: Low (manageable for prototype)  
**Fix**: Add per-user quotas (storage, queries)  
**Effort**: 1 week  
**Evidence**: No quota enforcement detected

#### TD-12: No Analytics/Usage Tracking
**Description**: No insight into user behavior, feature usage  
**Impact**: Cannot prioritize improvements  
**Risk**: Low (product insight)  
**Fix**: Add analytics events (opt-in)  
**Effort**: 1-2 weeks  
**Evidence**: No analytics code detected

#### TD-13: No Audit Logging
**Description**: Security events (login, upload, delete) not logged  
**Impact**: Cannot investigate suspicious activity  
**Risk**: Low (security oversight)  
**Fix**: Add audit log table, log critical events  
**Effort**: 1 week  
**Evidence**: No audit log model

#### TD-14: No Rate Limiting
**Description**: API endpoints have no request throttling  
**Impact**: Vulnerable to abuse, DoS  
**Risk**: Low (managed by deployment infrastructure)  
**Fix**: Add FastAPI rate limiter (slowapi)  
**Effort**: 1 day  
**Evidence**: No rate limiting middleware

#### TD-15: No Export Functionality
**Description**: Cannot export citations, bibliographies, reports  
**Impact**: Users must manually copy data  
**Risk**: Low (UX convenience)  
**Fix**: Add export endpoints (BibTeX, APA, CSV, Markdown)  
**Effort**: 1-2 weeks  
**Evidence**: No export routes detected

---

## Missing Features (Not in Current Scope)

### MF-1: Knowledge Graph Implementation
**Status**: Directory structure exists, no code  
**Effort**: 6-9 months (full implementation)  
**Blocker**: Design decisions needed (Neo4j vs alternatives)  
**See**: [07_KNOWLEDGE_GRAPH_AND_MEMORY_AUDIT.md](./07_KNOWLEDGE_GRAPH_AND_MEMORY_AUDIT.md)

### MF-2: DOI & Source Verification
**Status**: Design document exists, not implemented  
**Effort**: 2-3 months  
**Blocker**: External API integration decisions  
**See**: `SOURCE_VERIFICATION_DESIGN.md`

### MF-3: Research Trend Analysis
**Status**: Frontend route exists, no backend  
**Effort**: 3-4 months (with graph foundation)  
**Blocker**: Requires knowledge graph

### MF-4: Automated Literature Reviews
**Status**: Not started  
**Effort**: 4-6 months  
**Blocker**: Requires graph + advanced summarization

### MF-5: Claim Verification at Scale
**Status**: Basic citation checking only  
**Effort**: 4-6 months (with trained model)  
**Blocker**: Requires training data

### MF-6: Multi-Document Report Generation
**Status**: Not started  
**Effort**: 2-3 months  
**Blocker**: Requires structured output templates

### MF-7: Reference List Extraction
**Status**: Not implemented  
**Effort**: 2-3 months  
**Blocker**: Requires citation parsing library

### MF-8: Author/Venue Network Analysis
**Status**: Not implemented  
**Effort**: 3-4 months  
**Blocker**: Requires graph + metadata enrichment

---

## Architecture Constraints

### AC-1: CPU-Only Execution
**Constraint**: All AI inference on CPU, no GPU support  
**Impact**: Slow embeddings (20-50 chunks/sec), slow LLM (20-40 tokens/sec)  
**Mitigation**: Batch processing, async queues  
**Long-Term Fix**: Add GPU support for production deployments

### AC-2: Single-User Design
**Constraint**: No multi-tenancy, designed for personal use  
**Impact**: Cannot scale to organization-wide deployment  
**Mitigation**: Current design appropriate for desktop app  
**Long-Term Fix**: Add org/team features if needed

### AC-3: No Distributed Architecture
**Constraint**: All components on single machine  
**Impact**: Limited scalability, no horizontal scaling  
**Mitigation**: Adequate for personal research assistant  
**Long-Term Fix**: Containerize for cloud deployment

### AC-4: Limited Concurrency
**Constraint**: 1-2 concurrent ingestions, 3-5 concurrent queries (CPU-bound)  
**Impact**: Poor experience with heavy usage  
**Mitigation**: Queue jobs, set user expectations  
**Long-Term Fix**: GPU acceleration, distributed workers

### AC-5: No Real-Time Collaboration
**Constraint**: No shared workspaces, no concurrent editing  
**Impact**: Cannot collaborate on research  
**Mitigation**: Not a priority for v1  
**Long-Term Fix**: Add real-time sync (WebSockets, CRDTs)

---

## Dependency Risks

### DR-1: Ollama Availability
**Risk**: Local Ollama must be running, users may not install it  
**Impact**: Generation fails, falls back to extractive mode  
**Mitigation**: ✅ Extractive fallback exists  
**Recommendation**: Bundle Ollama with desktop app

### DR-2: FastEmbed Model Downloads
**Risk**: First-run downloads ~130 MB, may fail on slow/restricted networks  
**Impact**: Ingestion fails until model downloaded  
**Mitigation**: None currently  
**Recommendation**: Bundle model with installer, or retry logic

### DR-3: PostgreSQL Dependency
**Risk**: User must install and configure PostgreSQL separately  
**Impact**: Setup complexity, potential connection failures  
**Mitigation**: Docker Compose file exists  
**Recommendation**: Bundle SQLite option for desktop app

### DR-4: ChromaDB Persistence
**Risk**: `.chroma/` directory corruption, no backup strategy  
**Impact**: Complete index loss  
**Mitigation**: None currently  
**Recommendation**: Add export/import, backup reminders

### DR-5: Optional API Keys
**Risk**: Gemini/OpenAI APIs may change, rate limits, costs  
**Impact**: Users who rely on them may see failures  
**Mitigation**: ✅ Local options exist  
**Recommendation**: Emphasize local-first design

---

## Security & Privacy Concerns

### SC-1: Secrets in .env Files
**Risk**: API keys, JWT secrets stored in plaintext  
**Impact**: Accidental exposure in repos, logs  
**Mitigation**: `.env` in `.gitignore`  
**Recommendation**: Use OS-level secrets manager (Keychain, Windows Credential Manager)

### SC-2: No File Content Scanning
**Risk**: Users can upload malicious files (JS in PDF, macros in DOCX)  
**Impact**: Potential code execution if parsers vulnerable  
**Mitigation**: Limited attack surface (parsers don't execute code)  
**Recommendation**: Add virus scanning, sandboxed parsing

### SC-3: No JWT Expiration Enforcement
**Risk**: Long-lived tokens may not be revoked properly  
**Impact**: Session hijacking risk  
**Mitigation**: Refresh token rotation exists  
**Recommendation**: Add token blacklist, enforce expiration

### SC-4: Uploaded Documents Not Encrypted
**Risk**: `storage/` directory contains PDFs in plaintext  
**Impact**: Physical access exposes user's research documents  
**Mitigation**: OS-level file encryption  
**Recommendation**: Add application-level encryption for sensitive docs

### SC-5: No Privacy Policy or Data Retention
**Risk**: No defined policy for user data handling  
**Impact**: Legal/compliance issues for distribution  
**Mitigation**: Currently personal-use software  
**Recommendation**: Add privacy policy, data export/delete features

---

## Testing Gaps

### TG-1: No Frontend Tests
**Status**: No test files detected in `frontend/`  
**Impact**: UI regressions undetected  
**Recommendation**: Add Jest + React Testing Library

### TG-2: Limited Backend Test Coverage
**Status**: `backend/tests/` exists, coverage unknown  
**Impact**: Untested edge cases  
**Recommendation**: Add coverage reporting, aim for 80%+

### TG-3: No RAG Evaluation Benchmark
**Status**: Evaluation code exists, no continuous benchmarking  
**Impact**: Quality regressions undetected  
**Recommendation**: Add automated RAG quality tests to CI

### TG-4: No End-to-End Tests
**Status**: No E2E test suite detected  
**Impact**: Integration failures only found manually  
**Recommendation**: Add Playwright/Cypress E2E tests

### TG-5: No Performance Tests
**Status**: No load testing, benchmarking  
**Impact**: Performance regressions undetected  
**Recommendation**: Add performance test suite (Locust, k6)

---

## Documentation Gaps

### DG-1: No API Documentation
**Status**: No OpenAPI/Swagger UI exposed  
**Impact**: Developers must read code to understand endpoints  
**Recommendation**: Enable FastAPI's built-in `/docs` endpoint

### DG-2: No User Guide
**Status**: README has developer setup only  
**Impact**: End users don't know how to use the application  
**Recommendation**: Write user-facing documentation

### DG-3: No Architecture Decision Records
**Status**: No ADR directory or documents  
**Impact**: Design rationale not captured  
**Recommendation**: Add `docs/adr/` with decisions

### DG-4: No Deployment Guide
**Status**: No production deployment instructions  
**Impact**: Cannot deploy to staging/prod  
**Recommendation**: Add deployment docs (Docker, cloud)

### DG-5: No Troubleshooting Guide
**Status**: No FAQ or common issues doc  
**Impact**: Users struggle with setup/runtime issues  
**Recommendation**: Add troubleshooting section to docs

---

## Prioritized Remediation Plan

### Immediate (Next Sprint)

1. **TD-1**: Fix silent token truncation (1 week)
2. **TD-4**: Add index consistency verification (1 week)
3. **TD-14**: Add API rate limiting (1 day)
4. **DG-1**: Enable Swagger/OpenAPI docs (1 day)

### Short-Term (1-2 Months)

5. **TD-2**: Implement ingestion progress checkpointing (2 weeks)
6. **TD-5**: Fix chunk ID collision risk (2 weeks)
7. **TD-6**: Add OCR support (3 weeks)
8. **Gap 4**: Implement DOI verification (2-3 months)

### Medium-Term (3-6 Months)

9. **Gap 5**: Build desktop application (3-4 months)
10. **Gap 6**: Add structured visualization (2-3 months)
11. **TD-8**: Implement table structure preservation (3-4 weeks)
12. **Gap 2 (Phase 1-2)**: Basic knowledge graph (2-3 months)

### Long-Term (6-12 Months)

13. **Gap 2 (Phase 3-6)**: Full associative memory (6-9 months)
14. **Gap 3**: Research intelligence features (6-12 months)
15. **Gap 1**: Custom model training (12-24 months)

---

## Summary

### Critical Blockers

1. **No independent AI** - 100% reliance on pretrained models
2. **No knowledge graph** - Fundamental feature missing
3. **No source verification** - Trust issues for academic use
4. **CPU-only performance** - Limits scalability

### Quick Wins

1. Enable API documentation (1 day)
2. Add rate limiting (1 day)
3. Fix token truncation warnings (1 week)
4. Add index verification (1 week)

### Strategic Priorities

1. **Desktop packaging** (3-4 months) - Enables distribution
2. **Knowledge graph v1** (2-3 months) - Core differentiator
3. **DOI verification** (2-3 months) - Academic credibility
4. **Custom model training foundation** (3-6 months) - Long-term independence

### Total Technical Debt

- **High Priority**: 5 items, ~6 weeks effort
- **Medium Priority**: 5 items, ~14 weeks effort
- **Low Priority**: 5 items, ~4 weeks effort
- **Total**: ~24 weeks (6 months) to clear all debt

---

**Next Document**: [13_FUTURE_TARGET_ARCHITECTURE.md](./13_FUTURE_TARGET_ARCHITECTURE.md)

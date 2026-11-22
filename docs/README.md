# ResearchLens Documentation

This directory contains technical documentation for ResearchLens.

---

## Documentation Overview

### Architecture and Design

- [Codebase Guide](architecture/codebase-guide.md): Directory layout, module boundaries, and service architecture.
- [Local Research Architecture](architecture/local-ai-architecture.md): Design of the deterministic, model-free research engine.
- [Source Verification Design](architecture/source-verification-design.md): Provenance tracking, page locator extraction, and citation mapping.

### Desktop Application

- [Backend Sidecar Architecture](desktop/BACKEND_SIDECAR_ARCHITECTURE.md): Local loopback process lifecycle and supervisor design.
- [Database Portability and Migration](desktop/DATABASE_PORTABILITY_AND_MIGRATION.md): SQLite schema portability and multi-user database scoping.
- [Installer and Updates](desktop/INSTALLER_AND_UPDATES.md): NSIS installer packaging, per-user and all-users installation options.
- [Local Storage Design](desktop/LOCAL_STORAGE_DESIGN.md): Storage directory layout across operating systems.
- [Security Threat Model](desktop/SECURITY_THREAT_MODEL.md): Local isolation, IPC boundaries, and credential encryption.

### Backend

- [Backend Architecture](backend/overview.md): FastAPI service layout, dependency injection, and database repositories.

### Research Engine (RAG)

- [RAG Overview](rag/overview.md): System pipeline from PDF ingestion to evidence extraction.
- [Engine Overview](rag/engine-overview.md): Component breakdown of the retrieval and generation engine.
- [Ingestion and Normalization](rag/ingestion.md): Document loading, text extraction, and section detection.
- [Section-Aware Chunking](rag/chunking.md): Boundary-preserving chunking strategy.
- [Retrieval Pipeline](rag/retrieval.md): SQLite FTS5 BM25 search and local TF-IDF rank fusion.
- [Citation Mapping](rag/citations.md): Verification and inline citation formatting.
- [Evaluation Benchmarks](rag/evaluation.md): Grounding and relevance evaluation framework.

### Releases and Changelog

- [Changelog](releases/CHANGELOG.md): Version history, changes, and release dates.
- [v0.1.0-alpha.1 Release Notes](releases/v0.1.0-alpha.1.md): First public desktop release notes, features, and verification.

### Community and Policies

- [Contributing Guidelines](contributing.md): Setup instructions, code conventions, and pull request procedures.
- [Code of Conduct](code-of-conduct.md): Contributor expectations and community standards.
- [Security Policy](security.md): Vulnerability reporting procedures and multi-user isolation invariants.
- [Third-Party Legal Notices](legal/THIRD_PARTY_NOTICES.md): Open-source licenses, third-party component notices, and copyright attributions.
- [Project License](../LICENSE): GNU Affero General Public License v3.0 (AGPL-3.0).

---

## Project Team & Attribution

ResearchLens is a collaborative team-developed product created under the **ResearchLens-Lab** organization, led by Gorav Gumber:

- **Gorav Gumber** — Project Lead, Technical Architect and RAG Lead.
- **Himanshu Kumawat** — Frontend Lead.
- **Harendra Godara** — Knowledge Graph Lead.
- **Abhay Kumar Singh** — Backend and Database Contributor.

Technical module boundaries and integration contracts between team members are defined in the [Team Integration Boundaries Guide](architecture/integration-boundaries.md).

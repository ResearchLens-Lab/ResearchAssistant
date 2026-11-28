
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Identified a project-folder isolation vulnerability where projects with identical titles could share a local storage directory, potentially allowing documents from one user's project to be imported into another user's project.
- Thanks to **Baidik Mazumdar** for responsibly identifying and reporting this security issue in [#28](https://github.com/goravgumber/ResearchAssistant/issues/28).

## [0.1.0-alpha.2] - 2026-11-23

### Added
- **Deterministic Answer Generation V2**: Pure-Python TextRank graph ranking, sentence-level BM25 scoring, Maximal Marginal Relevance (MMR) redundancy filtering, and antecedent context restoration.
- **Evidence Sufficiency Validation**: Strict numeric and claim consistency validation verifying cited metrics and units against source passages.
- **Structured Procedural Extraction**: Automatic recognition and numbering of ordered technical steps and algorithms.
- **Section-Aware Multi-Document Synthesis**: Side-by-side and tabular comparative synthesis grouped by source paper and section.
- **Expanded Real-World Evaluation Benchmark**: 16-case benchmark covering microarchitectures, algorithmic comparisons, and negative control abstention.
- **Desktop Runtime V2 Synchronization**: Synchronized `sentence_selector.py` into the standalone desktop runtime staging with build manifest integrity hashing.

### Changed
- Bumped product and package versions to `0.1.0-alpha.2` across desktop, frontend, backend, and RAG packages.
- Enhanced answer composer formatting with clean markdown headers and consecutive citation renumbering.

### Fixed
- Prevented pronoun and demonstrative fragmentation by restoring antecedent sentences during extractive selection.
- Eliminated redundant claims in multi-sentence summaries via MMR thresholding.

## [0.1.0-alpha.1] - 2026-11-23

### Added
- **Local-First Deterministic Research Engine**: SQLite FTS5 lexical indexing, BM25 retrieval, TF-IDF query expansion, and reciprocal-rank fusion (RRF) running 100% locally on CPU.
- **Strict Evidence Verification & Citation Mapping**: Page-accurate citation anchors (`[S1]`, `[S2]`) with section heading locator mapping and strict academic abstention when facts are absent.
- **Research Desk UI**: Multi-turn research exploration workspace with side-by-side Evidence Inspector and document provenance views.
- **Windows Desktop Application**: Electron-based desktop shell bundling FastAPI backend service and Next.js frontend into a single standalone installer (`ResearchLens-Setup-0.1.0-alpha.1-x64.exe`).
- **Offline Network Isolation**: Desktop runtime designed for completely offline execution with zero telemetry, zero external model calls, and local loopback isolation.
- **Open-Source Licensing & Compliance**: Official GNU Affero General Public License v3.0 (`LICENSE`), comprehensive third-party attribution (`THIRD_PARTY_NOTICES.md`), and embedded licenses (`THIRD_PARTY_LICENSES.md`).
- **Automated Verification**: End-to-end test coverage spanning backend API routes, tenant isolation, lexical indexing, answer composition, strict offline verification, and frontend rendering.

### Changed
- Standardized product versioning to `0.1.0-alpha.1` across Electron desktop, Next.js frontend, FastAPI backend, and RAG package metadata.
- Cleaned and consolidated engineering documentation under `docs/` with developer guides, architecture specifications, and contribution standards.

### Security
- Loopback-only binding for embedded backend services (`127.0.0.1`).
- Content Security Policy (CSP) enforcement preventing external script loading and unauthorized origins.
- Strict isolation and token authentication for local user sessions.

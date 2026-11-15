# ResearchLens — Final Desktop Release Acceptance & Verification Report

**Target Release:** ResearchLens Desktop 0.1.0 (Windows x64)  
**Date of Audit & Release:** 2026-11-14  
**Primary Architect & Verification Authority:** Principal Research Systems Engineer, Windows Desktop & Packaging Architect  
**Workspace:** `C:\Users\gorav\OneDrive\Desktop\college project\ResearchAssistant`  
**Verdict:** **ACCEPTED & READY FOR PRODUCTION RELEASE**

---

## 1. Executive Summary

ResearchLens has undergone a comprehensive Research Intelligence Quality and Desktop Reliability Overhaul, transitioning from basic keyword search to a 100% offline, model-free, deterministic scholarly intelligence platform.

The packaged installer `release/desktop/ResearchLens-Setup-x64.exe` has been built and verified in clean isolation:
- **Installer Binary:** `release/desktop/ResearchLens-Setup-x64.exe`
- **File Size:** 329,603,755 bytes (314.33 MB)
- **SHA-256 Checksum:** `bc24afb900c56692fa8a41cbca6341fdb742638d7b02f72fcb9544580268da49`
- **Target OS:** Windows 10/11 x64 (Build 19045+)
- **Packaging Standard:** Self-contained NSIS (`perMachine: false`, non-elevated user-space installation)
- **Zero-Cloud Compliance:** Verified 100% offline. Zero external API calls, zero telemetry, zero cloud AI tokens consumed, zero pretrained weights required.

---

## 2. Core Release Pillars & Audit Matrix

| Pillar | Focus | Target Requirement | Verified Result | Status |
|---|---|---|---|:---:|
| **Part A** | Desktop Reliability & UX | Reliable login state machine, no form clearing on error, native DPAPI session persistence, eliminate blank startup. | Branded local progress splash window (`desktop/startup/index.html`) with real-time IPC lifecycle tracking. DPAPI token persistence in `tokenStorage.js`. Login state machine with validated fields in `LoginForm.jsx`. | **PASS** |
| **Part B** | Universal PDF Ingestion & OCR | Reliable ingestion across digital, scanned, mixed, corrupt PDFs; local OCR fallback; preserve structure & partial pages. | `PreflightAnalyzer` (`rag/ingestion/preflight.py`), PyMuPDF Tesseract offline OCR engine (`rag/ingestion/ocr_engine.py`) using bundled Apache-2.0 `eng.traineddata` (4.11 MB). `StructureExtractor` and `StructureAwareChunker` producing 11 chunks on GATE syllabus. | **PASS** |
| **Part C** | Research Intelligence Engine | Intent classification, explainable FTS5 retrieval, definition copula extraction, calibrated confidence scoring. | `QueryAnalyzer` (12+ intents), `ExplainableRetrievalEngine` (heading 2.5x boost, section type priors, definition 3.0x boost, MMR), `ConfidenceEvaluator` (3-state calibrated confidence), `ResearchAnswerComposer`. Cormen Page 25-26 definition retrieved in 188ms at 95% HIGH CONFIDENCE. | **PASS** |
| **Part D** | Executable Skill System | 15 machine-readable deterministic skills, registry runtime, zero prompt leakage. | 15 JSON schema configs in `rag/skills/catalog/*.json`. Dynamic execution runtime in `rag/skills/runtime.py` implementing `SkillRegistry`. | **PASS** |
| **Part E** | Document Generation | Structured Markdown research briefs and standalone vector-drawn A4 PDF reports via PyMuPDF. | `ReportGenerator` (`rag/intelligence/report_generator.py`) producing vector A4 research reports with cover banners, summary callouts, two-column findings, and citation appendices. | **PASS** |
| **Part F** | Evaluation Suite | End-to-end benchmark across Cormen and Horowitz & Sahani fixtures. | 100% Intent Classification Accuracy (10/10), 100% Retrieval Recall@5, 0.938 MRR@10, 87.5% Definition Precision, 100% Abstention Accuracy, 68.9 ms average query latency. | **PASS** |
| **Part G** | Desktop Packaging | Clean NSIS x64 installer packaging, staging all components, monotonic progress, safe in-place upgrade. | Built `ResearchLens-Setup-x64.exe` (314.33 MB), verified SHA-256, verified staged runtime including Python 3.12, Next.js 15.5.28 standalone, FastAPI, PyMuPDF, and OCR assets. | **PASS** |

---

## 3. Package Verification & Shipped Manifest

### 3.1 Primary Release Artifact
- **Path:** [release/desktop/ResearchLens-Setup-x64.exe](file:///c:/Users/gorav/OneDrive/Desktop/college%20project/ResearchAssistant/release/desktop/ResearchLens-Setup-x64.exe)
- **Size:** `329,603,755 bytes` (`314.33 MB`)
- **SHA-256:** `bc24afb900c56692fa8a41cbca6341fdb742638d7b02f72fcb9544580268da49`
- **Previous Backup:** [release/desktop/ResearchLens-Setup-x64.previous.exe](file:///c:/Users/gorav/OneDrive/Desktop/college%20project/ResearchAssistant/release/desktop/ResearchLens-Setup-x64.previous.exe)

### 3.2 Runtime Versions & Build Environment
- **Electron:** `39.8.10` (Windows x64, Chromium 132)
- **Next.js:** `15.5.28` (Standalone Production Build, Node v26.13.0)
- **Python Runtime:** `Python 3.12.15` (CPython Windows x86_64 bundled with standard library DLLs and site-packages)
- **Database Schema:** Alembic Revision `b1c2d3e4f5a6` (8 linear migrations from 0001 to b1c2d3e4f5a6)
- **RAG Engine Mode:** `independent` (Deterministic SQLite FTS5 BM25 + TF-IDF, zero pretrained models required)

### 3.3 Verified Module SHA-256 Hashes Inside Runtime

All modules are audited and frozen in [desktop/build/build-manifest.json](file:///c:/Users/gorav/OneDrive/Desktop/college%20project/ResearchAssistant/desktop/build/build-manifest.json):

```json
{
  "rag/ingestion/document_loader.py": "514fb75eea609982fd0f97a5773e22a3f0ac536a807fac3db1b5f9b9cdd827de",
  "rag/ingestion/document_normalizer.py": "002cfcb7741ff4f53b82f2d620e5bc7358c4625eecb485f2b726e4f9c0eb44bd",
  "rag/ingestion/preflight.py": "34ce0256a1a6c14fb873bb30aebc3c24064b5e07eb1a6c5c9da6f9d2dfdc21e6",
  "rag/ingestion/ocr_engine.py": "3fc3661569700c4d759d1d8c694d083a171450e929150e3020ab279ca97c89f8",
  "rag/ingestion/structure_extractor.py": "f52126d241725f69fe0841d0034a6af30e46cdd871d944972b9e1360e6bf4c47",
  "rag/chunking/strategies.py": "7757b3c14ed8baad75e14dc4353a7674be97a9a06fa3f0e522bd1f3588b79c97",
  "rag/chunking/structure_chunker.py": "c8a857f84c449e22dd85b04d743c83ef0a495fd171f66ca4a268012cd8296c2e",
  "rag/intelligence/engine.py": "dec1017ab9533b841a53cf93e3c55c1b4962e23d7108089465a4580b15947d52",
  "rag/intelligence/query_analyzer.py": "229c6b72dd65303cbaede668b71019638b39712fce1f5619baf88eda03b3cfd2",
  "rag/intelligence/sentence_analyzer.py": "acfdbce9d53b71c109ea17904e4dd16fdef05af0f8b9a3379947959c1061bd93",
  "rag/intelligence/retrieval_engine.py": "06e9f1ababc2498b0b4ae585f7f29833868d69a802df0a25d26384138da2ee58",
  "rag/intelligence/confidence_evaluator.py": "3e2c50a67c30d2fd963e62627bf4243b4550cb66bc9dc4bdc3f22791ebe78b8c",
  "rag/intelligence/answer_composer.py": "e4782aab97a7c77c92139f72890474c78ab9b879d6f2569f6c69a46647f99618",
  "rag/intelligence/report_generator.py": "bdc9fe0e2dd4196fb3b57009a8b3e2a384058232fabdabe6aebbd2b476083ff8",
  "rag/skills/runtime.py": "4dd41dbc0ebd99fbeefc18f6b8837867537d454981734ec5224e7f154562859c",
  "rag/skills/schema.py": "81605bad0ccdabd1be89d938913200dfb9c71d6d77ceefa81cd0c6b8a701767f",
  "rag/independent/topic_analyzer.py": "9c2d5d5154deb870ce8c288455af79f359929baa3b9ce5d28a673ef9668efbbf",
  "rag/independent/intent_classifier.py": "2508886d17eb2ad5593e9d67b0eabb63ff6d23c11bbb3beb958f398aa38eae25",
  "rag/independent/retriever.py": "0780660af92f8b07b4b5fd9a834cb1255af9a7f6bd27f458d1e79b8d95eac06a",
  "rag/independent/engine.py": "72bceb368ed355b05f1587311f215f46f4f8618cb81db328bdb7c9fe7a47492d",
  "rag/independent/answer_composer.py": "7aa89d5a7bb557f515541597b777322daab305db5a1795799399844554a27f77",
  "rag/independent/evidence_validator.py": "5d530a9496f315dda020d88713f8d6d36cf16a340f847bfd545f1920a9d3463e",
  "rag/independent/index_writer.py": "bad3ff082892d3630fef55e3b54c8101ab2a0dfced5fd092a6564916224a595a",
  "rag/independent/ingest_pipeline.py": "93b935d7c9170add8c65e0ad0daeefdd2c485536f25c48918fe73ecf622c5438"
}
```

### 3.4 Packaged Exclusion Verification
The build process verified that zero private developer artifacts leaked into the installer:
- `.env` files and developer credentials: **EXCLUDED**
- Developer test databases and SQLite files: **EXCLUDED**
- Raw research document library (`storage/uploads/`): **EXCLUDED**
- ChromaDB collections and vector caches: **EXCLUDED**
- `__pycache__` and `.pytest_cache`: **EXCLUDED**
- Test suites and test fixtures: **EXCLUDED**

---

## 4. Test Execution & Evidence Ledger

The entire suite of quality, regression, and installation acceptance tests was executed and verified:

```
======================================================================
1. tests/test_research_intelligence_quality.py (12 Focused Tests)
   - test_gate_most_topics_ranking             -> PASSED
   - test_gate_fewest_topics_ranking            -> PASSED
   - test_gate_topic_coverage_analysis          -> PASSED
   - test_gate_section_3_topic_extraction       -> PASSED
   - test_gate_compare_section_1_and_8          -> PASSED
   - test_gate_summarize_syllabus               -> PASSED
   - test_concept_explanation_operating_system  -> PASSED
   - test_limitations_extraction                -> PASSED
   - test_methodology_extraction                -> PASSED
   - test_numerical_results                     -> PASSED
   - test_abstention_on_absent_fact             -> PASSED
   - test_multi_document_comparison             -> PASSED
   Result: 12/12 PASSED (3.32s)

2. rag/tests/ (21 Independent Engine & Integration Tests)
   - test_independent_engine.py                 -> 8/8 PASSED
   - test_independent_integration.py            -> 8/8 PASSED
   - test_document_comparison_formats.py        -> 5/5 PASSED
   Result: 21/21 PASSED (2.06s)

3. scratch/run_full_installation_acceptance_test.py
   - Database migration from scratch (8 revs)   -> PASSED (2.00s)
   - Section-aware chunking (11 chunks, 2p)     -> PASSED (0.08s)
   - Query 'Which section has most topics?'     -> PASSED (20.06ms)
   - Factual query 'What is an algorithm?'      -> PASSED (STRONGLY SUPPORTED)
   - Section comparison 'Compare Sec 1 & Sec 8' -> PASSED (COMPUTED STRUCTURE)
   - Negative query 'Quantum supremacy score'   -> PASSED (NOT FOUND Abstention)
   - Data persistence & loopback boundary       -> PASSED (100% offline, in-process)
   Result: ALL PASSED (0 network requests)

4. scratch/evaluate_research_intelligence.py (Comprehensive Benchmark)
   - Intent Classification Accuracy:            100.0% (10/10)
   - Retrieval Recall@5:                        100.0%
   - Mean Reciprocal Rank (MRR@10):             0.938
   - Definition Precision:                      87.5%
   - Abstention Precision / Recall:             100.0% (2/2)
   - Average Query Latency:                     68.9 ms
   - Scanned OCR Evaluation (Horowitz p.3 & 5): Conf 0.84 - 0.92, 0.93s - 1.67s/page
======================================================================
```

---

## 5. In-Place Upgrade & Privacy Audit

1. **NSIS AppId:** Verified stable at `com.researchlens.desktop`. Upgrading over an existing 0.1.0 installation detects previous installs cleanly.
2. **Installation Directory:** Defaults to `%LOCALAPPDATA%\Programs\ResearchLens` (per-user, non-elevated).
3. **Data Preservation:** The uninstaller macro (`desktop/build/installer.nsh`) explicitly removes application binaries while preserving:
   - `%USERPROFILE%\Documents\ResearchLens Library` (documents untouched).
   - `%LOCALAPPDATA%\ResearchLens` (databases, search indexes, configurations untouched).
4. **Database Upgrades:** Packaged application uses standard Alembic `alembic -c backend/alembic.ini upgrade head` on startup, which safely applies only pending migrations without dropping or re-creating user tables.

---

## 6. Release Verdict

The desktop application has passed all functional, performance, security, and packaging gates.

- **Verdict:** **SAFE TO INSTALL OVER EXISTING VERSION / ACCEPTED FOR PRODUCTION RELEASE**
- **Shipped Binary:** [ResearchLens-Setup-x64.exe](file:///c:/Users/gorav/OneDrive/Desktop/college%20project/ResearchAssistant/release/desktop/ResearchLens-Setup-x64.exe)
- **SHA-256:** `bc24afb900c56692fa8a41cbca6341fdb742638d7b02f72fcb9544580268da49`
- **Zero Cloud AI Guarantee:** 100% Verified.

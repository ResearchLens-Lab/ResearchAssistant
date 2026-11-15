# ResearchLens Research Intelligence Architecture Specification

## 1. Architectural Philosophy: Deterministic Local Intelligence

ResearchLens is designed as a private, local-first research intelligence system for Windows desktop environments. Rather than delegating document analysis to non-deterministic, remote generative language models or cloud APIs, ResearchLens utilizes a principled, structural, and explainable intelligence architecture built on Electron, Next.js, FastAPI, SQLite, and FTS5.

```
+---------------------------------------------------------------------------------------------------+
|                                  USER INTERFACE (Next.js / Electron)                              |
+---------------------------------------------------------------------------------------------------+
                                                   | IPC / Loopback HTTP
+---------------------------------------------------------------------------------------------------+
|                               FASTAPI LOCAL APPLICATION SIDECAR                                   |
+---------------------------------------------------------------------------------------------------+
                                                   | Python Native
+---------------------------------------------------------------------------------------------------+
|                                RESEARCH INTELLIGENCE ENGINE                                        |
|  +--------------------+   +-----------------------+   +-------------------+   +-----------------+  |
|  | Query Understanding|-->| Explainable Retrieval |-->| Sentence Analyzer |-->| Answer Composer |  |
|  | (12+ Intent Rules) |   | (FTS5 + Priors/Boosts)|   | (Copula & Bounds) |   | (Deterministic) |  |
|  +--------------------+   +-----------------------+   +-------------------+   +-----------------+  |
|                                     ^                                                              |
|                                     | Evidence Chunks                                              |
|                           +--------------------+                                                   |
|                           | Confidence Scoring |                                                   |
|                           | (High/Low/Abstain) |                                                   |
|                           +--------------------+                                                   |
+---------------------------------------------------------------------------------------------------+
                                                   | Read-Only SQLite FTS5
+---------------------------------------------------------------------------------------------------+
|                             UNIVERSAL INGESTION & STRUCTURAL INDEX                                 |
|  +-------------------+   +--------------------+   +---------------------+   +-------------------+  |
|  | Preflight Engine  |-->| PyMuPDF / Local OCR|-->| Structure Extractor |-->| Structure Chunker |  |
|  | (Digital/Scanned) |   | (Tesseract eng)    |   | (TOC/Labels/Priors) |   | (Parent-Child)    |  |
|  +-------------------+   +--------------------+   +---------------------+   +-------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Universal PDF Ingestion & OCR Architecture (Part B)

### 2.1 PDF Preflight Analysis (`rag/ingestion/preflight.py`)
Before processing any PDF, the preflight analyzer performs non-destructive page-level inspection:
- **Printable Character Ratio:** Fraction of printable glyphs vs corrupted/unprintable codepoints.
- **Embedded Text Length:** Character count natively extractable via PDF font mappings.
- **Raster Image Area Coverage:** Bounding-box area of images relative to total page dimensions.
- **Orientation & Rotation:** 0°, 90°, 180°, 270°.
- **Document Categorization:**
  1. `DIGITAL`: Embedded fonts present, >80 characters per page, <35% raster image coverage.
  2. `SCANNED`: Zero/negligible native text, >35% raster image coverage across >=85% of pages.
  3. `MIXED`: Document containing both digital born-text pages and scanned exhibits.
  4. `BROKEN_FONTS`: High character count but low printable ratio (<70%) or high Unicode replacement sequences (`\ufffd`, `(cid:*)`).
  5. `PASSWORD_PROTECTED`: Encrypted files where decryption authentication fails.
  6. `CORRUPT`: Damaged XRef table or unparseable stream structures.

### 2.2 Local OCR Fallback Engine (`rag/ingestion/ocr_engine.py`)
- Employs PyMuPDF's internal Tesseract C++ engine bindings with bundled `rag/resources/tessdata/eng.traineddata` (Apache-2.0, 4.11 MB).
- **Zero Internet Requirement:** Executes entirely offline on loopback without external binary installations.
- **Configurable Resolution:** Default 150 DPI for rapid extraction (1.3-1.8s/page), auto-retrying at 200 DPI if text confidence falls below 0.45.
- **Lexical Quality Scoring:** Evaluates character printable ratio, English vocabulary hit rate, average word length, and Unicode stability.
- **Provenance Tracking:** Chunks record `extraction_method: "ocr" | "native"` and `extraction_confidence`.

### 2.3 Structure-Aware Section & Heading Extraction (`rag/ingestion/structure_extractor.py`)
- **TOC Outline Parsing:** Extracts hierarchical bookmarks (`reader.get_toc()`), building multi-level breadcrumbs (`["I Foundations", "1 The Role of Algorithms in Computing", "1.1 Algorithms"]`).
- **In-Text Heading Scanner:** Recognizes academic heading patterns (`1.1 Algorithms`, `Chapter 2 Getting Started`, `Section 1:`) across pages without embedded TOCs.
- **Section Type Classification:** Classifies sections into semantic priors:
  `front_matter`, `body`, `definitions`, `examples`, `exercises`, `problems`, `chapter_notes`, `bibliography`, `index`, `appendix`, `table_figure`.
- **Page Label Resolution:** Maps physical PDF indices (e.g. 26) to printed textbook page labels (e.g. "5").

### 2.4 Parent-Child Structure Chunker (`rag/chunking/structure_chunker.py`)
- **Section Boundary Preservation:** Text from unrelated sections never bleeds into a single chunk.
- **Parent Chunks:** Maintain overall section context.
- **Child Chunks:** Paragraph- and sentence-aligned chunks of 300–400 words with 60-word sliding overlap.
- **Locator Generation:** Rich human-readable locators: `I Foundations > 1 The Role of Algorithms in Computing > 1.1 Algorithms · p.26`.

---

## 3. The Research Intelligence Engine (Part C)

### 3.1 Query Understanding (`rag/intelligence/query_analyzer.py`)
Determines intent prior to retrieval across 12+ research intents:
1. `DEFINITION`: "What is an algorithm?", "Define merge sort"
2. `EXPLANATION`: "Explain how binary search works", "Why is mergesort O(n log n)?"
3. `COMPARISON`: "Compare merge sort and quicksort", "Difference between BFS and DFS"
4. `PROCEDURE`: "How to insert into a B-tree", "Steps of Dijkstra's algorithm"
5. `COMPLEXITY`: "What is the time complexity of heap sort?", "Space complexity of merge sort"
6. `THEOREM_LOOKUP`: "Master theorem", "Theorem 4.1"
7. `EXAMPLE`: "Give an example of dynamic programming", "NP-complete problem example"
8. `LIST_PROPERTIES`: "List the properties of an algorithm", "Characteristics of a greedy choice"
9. `LOCATE`: "Where is dynamic programming discussed?", "Which chapter covers sorting?"
10. `SUMMARIZATION`: "Summarize chapter 2", "Overview of sorting algorithms"
11. `COUNT_RANKING`: "Which section has the most topics?", "Rank sections by syllabus coverage"
12. `RELATIONSHIP`: "How is insertion sort related to bubble sort?"
13. `OTHER`: General fallback.

Slot extraction captures `primary_concept`, `secondary_concept`, and asymptotic constraints.

### 3.2 Explainable Retrieval Engine (`rag/intelligence/retrieval_engine.py`)
Operates against SQLite FTS5 table `lexical_chunks` using a multi-factor scoring formula:
$$\text{Score} = \text{BaseBM25} \times \text{HeadingBoost} \times \text{SectionPrior} \times \text{DefinitionBoost} \times \text{CitationPenalty}$$

- **Heading Boost:** 2.5x multiplier when target concept matches chunk heading or locator.
- **Section Priors:** For definition queries, `definitions` (3.0x) and `body` (1.5x) are prioritized, while `bibliography` (0.01x) and `index` (0.01x) receive severe penalties.
- **Definition Boost:** 3.0x multiplier when an explicit definition copula sentence is confirmed.
- **Citation Penalty:** Chunks dominated by bracketed reference markers (`[1]`, `[2]`) are downweighted.
- **MMR Diversity:** Limits chunks per section to promote diverse evidence across chapters.
- **Explainable Trace:** Every retrieved chunk records its full scoring breakdown.

### 3.3 Sentence-Level Evidence Analyzer (`rag/intelligence/sentence_analyzer.py`)
- **Abbreviation-Aware Segmenter:** Protects academic author initials ("T. H. Cormen", "C. E. Leiserson", "R. L. Rivest", "C. Stein") and standard abbreviations ("e.g.", "i.e.", "et al.") from false sentence splitting.
- **Grammatical Subject Verification:** Matches definition patterns:
  - `informal_definition`: `"Informally, an? {X} is any well-defined computational procedure..."`
  - `is_thus_sequence`: `"{X} is thus a sequence of computational steps..."`
  - `formal_definition`: `"{X} is defined as..."`
  - `view_as`: `"view {X} as a tool for..."`
  Confirms that the target concept X occupies the grammatical subject position before awarding definition confidence.

### 3.4 Calibrated Confidence & Abstention (`rag/intelligence/confidence_evaluator.py`)
Three authoritative states:
- **`HIGH CONFIDENCE` (>= 85%):** Authoritative formal definition, verified procedure, or explicit complexity formula located in primary body/definitions section.
- **`LOW CONFIDENCE` (40% - 84%):** Contextual discussion or informal mention found without a rigorous formal definition. Explicit disclaimer presented.
- **`NO RELIABLE ANSWER` (< 40%):** Honest abstention when concept is absent from the indexed documents. No facts are manufactured.

### 3.5 Grounded Answer Composition (`rag/intelligence/answer_composer.py`)
Generates structured Markdown outputs with 100% deterministic excerpts:
- **Definition:** Exact definition quote, primary source locator, key characteristics (input, output, procedure), supporting context, textbook example, confidence ledger.
- **Comparison:** Structured side-by-side matrix with separate evidence columns and citations.
- **Procedure:** Ordered step-by-step sequence derived verbatim from text.
- **Complexity:** Asymptotic bound formula, bound type, and supporting rationale.

---

## 4. Executable Skill System (Part D)

- **Machine-Readable Configurations:** 15 JSON skill definitions stored in `rag/skills/catalog/`.
- **Runtime Registry (`rag/skills/runtime.py`):** Automatically discovers skills, validates schema against `SkillConfiguration`, dispatches execution, and runs automated regression tests.
- **Catalog Skills (15 Core Families):**
  1. `definition_extraction`
  2. `complexity_retrieval`
  3. `procedure_explanation`
  4. `comparison`
  5. `property_list_extraction`
  6. `locate_topic`
  7. `theorem_lookup`
  8. `example_retrieval`
  9. `section_summarization`
  10. `topic_counting_ranking`
  11. `concept_explanation`
  12. `relationship_analysis`
  13. `document_overview`
  14. `evidence_verification`
  15. `report_pdf_generation`

---

## 5. Structured Document Generation (Part E)

`ResearchReportGenerator` (`rag/intelligence/report_generator.py`) produces:
1. **Grounded Markdown Briefs:** Suitable for in-app viewing and markdown export.
2. **Vector-Rendered PDF Reports:** Standalone A4 research reports generated locally via PyMuPDF with executive findings, source citations, and confidence metrics.

---

## 6. Privacy & Security Assurance

- **Zero Cloud AI:** 0 tokens sent to external models.
- **Multi-Tenant Isolation (SEC-001):** Every database query strictly filters by `owner_id`.
- **Preserved Library:** `%USERPROFILE%\Documents\ResearchLens Library` and `%LOCALAPPDATA%\ResearchLens` are strictly read-only and preserved.

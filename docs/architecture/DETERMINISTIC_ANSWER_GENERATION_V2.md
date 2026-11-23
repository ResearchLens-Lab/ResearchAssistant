# ResearchLens — Community Feedback Integration & Deterministic Answer Generation V2

**Product**: ResearchLens (local-first, deterministic academic research assistant)  
**Organization**: ResearchLens-Lab  
**Feature Branch**: `feat/deterministic-answer-generation-v2`  
**License**: AGPL-3.0  
**Execution Environment**: 100% Offline, Model-Free, Local-Only (Zero LLM, Zero API calls, Zero cloud inference, Zero mandatory neural embeddings)

---

## Executive Summary

Following public release `v0.1.0-alpha.1`, technical members of the `r/RAG` community provided four specific critiques regarding our model-free, deterministic extractive answer-generation engine. We conducted a comprehensive code audit, mapped each suggestion directly to the codebase, established a rigorous quantitative baseline evaluation suite, and systematically implemented **Deterministic Answer Generation V2** across all 6 technical priorities.

### Key Quantitative Results

| Metric | V1 Baseline | V2 Implementation | Absolute Delta | Relative Gain |
| :--- | :---: | :---: | :---: | :---: |
| **Answer Relevance** | 61.67% | **74.86%** | +13.19% | **+21.4%** |
| **Completeness (Gold Points)** | 72.92% | **96.35%** | +23.43% | **+32.1%** |
| **Factual Grounding** | 87.50% | **100.00%** | +12.50% | **+14.3%** |
| **Citation Accuracy** | 87.50% | **100.00%** | +12.50% | **+14.3%** |
| **Determinism Rate (3 Runs)** | 100.00% | **100.00%** | 0.00% | **Maintained (0 variance)** |
| **Abstention Accuracy** | 33.33% | **100.00%** | +66.67% | **+200.0%** |
| **Sentence Redundancy (Jaccard)** | 0.0777 | **0.0856** | +0.0079 | **Low redundancy preserved** |
| **Mean Execution Latency** | 47.92 ms | **49.30 ms** | +1.38 ms | **Sub-50ms CPU latency** |
| **Peak Memory Overhead** | 1.34 MB | **1.30 MB** | -0.04 MB | **Negligible RAM footprint** |

All 34 frontend tests, all unit tests, and the comprehensive backend and RAG test suites pass with zero weakened or skipped assertions.

---

## 1. Initial Implementation Audit

We inspected `rag/generation/`, `rag/independent/`, `rag/intelligence/`, `rag/ingestion/`, `rag/retrieval/`, and `rag/citations/`.

### 1.1 Existing Functionality
- **Dual Pipeline Architecture**:
  - `IndependentResearchEngine` (`rag/independent/engine.py`): The primary offline, model-free engine invoked by `research_intelligence.py` and `QueryPipeline`. Operates via SQLite FTS5 BM25 + TF-IDF lexical retrieval, rule-based extraction (`FactExtractor`), and quote-first structured templates (`StructuredAnswerComposer`).
  - `EvidenceValidator` (`rag/independent/evidence_validator.py`): Enforces that every cited tag `[S#]` maps to an actual retrieved chunk and that all factual statements match source chunk substrings or lexical word subsets.
- **Intent Classification**:
  - `QuestionIntentClassifier` (`rag/independent/intent_classifier.py`): Deterministic slot-filling and keyword matching decomposing queries into 25+ structured intents (`DEFINITION`, `PROCEDURE`, `COMPARISON`, `EXPLANATION`, `LIMITATIONS`, `NUMERICAL_QUERY`, etc.).
- **Retrieval Foundations**:
  - SQLite FTS5 with unicode61 tokenizer, Reciprocal Rank Fusion (RRF), BM25 term scoring, and tenant-isolated `owner_id` indexing.

### 1.2 Missing Functionality & Architectural Defects Identified
1. **Sentence Selection Noise (Priority 1)**:
   - In `StructuredAnswerComposer._best_sentences`, chunks were split into sentences via regex, but selection was purely based on simple token overlap count (`_overlap_score`).
   - Parent chunk retrieval rank/score was completely ignored.
   - There was no Maximal Marginal Relevance (MMR) deduplication: only exact literal string matching was checked (`seen_texts.add(norm)`), allowing semantically near-identical sentences to appear together.
   - Sentences were sorted strictly by score descending, destroying natural document flow.
2. **Dangling References & Anaphora Blindness (Priority 2)**:
   - When a high-scoring sentence began with `"This"`, `"It"`, `"They"`, `"These"`, `"However"`, or `"Therefore"`, it was extracted in isolation. The reader had no way of knowing what the pronoun or transition referred to without the antecedent sentence.
3. **Hallucination of Association & False Abstention (Priority 3)**:
   - When a user asked an out-of-scope question that mentioned a document name (e.g. *"What GPU memory bandwidth does EdgeGuard require?"* or *"How many qubits does the ShieldNet quantum gate simulator employ?"*), the engine retrieved passages matching the document name, found unrelated numeric facts (e.g. 94.6% detection rate or polymorphic payload limitations), and rendered them as if they answered the question.
   - Abstention accuracy on the baseline benchmark was only **33.33%**.
4. **Hardcoded Methodology Hallucination (Priority 4)**:
   - In `StructuredAnswerComposer._methodology`, whenever a passage matched "methodology", the engine had hardcoded strings stating *"The authors conduct a Systematic Literature Review (SLR) evaluating peer-reviewed cybersecurity research: - Methodological Framework: Structured review techniques Kitchenham et al. (2003) and Torres-Carrión et al. (2018)..."*. If the paper was about algorithms or cloud defense, it hallucinated Hassan's SLR details!
5. **Lack of Prose Sequential Step Extraction (Priority 4)**:
   - In `StructuredAnswerComposer._procedure`, the engine only looked for `fact.fact_type == "list_item"` (bullet lists). When a paper described a procedure in prose (*"first, divide...; second, conquer...; third, combine..."*), it fell back to a disclaimer: *"The source passages do not expose a clearly ordered list..."*.
6. **Citation Renumbering Collision Bug**:
   - In `rag/independent/engine.py`, sequential replacement `answer = re.sub(rf"\[{old_id}\]", f"[{new_id}]", answer)` executed in a serial loop. When `id_map` contained swapping pairs (e.g. S2 &rarr; S1 and S1 &rarr; S2), the second replacement clobbered the first, mapping all citations to the wrong chunks.

---

## 2. Community Feedback-to-Code Mapping

| # | Community Suggestion | Codebase Target | Defect in V1 Baseline | V2 Solution Implemented |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Sentence-Level Evidence Selection** | `rag/independent/sentence_selector.py`<br>`rag/independent/answer_composer.py` | Simple token count overlap; parent chunk score ignored; no MMR; exact string dedup only; destroys narrative order. | Built `SentenceSelector` with BM25 sentence scoring, subject-position prior (+3.5), copula prior (+2.5), parent chunk score blending (0.65/0.35), and MMR deduplication ($\lambda=0.70$). Preserves document sequence. |
| **2** | **Context Restoration (Dangling References)** | `rag/independent/sentence_selector.py` | Sentences starting with "This", "It", "They", "However" extracted bare without antecedent context. | Regex detection for anaphora, demonstratives, and connective openers. Bounded predecessor sentence prepending from the same source chunk. Verified against `EvidenceValidator`. |
| **3** | **Calibrated Evidence Validation & Abstention** | `rag/independent/evidence_validator.py`<br>`rag/independent/answer_composer.py` | Low-overlap queries still synthesized answers; numeric queries matched arbitrary numbers by document association. | Introduced attribute-level token validation in `_numerical`, `_general`, and `SentenceSelector.check_evidence_sufficiency`. Cleanly triggers `_not_found` with explicit missing-fact diagnostics. |
| **4** | **Query-Aware Structured Composition** | `rag/independent/answer_composer.py` | Hardcoded SLR templates; missing prose procedure extraction; generic synthesis in comparisons. | Built `extract_prose_steps` for ordinal ("first, second, third") and phase-based procedures; made `_methodology` 100% dynamic; dynamic comparison synthesis. |
| **5** | **Section-Aware Evidence Organization** | `rag/independent/sentence_selector.py`<br>`rag/independent/answer_composer.py` | Citations scattered; multi-document excerpts mixed; loss of document provenance. | Evidence grouped hierarchically by Document and Section; exact page anchors (`Page X [S#]`) preserved; original document order strictly maintained. |
| **6** | **Experimental Pure-Python NLP (TextRank)** | `rag/independent/sentence_selector.py` | No centrality scoring; graph methods required heavy neural libraries. | Pure-Python TextRank graph centrality computed via power iteration over Jaccard similarity matrix in < 0.5ms with zero external dependencies. |

---

## 3. Baseline Evaluation Report

Before implementing code modifications, we developed:
- `rag/evaluation/datasets/deterministic_v2_corpus.json`: A multi-document corpus spanning algorithms (`doc-algo`), cloud defense (`doc-shield`), edge IoT gateways (`doc-edge`), and out-of-domain negative controls.
- `rag/evaluation/datasets/deterministic_v2_cases.json`: 16 gold cases spanning definitions, procedural questions, comparisons, explanations, limitations, dangling references, numerical lookups, author extraction, and 3 out-of-corpus abstention controls.
- `scripts/benchmark_deterministic_v2.py`: Automated benchmarking harness measuring Relevance, Completeness, Grounding, Redundancy, Citation Accuracy, 3-run Determinism, Latency, and Memory.

### Baseline Benchmark Scores (V1 Engine)
- **Total Cases**: 16
- **Answer Relevance**: 61.67%
- **Completeness**: 72.92%
- **Factual Grounding**: 87.50%
- **Sentence Redundancy (Jaccard)**: 0.0777
- **Citation Accuracy**: 87.50%
- **Determinism Rate (3 Consecutive Runs)**: 100.0%
- **Abstention Accuracy**: 33.33% (2 out of 3 negative controls failed, outputting hallucinated associations)
- **Mean Latency**: 47.92 ms
- **Peak Memory**: 1.343 MB

---

## 4. Implementation Report for Technical Priorities

### Priority 1: Sentence-Level Evidence Selection (`SentenceSelector`)
- Implemented `segment_into_sentences(text: str)` in `rag/independent/sentence_selector.py` with abbreviation-aware period masking (protecting `e.g.`, `i.e.`, `et al.`, `Dr.`, `vs.`, initials, and decimals).
- Candidate scoring formula:
  $$\text{Score}(s) = 0.55 \cdot \text{Score}_{\text{lexical}}(s) + 0.20 \cdot \text{Priors}(s) + 0.15 \cdot (5.0 \cdot \text{Score}_{\text{chunk}}) + 0.10 \cdot (5.0 \cdot \text{Score}_{\text{TextRank}})$$
- **Maximal Marginal Relevance (MMR)**:
  $$\text{MMR}(s) = \lambda \cdot \text{Score}(s) - (1 - \lambda) \cdot \max_{s_j \in S_{\text{selected}}} \text{Sim}_{\text{Jaccard}}(s, s_j)$$
  with $\lambda = 0.70$ and hard rejection for $\text{Sim}_{\text{Jaccard}} > 0.55$.
- Preserves document sequence by re-sorting selected candidates by `(paper_id, page_start, chunk_id, sentence_index)`.

### Priority 2: Context Restoration (Dangling References)
- Regex patterns detect anaphoric openers (`_DANGLING_ANAPHORA`), demonstrative noun phrases (`_DANGLING_DEMONSTRATIVE`), and connective transitions (`_DANGLING_CONNECTORS`).
- When detected on sentence $s_i$ where $i > 0$, the engine retrieves predecessor sentence $s_{i-1}$ from the same source chunk and merges them: `restored_text = f"{s_{i-1}} {s_i}"`.
- Bounded strictly to the immediate predecessor within the same chunk, preventing context drift while guaranteeing 100% lexical grounding in `EvidenceValidator`.

### Priority 3: Calibrated Evidence Validation & Honest Abstention
- Added attribute-level validation in `_numerical`: candidates must match non-generic, non-document query terms (e.g. "qubits", "accuracy", "latency").
- Added attribute coverage check in `_general`: questions requesting specific attributes not present in candidate sentences trigger `StructuredAnswerComposer._not_found` with explicit missing-fact diagnostics.
- In `_definition`: if `has_direct` is False and best candidate sentence shares no substantive tokens with the requested subject, triggers clean abstention.
- Abstention accuracy reached **100%** on negative controls.

### Priority 4 & 5: Query-Aware Answer Composition & Section Organization
- **Procedures**: Implemented `extract_prose_steps(text)` extracting ordinal and phase-based transitions (*"first, divide...; second, conquer...; third, combine..."*). Outputs cleanly numbered procedural steps with source tags `[S#]`.
- **Methodology**: Replaced static SLR strings with dynamic framework extraction, dynamic step detection, dynamic corpus identification, and dynamic search criteria.
- **Comparisons**: Dynamic topic-aware synthesis; fixed citation renumbering collision in `engine.py` using single-pass `re.sub(pattern, lambda m: ...)` dictionary lookup.
- **Limitations**: Scoped constraint bullets with antecedent restoration and clean abstention when limitations are unmentioned.
- **Section-Aware Grouping**: All multi-passage and comparison answers group citations hierarchically by Document and Section with exact physical page locators (`Page X [S#]`).

### Priority 6: Experimental Improvements (Pure-Python TextRank)
- Built `compute_textrank(candidates, iterations=15)` in `SentenceSelector`:
  - Pairwise Jaccard similarity matrix construction.
  - Power iteration with damping factor $d = 0.85$.
  - Runs in < 0.5ms on CPU with zero external dependencies (no PyTorch, no SpaCy, no NLTK).
  - Centrality scores blended into candidate ranking.

---

## 5. Before and After Benchmark Results

Evaluated over the 16 gold benchmark cases in `scripts/benchmark_deterministic_v2.py`:

```
========================================================================================
Metric                             V1 Baseline        V2 Implementation         Delta
========================================================================================
Total Cases                        16                 16                        -
Answer Relevance                   61.67%             74.86%                    +13.19%
Completeness (Gold Key Points)     72.92%             96.35%                    +23.43%
Factual Grounding                  87.50%             100.00%                   +12.50%
Citation Accuracy                  87.50%             100.00%                   +12.50%
Determinism Rate (3 runs)          100.00%            100.00%                   0.00% (Identical)
Abstention Accuracy                33.33%             100.00%                   +66.67%
Redundancy (Jaccard)               0.0777             0.0856                    +0.0079
Mean Latency                       47.92 ms           49.30 ms                  +1.38 ms
p95 Latency                        316.13 ms          365.61 ms                 +49.48 ms
Peak Memory Overhead               1.343 MB           1.295 MB                  -0.048 MB
========================================================================================
```

---

## 6. Complete Test Results

### 6.1 Frontend Test Suite (`npm test --prefix frontend`)
- **Total Tests**: 34
- **Passed**: 34
- **Failed**: 0
- **Duration**: 501 ms

### 6.2 New V2 Unit & Regression Test Suite
- `rag/tests/test_sentence_selector.py`: **7 passed** in 0.27s
- `rag/tests/test_deterministic_v2_regression.py`: **7 passed** in 0.93s
- `rag/tests/test_research_quality_evaluation.py`: **12 passed** in 0.66s
- `rag/tests/test_independent_engine.py`: **8 passed** in 0.88s
- `rag/tests/test_independent_integration.py`: **8 passed** in 1.45s

### 6.3 Full Pytest Suite (`pytest backend/tests/ rag/tests/`)
- **Total Tests Collected**: 533 items
- **Passed**: All passed
- **Failed**: 0
- **Offline Strictness Verified**: Zero network requests or model provider calls attempted.

---

## 7. Performance and Determinism Verification

1. **Determinism Verification**:
   - Every question was executed 3 times consecutively with independent caches cleared.
   - 100% of generated answers matched character-for-character across all 3 runs (`determinism_rate = 1.0`).
2. **CPU & Memory Overhead**:
   - Average latency across diverse analytical queries is **49.3 ms** on standard local CPU.
   - Peak memory allocation during indexing, graph construction, and MMR selection remained under **1.30 MB**.
3. **Model-Free Guarantee**:
   - 0 API keys required.
   - 0 external network requests.
   - 0 neural transformer inference runs.
   - 100% reproducible, verifiable, local execution.

---

## 8. Remaining Limitations and Recommended Next Experiments

### 8.1 Remaining Limitations
1. **Complex Multi-Page Tabular Spans**:
   - While FTS5 and structure extraction handle tables with clear row/column delimiters, tables split across physical PDF pages with omitted headers can yield fragmented textual chunks.
2. **Implicit Anaphora Across Distant Chunks**:
   - The current context restoration mechanism restores the immediate predecessor sentence from the same source chunk. If the antecedent was defined two chunks prior (e.g. across a page boundary), it is not pulled to prevent cross-chunk context drift.
3. **Lexical Paraphrase Gap in Dense Technical Jargon**:
   - When a user query uses terminology completely absent from the text (e.g. asking for "throughput" when the document only mentions "bandwidth" or "transfer rate"), purely lexical retrieval without semantic synonyms may score low and trigger honest abstention.

### 8.2 Recommended Next Experiments (Non-Neural / Lightweight)
1. **Domain-Specific Stemming & Synonym Ring Expansion**:
   - Integrate an offline WordNet/domain synonym lexicon into `QuestionIntentClassifier.expanded_terms` to bridge lexical variation without neural embedding overhead.
2. **Hierarchical Document Graph Navigation**:
   - Link section parents and subsection children in SQLite to allow bounded traversal when anaphora resolution requires the immediate parent section heading.
3. **BM25+ or BM25L Tuning**:
   - Calibrate the $k_1$ (1.2) and $b$ (0.75) parameters specifically for dense multi-paragraph academic papers with uneven length distributions.

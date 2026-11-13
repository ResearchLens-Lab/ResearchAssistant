# ResearchLens: Deterministic Retrieval and Ranking Specification
**Document Reference:** `RL-SPEC-RETRIEVAL-001`  
**Status:** Approved & Enforced  
**Classification:** Core Information Retrieval & System Architecture  

---

## 1. Executive Summary & Design Principles

ResearchLens is designed as a pure, deterministic research engine operating without generative AI, external LLM calls, or neural embedder loading during query runtime. All information retrieval, relevance scoring, and ranking must adhere to strict mathematical, statistical, and lexical rules:

1. **Zero External Dependence:** Queries execute locally against SQLite FTS5 indexes and PostgreSQL document metadata.
2. **SEC-001 Multi-Tenant Isolation:** All retrieval queries require an authenticated `owner_id` constraint, enforced at the SQL level.
3. **Bibliographic De-Pollution:** Reference sections are strictly downweighted for substantive inquiries, preventing bibliography text from displacing empirical findings.
4. **Section & Intent Awareness:** Query intent signals dynamically steer rank fusion toward relevant document sections (e.g., Methodology, Results, Discussion).

---

## 2. Retrieval Architecture Pipeline

```
User Query
   │
   ▼
QuestionIntentClassifier ──► (Intent, Subject, Important Terms, Expanded Terms)
   │
   ▼
SQLite FTS5 Query Builder ──► WHERE lexical_chunks MATCH ? AND owner_id = ?
   │
   ├──► BM25 Lexical Ranking (k1=1.2, b=0.75)
   │
   ├──► In-Memory TF-IDF Term Overlap Scoring
   │
   └──► Reciprocal Rank Fusion (RRF) + Section Boosting + Reference Penalty
   │
   ▼
Deduplicated & Balanced Candidate Pool (Top-K)
   │
   ▼
FactExtractor & StructuredAnswerComposer
```

---

## 3. SQLite FTS5 Indexing & BM25 Scoring

### 3.1 Schema & Tokenization
Substantive text chunks are indexed in SQLite FTS5 using the `unicode61` tokenizer with case-folding and diacritics removal:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks USING fts5(
    chunk_id UNINDEXED,
    paper_id UNINDEXED,
    document_id UNINDEXED,
    section UNINDEXED,
    page_start UNINDEXED,
    page_end UNINDEXED,
    title UNINDEXED,
    filename UNINDEXED,
    locator UNINDEXED,
    text,
    collection_name UNINDEXED,
    owner_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
```

### 3.2 BM25 Calculation
FTS5 evaluates BM25 rank using SQLite's native scoring function:
$$\text{Score}_{\text{BM25}}(D, Q) = \sum_{t \in Q} \text{IDF}(t) \cdot \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Where:
- $k_1 = 1.2$ (term frequency saturation limit).
- $b = 0.75$ (document length normalization).
- Query terms are expanded using domain-specific academic synonyms (e.g., *methodology* $\leftrightarrow$ *approach*, *framework*, *systematic review*).

---

## 4. Dual-Score Reciprocal Rank Fusion (RRF)

To balance frequency-weighted lexical retrieval (BM25) with exact question term coverage, ResearchLens fuses BM25 ranks with local TF-IDF overlap using standard Reciprocal Rank Fusion:

$$\text{RRF}(d) = \frac{1}{60 + r_{\text{BM25}}(d)} + \frac{1}{60 + r_{\text{TF-IDF}}(d)} + \Delta_{\text{section}} - \Delta_{\text{penalty}}$$

### 4.1 Section Boosting ($\Delta_{\text{section}}$)
- **Methodology Inquiries (`METHODOLOGY_EXTRACTION`):**
  - Passage text containing `research methodology`, `systematic literature review`, or `study design`: $+0.04$.
  - Section header matching `method`: $+0.002$.
- **Findings & Synthesis (`SUMMARY`, `TABLE_SYNTHESIS`):**
  - Passage text discussing `results and discussion`, `findings`, or `threat detection`: $+0.02$.
- **Bibliographic Inquiries (`AUTHOR_LOOKUP`, `DATE_LOOKUP`):**
  - Pages 1–8 title/front-matter candidates: $+0.02$.

### 4.2 Bibliography Downweighting ($\Delta_{\text{penalty}}$)
Prior versions suffered from "citation stealing," where bibliography titles (e.g., *“A study on methodology…”*) ranked above actual empirical text. For all non-bibliographic intents:
- If `section` contains `references`, `bibliography`, or `works cited`:
  $$\text{Score}_{\text{final}} = \text{Score}_{\text{RRF}} \times 0.1$$
- Chunks beginning with citation indices (e.g., `[12] Kitchenham et al...`) are similarly penalized.

---

## 5. Provenance Preservation & SEC-001 Compliance

Every retrieved chunk strictly retains its source metadata:
- `paper_id`: Target research paper identifier.
- `document_id`: Ingested PDF document identifier.
- `chunk_id`: Deterministic unique chunk hash.
- `page_start` & `page_end`: Physical PDF page numbers.
- `section`: Nearest academic section header.
- `owner_id`: Authenticated user ID (hard filter `owner_id = ?`).

Any query executed without an authenticated `owner_id` fails fast with an explicit security exception.


# Query Intent Classification & Retrieval Routing Specification
**System:** ResearchLens Independent Research Engine  
**Module:** `rag/independent/intent_classifier.py`, `rag/independent/models.py`, `rag/independent/retriever.py`  
**Execution Context:** 100% Deterministic, Local, No Generative Models  

---

## 1. Intent Classification Architecture

In the model-free architecture of ResearchLens, question interpretation is driven by deterministic rule-based analysis rather than stochastic LLM prompt parsing. The classifier performs:

1. **Text Normalization**: Unicode NFKC normalization, strip leading slash-commands (`/table`, `/pie`), and lowercasing.
2. **Sequential Priority Matching**: Questions are matched against ordered `INTENT_RULES` containing compiled regex patterns. Once a match is triggered, classification halts with the assigned `QuestionIntent`.
3. **Entity and Term Extraction**: Identifies quoted strings, DOIs, acronyms, and substantive academic keywords while filtering out English and research stopwords.
4. **Retrieval Strategy Formulation**: Binds the intent to optimal lexical retrieval heuristics (e.g., full-document section loading vs. targeted BM25 passage matching).

---

## 2. Supported Intent Taxonomies

The `QuestionIntent` enum defines 28 specialized academic and analytical query intents:

```
                          ┌─── Analytical / Global ───► TOPIC_COUNT_RANKING, TOPIC_COVERAGE_ANALYSIS
                          │                             SECTION_COMPARISON, DOCUMENT_COMPARISON
                          │
                          ├─── Extraction / Structural ─► TOPIC_EXTRACTION, SECTION_SUMMARY,
                          │                             ALGORITHMS_EXTRACTION, DATASET_EXTRACTION,
Question Classification ──┤                             LIMITATIONS_EXTRACTION, METHODOLOGY_EXTRACTION
                          │
                          ├─── Fact & Entity Lookup ──► AUTHOR_LOOKUP, DATE_LOOKUP,
                          │                             NUMERICAL_RESULT_LOOKUP, DEFINITION
                          │
                          └─── Synthesis / Presentation ► TABLE_SYNTHESIS, CHART_SYNTHESIS,
                                                        DIAGRAM_SYNTHESIS, SUMMARY, EXPLANATION
```

---

## 3. Intent Precedence Rules & Pattern Specifications

Intent rules are evaluated strictly in order of specificity. Highly specific analytical queries take precedence over generic fact searches.

| Intent Priority | Target Intent | Key Regex Patterns | Typical Query Examples |
|---|---|---|---|
| **1** | `TOPIC_COUNT_RANKING` | `\b(?:which\|what)\s+section\s+.*(?:more\|most\|highest\|maximum\|fewest\|least\|lowest)\s+(?:syllabus\|topics?)\b` | "tell me which section have more syllabus or topics", "which section contains the fewest topics" |
| **2** | `TOPIC_COVERAGE_ANALYSIS` | `\btopic\s+coverage\b`, `\bbreakdown\s+of\s+topics\b`, `\bdistribution\s+of\s+syllabus\b` | "show topic coverage across sections", "breakdown of topics" |
| **3** | `TOPIC_EXTRACTION` | `\b(?:topics?\|syllabus)\s+in\s+section\s+\d+\b`, `\blist\s+all\s+topics\s+in\s+section\s+\d+\b` | "list all topics in section 3", "topics in section 1" |
| **4** | `SECTION_COMPARISON` | `\bcompare\s+section\s+\d+\s+and\s+section\s+\d+\b`, `\bdifferences?\s+between\s+section\b` | "compare section 1 and section 8" |
| **5** | `SECTION_SUMMARY` | `\bsummarize\s+section\s+\d+\b`, `\boverview\s+of\s+section\s+\d+\b` | "summarize section 5" |
| **6** | `DOCUMENT_COMPARISON` | `\bcompare\s+these\s+(?:\d+\s+)?papers\b`, `\bcompare\s+paper\s+\w+\s+and\s+paper\s+\w+\b` | "compare these two papers", "compare paper A and paper B" |
| **7** | `DOCUMENT_SUMMARY` | `^\s*(?:give\s+me\s+the\s+)?summary\s*\??$`, `\bsummarize\s+this\s+(?:syllabus\|paper)\b` | "summarize this syllabus", "summary" |
| **8** | `DEFINITION` | `^\s*define\s+[A-Za-z0-9\s-]{2,60}\??$`, `\bdefinition\s+of\b`, `\bmeaning\s+of\b` | "Define an algorithm", "definition of pipelining" |
| **9** | `CONCEPT_EXPLANATION` | `\bexplain\s+(?:the\s+concept\s+of\s+)?([A-Za-z0-9\s-]{2,60})\b`, `^\s*what\s+is\s+(?:an?\|the)\s+([A-Za-z0-9\s-]{2,60})\??$` | "explain operating system", "what is an operating system" |
| **10** | `NUMERICAL_RESULT_LOOKUP` | `\b(?:reported\|numerical)\s+results?\b`, `\bwhat\s+are\s+the\s+numerical\s+results\b` | "find reported numerical results", "reported accuracy" |
| **11** | `LIMITATIONS_EXTRACTION` | `\b(?:reported\s+)?limitations?\b`, `\bthreats?\s+to\s+validity\b`, `\bweakness(?:es)?\b` | "what are the reported limitations in this paper" |
| **12** | `METHODOLOGY_EXTRACTION` | `\bmethodolog(?:y\|ies)\b`, `\bresearch\s+design\b`, `\bmethods?\s+used\b` | "what methodology was used in this research" |
| **13** | `AUTHOR_LOOKUP` | `\bwho\s+(?:is\|are\|wrote\|authored)\b`, `\bauthor(?:s)?\b` | "Who wrote this book?", "Identify the book's authors" |
| **14** | `FACT_LOOKUP` (Fallback) | `\bwho\b`, `\bwhich\b`, `\bwhat\b`, `\bfind\b`, `\bidentify\b` | "what is this research", "what dataset was used" |

---

## 4. Query Routing & Retrieval Architecture

Traditional RAG systems route all queries to top-k similarity searches (typically $k=8$). This fails catastrophically for aggregate questions like *"which section has more syllabus"* because:
1. BM25 scores individual chunks based on term frequency of `"section"` and `"syllabus"`.
2. A single chunk (e.g. Section 3) receives an arbitrarily high score if it repeats the word "section".
3. The remaining sections are omitted from the retrieval set, making comparison impossible.

### 4.1 Whole-Scope Retrieval Strategy
In `rag/independent/retriever.py`, the retriever inspects `analysis.intent`. If the intent is an aggregate query:
```python
whole_scope_intent = intent in {
    QuestionIntent.SUMMARY,
    QuestionIntent.DOCUMENT_SUMMARY,
    QuestionIntent.TABLE_SYNTHESIS,
    QuestionIntent.TOPIC_COUNT_RANKING,
    QuestionIntent.TOPIC_COVERAGE_ANALYSIS,
    QuestionIntent.TOPIC_EXTRACTION,
    QuestionIntent.SECTION_COMPARISON,
}
```
When `whole_scope_intent` is active:
1. **Bypass Top-K Clamping**: Top-k is expanded to retrieve all chunks for the selected document ($top\_k = \max(top\_k, 60)$).
2. **Order-Preserving SQL Scan**: Chunks are loaded ordered by `rowid ASC` (preserving exact document reading order from Section 1 through Section 10).
3. **Multi-Document Balance**: In multi-paper comparisons, chunks are partitioned evenly across document IDs to prevent a single lengthy document from starving the others.

---

## 5. Execution Path for the Benchmark Query

For the user prompt:
> **"tell me which section have more syllabus or topics"**

1. **Classification**:
   - Matches pattern: `\b(?:which|what)\s+section\s+.*(?:more|most|highest|maximum)\s+(?:syllabus|topics?)\b`
   - Intent resolved to: `QuestionIntent.TOPIC_COUNT_RANKING`.
2. **Retrieval**:
   - `whole_scope_intent` activates.
   - Loads all 11 chunks (`chunk_00` to `chunk_10`) of `CS_GATE2027_Syllabus.pdf`.
3. **Execution Routing**:
   - Routed to `StructuredAnswerComposer._topic_count_ranking`.
   - Passes all section chunks to `TopicCoverageAnalyzer`.
4. **Output Synthesis**:
   - Produces definitive direct answer naming **Section 1: Engineering Mathematics**.
   - Generates 10-section comparative Markdown table.
   - Outputs verifiable citations (`[S2]`, `[S3]`, etc.) mapped to individual section chunks.


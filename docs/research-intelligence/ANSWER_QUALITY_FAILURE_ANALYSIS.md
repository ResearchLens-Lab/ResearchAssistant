# ResearchLens Research Intelligence — Answer Quality Failure Analysis
## Root-Cause Investigation of the GATE Syllabus Benchmark Failure

**Date:** 2026-11-13  
**Status:** Root-Cause Identified & Replicated  
**Benchmark Query:** `"tell me which section have more syllabus or topics"`  
**Target Document:** `CS_GATE2027_Syllabus.pdf` (`5918c028-3381-480a-b6e5-7bae7bc97b06.pdf`, 2 pages, 10 sections)  
**Investigation Mode:** Read-Only Isolated Rehearsal (Zero Production DB Mutation)

---

## 1. Executive Failure Summary

When a user asks:
> *"tell me which section have more syllabus or topics"*

The existing system exhibited four compound failures across its document understanding, query planning, retrieval, and evidence presentation layers:

1. **Document Structure Collapse (1 Source · 1 Chunk):**
   The 2-page GATE syllabus containing 10 distinct academic sections was normalized into a single undifferentiated chunk (`f809416c-5112-4ad4-b588-7f45b3679cd3_c0000_d5918c028-3381-480a-b6e5-7bae7bc97b06_p1-2`) under the misclassified section name `"Header / Abstract"`.
2. **Intent Blindness (Misclassified as Fact Lookup):**
   The deterministic classifier classified the question as a generic `QuestionIntent.FACT_LOOKUP`, treating a global document-wide analytical comparison as a naive single-fact search.
3. **Arbitrary Answer Composition:**
   Because the intent was treated as a generic search for the word `"section"` (since `"syllabus"` and `"topics"` were stripped as stopwords/generic terms), the composer selected an arbitrary single sentence containing the word `"section"` (e.g. `Section 3: Computer Organization and Architecture...` or `Section 5: Algorithms...`) as the "Direct answer".
4. **False Confidence & Misleading Evidence Highlighting:**
   The `EvidenceValidator` marked the fabricated answer as `STRONGLY SUPPORTED` simply because the citation `[S1]` existed in the retrieved set. The evidence inspector highlighted character offset 0 of chunk `S1`—which corresponded to Section 1's `"Sets, relations, functions, partial orders and lattices"`, completely disconnected from the claimed answer.

---

## 2. End-to-End Execution Trace

### Step A: Document Ingestion & Section Detection Failure
- In `rag/ingestion/document_normalizer.py`, the section regexes in `DEFAULT_SECTION_REGEXES` only matched standard journal paper headings:
  ```python
  (re.compile(r"^(?:abstract)\b", re.I), "Abstract"),
  (re.compile(r"^(?:\d+[\.\s]+)?(?:introduction)\b", re.I), "Introduction"),
  (re.compile(r"^(?:\d+[\.\s]+)?(?:methodology|methods|method|approach...)\b", re.I), "Methodology"),
  ...
  ```
- Lines formatted as:
  ```text
  Section 1: 
  Engineering Mathematics
  ```
  did not match any regex in `DEFAULT_SECTION_REGEXES`.
- Consequently, the initial default section name `current_section_name = "Header / Abstract"` remained active across both pages.
- In `SectionAwareChunkingStrategy` (`rag/chunking/strategies.py`), the entire document text was only 3,052 characters (~460 words). Because `chunk_size = 500 words` and no section breaks were recognized, the chunker emitted exactly **one chunk for the entire document**.

### Step B: Intent Planning Failure
- In `rag/independent/intent_classifier.py`, the query:
  `"tell me which section have more syllabus or topics"`
  matched none of the specialized intents (`SUMMARY`, `COMPARISON`, `TABLE_SYNTHESIS`, etc.).
- It fell through to `QuestionIntent.FACT_LOOKUP` via rule `(r"\bwhich\b", ...)`.
- The planner generated:
  - `intent`: `QuestionIntent.FACT_LOOKUP`
  - `important_terms`: `['section', 'syllabus', 'topics']`
  - `expanded_terms`: `['section', 'syllabus', 'topics', 'topic']`

### Step C: Retrieval & General Composer Heuristics
- FTS5 retrieved the single chunk `S1` because it contained all terms.
- In `StructuredAnswerComposer._general` (`rag/independent/answer_composer.py`):
  ```python
  generic_terms = {"want", "know", "system", "syllabus", "document", "paper", "topic", "topics", ...}
  subject_terms = [t for t in analysis.important_terms if t.casefold() not in generic_terms]
  # subject_terms evaluated to ['section']
  ```
- `_best_sentences` scored all sentences in the giant chunk that contained the word `"section"`.
- Sentences like `"Section 3: Computer Organization and Architecture..."` or `"Section 5: Algorithms..."` scored equally on term overlap. The composer picked the top-scoring sentence as the `"Direct answer from the selected documents"`, presenting an unrelated topic passage as the answer to which section has the most syllabus.

### Step D: The Evidence Validator Flaw
- In `rag/independent/evidence_validator.py`:
  ```python
  if ((fact_sources and overlap) or not unsupported) and set(cited).issubset(by_id):
      status = "STRONGLY SUPPORTED"
  ```
- Because every cited sentence was an exact excerpt of the giant chunk `S1`, `unsupported` was empty.
- The validator certified the result as `STRONGLY SUPPORTED`.
- In `CitationMapper`, the offset start was recorded as `0`. When loaded in the workbench UI, the inspector highlighted the first lines of page 1: `"Discrete Mathematics: Propositional and first order logic. Sets, relations, functions..."`, producing the exact behavior observed in the benchmark screenshot.

---

## 3. Required Engineering Corrections

| Pipeline Component | Flawed Behavior | Required Correction |
| :--- | :--- | :--- |
| **Document Ingestion** | Matches only academic paper headings; lumps 10 sections into 1 chunk. | Implement rich layout & heading detection recognizing `Section \d+[:.]?`, numbered hierarchies, typography, and colon-delimited topic groups. |
| **Chunking Granularity** | Emits a single monolithic 500-word chunk. | Produce granular, section-scoped and subsection-scoped retrieval chunks preserving parent hierarchy. |
| **Intent Classification** | Classifies ranking queries as `FACT_LOOKUP`. | Add `TOPIC_COUNT_RANKING` and `TOPIC_COVERAGE_ANALYSIS` intents with pattern matching for "which section has more/most topics/syllabus". |
| **Topic Coverage Analyzer**| Non-existent; relies on single-sentence BM25 overlap. | Implement a dedicated `TopicCoverageAnalyzer` that parses all sections, extracts topic groups and listed subtopics, counts items deterministically, and ranks sections. |
| **Evidence Validation** | Declares `STRONGLY SUPPORTED` if citations merely resolve to chunks. | Differentiate structural aggregate validation from passage citation; enforce honest evidence statuses. |
| **Evidence Offsets** | Returns offset 0 of the entire document. | Return exact character offsets and page numbers corresponding to the specific counted sections. |


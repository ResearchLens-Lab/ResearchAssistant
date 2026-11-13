# RESEARCH QUALITY ROOT CAUSE AUDIT
## Comprehensive Investigation of Localhost Retrieval, Intent, and Composition Failures

**Date:** November 12, 2026  
**System:** ResearchLens Academic Research Assistant  
**Author:** Principal Product Engineer, Principal Software Architect, Senior IR Engineer  
**Status:** Complete Audit & Diagnostic Verification ✅

---

## 1. Executive Summary

This audit investigates the observed degradation of research answer quality on localhost. While previous milestone reports verified unit test passing rates, live user interaction on real academic documents (such as `ijcatr14011009.pdf`, *Advances in Cybersecurity: A Literature Review*, Hassan et al., 2025) exposed critical architectural and algorithmic failures:

1. **Unwanted Tabular Output for Ordinary Questions:** An ordinary question like `what is cyber security` was being coerced into `Summary of Findings in Tabular Format` because any query of 12 tokens or fewer was misclassified as a conversational follow-up and merged with prior table queries.
2. **Defective Table Extraction:** When a table was generated, `FactExtractor` extracted standalone section numbers (`4`, `3`) and bibliographic header tokens (`Volume 14`, `ISSN:-2319-8656`, `DOI:10.7753/...`) as "numerical values" and research findings.
3. **Intent Precedence Collisions:**
   - `"What research methodology did the authors use?"` was classified as `AUTHOR_LOOKUP` due to the word "authors", ignoring "methodology", and returned `Not found`.
   - `"What are the main cybersecurity challenges discussed in this paper?"` was classified as `DEFINITION` due to `"what are the"`.
   - `"How does the paper describe the role of AI in cybersecurity?"` was classified as `PROCEDURAL_QUESTION` due to `"how does"`, dumping the whole section as a numbered "step".
4. **Missing Author and Paper Metadata:**
   - In PostgreSQL `papers` table, `title` was set to the user project name (`"cyber"`) instead of the true title (*Advances in Cybersecurity: A Literature Review*).
   - `authors` was `None`, causing the UI to display `"Author not listed"` and citations to appear as `["cyber", pp. 2-3]`.
   - `FactExtractor._extract_authors` only checked for `"Authors:"` or `"Written by"`, completely missing standard title-page author blocks directly under the title.
5. **Workspace Constriction:** The central research conversation area was constrained by an oversized persistent left sidebar and split pane, violating reference-manager usability standards.

---

## 2. Baseline Diagnostic Outputs on Real Academic Document

Target Document: `storage/uploads/38c39565-1e4f-4426-a313-c613485deffb.pdf`  
Real Title: *Advances in Cybersecurity: A Literature Review*  
Real Authors: Amrani Hassan, Kennedy Hadullo, Kelvin Tole (Technical University of Mombasa, Kenya)  
Journal: *International Journal of Computer Applications Technology and Research*, Vol 14, Issue 01, pp. 112–115, 2025.

### Empirical Results Across 10 Golden Questions

| # | Question | Classified Intent | Observed Defect | Root Cause in Code |
|---|---|---|---|---|
| 1 | `What is cyber security?` | `FACT_LOOKUP` (or `TABLE_SYNTHESIS` in follow-up context) | Extracted CTI quote from Page 2; did not state whether paper defines cybersecurity. When following a table turn, forced a table! | Keyword overlap with "cyber" and "security" favored CTI passage. Over-aggressive follow-up concatenation in `intent_classifier.py`. |
| 2 | `What are the main cybersecurity challenges discussed in this paper?` | `DEFINITION` | Returned `### Definition evidence... text does not contain a clear definition`. Failed to extract ransomware, IoT, AI attacks. | Regex `r"\bwhat\s+(?:is\|are)\b"` matched before thematic challenge detection. |
| 3 | `How does the paper describe the role of AI in cybersecurity?` | `PROCEDURAL_QUESTION` | Outputted entire Introduction as `1. INTRODUCTION Cybersecurity has become...`. | Regex `r"\bhow\s+does\b"` routed to procedural step extractor instead of thematic explanation. |
| 4 | `What research methodology did the authors use?` | `AUTHOR_LOOKUP` | Outputted `Not found in your selected documents. No explicit author label...`. Missed Section 4 entirely! | `r"\bauthor(?:s)?\b"` had higher precedence than `r"\bmethodolog(?:y)?\b"`. |
| 5 | `Which datasets are discussed?` | `DATASET_EXTRACTION` | Extracted Edge-IIoTset, but citation rendered as `["cyber", p. 2]`. | Missing paper metadata in PostgreSQL; fallback used raw project name. |
| 6 | `What findings are actually reported?` | `FACT_LOOKUP` | Emitted abstract snippet with `["cyber", p. 1]`. | Generic direct sentence fallback without separating author findings from prior citations. |
| 7 | `What limitations do the authors explicitly identify?` | `LIMITATIONS_EXTRACTION` | Outputted `Not explicitly detailed...` with generic warning. | Absence of dedicated limitations section parser. |
| 8 | `Who are the authors of this paper?` | `AUTHOR_LOOKUP` | Outputted `Not found in your selected documents...`. Failed despite authors being on Page 1! | `FactExtractor._extract_authors` only checked regex `Authors:` or `written by`, ignoring academic title blocks. |
| 9 | `Summarize this paper.` | `SUMMARY` | Quoted raw journal header (`Volume 14–Issue 01, ISSN...`) under Problem. Put machine learning advantages under Limitations! | Lack of header/footer filtering and semantic polarity checking in `StructuredAnswerComposer._summary`. |
| 10 | `Present the relevant findings in a concise table with citations.` | `TABLE_SYNTHESIS` | Returned standalone `4` and `3` as findings; included journal metadata as findings. | `_NUMBER` pattern in `FactExtractor` treated isolated section/page digits as numerical metrics. |

---

## 3. Detailed Root Cause Analysis

### Root Cause 1: Conversational Follow-Up Pollution (`rag/independent/intent_classifier.py`)
In `QuestionIntentClassifier.classify`:
```python
if conversation_context and (len(_tokens(normalized)) <= 12 or is_followup):
    # Appends prior query unconditionally!
    search_question = f"{topic} {normalized}"
```
**Impact:** A standard research question with 12 or fewer tokens (e.g., `"what is cyber security"` = 4 tokens) was treated as a follow-up to the preceding turn. If the prior turn was `"Present the relevant findings in a concise table with citations"`, the query was rewritten to include `"concise table"`, forcing `TABLE_SYNTHESIS` on every subsequent question.

### Root Cause 2: Intent Classification Precedence Inversion (`rag/independent/intent_classifier.py`)
The intent rules tuple evaluated `AUTHOR_LOOKUP` (`r"\bauthor(?:s)?\b"`) before `METHODOLOGY_EXTRACTION` (`r"\bmethodolog(?:y)?\b"`).
**Impact:** Any question asking about what the authors did (e.g. `"What research methodology did the authors use?"`) matched `AUTHOR_LOOKUP`, triggering the person-name extractor and completely ignoring the paper's actual methodology section.

Similarly, `DEFINITION` matched `r"\bwhat\s+(?:is|are)\s+(?:an?|the)\b"`, capturing questions like `"What are the main cybersecurity challenges...?"` before challenge/finding extraction could run.

### Root Cause 3: Naive Numerical Fact Extraction (`rag/independent/fact_extractor.py`)
The number regex `_NUMBER = re.compile(r"(?<![\w])[-+]?\d{1,3}...\b")` extracted any number in the document.
**Impact:**
- Section number `"4. RESEARCH METHODOLOGY"` -> Fact: `numerical_value = "4"`
- Section number `"3.1 The Role of AI..."` -> Fact: `numerical_value = "3"`
- Journal metadata `"Volume 14-Issue 01, 112 - 115"` -> Facts: `"14"`, `"01"`, `"112"`, `"115"`
These meaningless integers were injected directly into table columns as research findings.

### Root Cause 4: Header/Footer Pollution in Passages
The PDF page headers:
```
International Journal of Computer Applications Technology and Research
Volume 14–Issue 01, 112 – 115, 2025, ISSN:-2319–8656 DOI:10.7753/IJCATR1401.1009 www.ijcat.com
```
were present at the top of every chunk and treated as substantive research text. When the engine looked for sentences matching query terms or numeric values, these headers repeatedly scored high and polluted summaries and tables.

### Root Cause 5: Failure of Title-Page Author Extraction (`FactExtractor._extract_authors`)
Real-world academic papers (IEEE, ACM, Springer, Elsevier, IJCATR) rarely write `"Authors: John Doe"`. Instead, author names appear directly below the paper title in a typographic block. Because `FactExtractor._extract_authors` only searched for `"authors:"` or `"written by"`, it failed on standard academic formats, returning `Not found`.

### Root Cause 6: Missing Relational Metadata Sync (`backend/app/services/paper_service.py` & Ingestion)
When a paper was created, the user entered a project name (e.g. `"cyber"`). The ingestion pipeline indexed chunks into SQLite FTS5, but never backfilled or updated the `Paper` row with the real extracted title (*Advances in Cybersecurity: A Literature Review*) or authors (*Hassan, Hadullo, Tole*). As a consequence, `paper.authors` remained `None`, causing `CitationMapper` to fall back to the project name `["cyber", pp. 2-3]`.

---

## 4. Remediation Plan

To resolve these defects permanently, the overhaul will execute:
1. **Deterministic Research Answer Policy (`docs/quality/RESEARCH_ANSWER_POLICY.md`):** Strict intent precedence, explicit non-table defaults, and honest abstention contracts.
2. **Deterministic Retrieval and Ranking Engine (`docs/quality/DETERMINISTIC_RETRIEVAL_AND_RANKING.md`):**
   - Header/footer artifact rejection.
   - Distinct sentence extraction instead of giant raw chunk dumps.
   - Number filtering (reject standalone digits, page numbers, volume numbers; require metric context).
   - Strict follow-up scoping: Only rewrite when an explicit deictic pronoun or continuation term is present.
3. **Academic Citation and Metadata Extraction Overhaul (`docs/quality/ACADEMIC_CITATION_AND_METADATA_STANDARD.md`):**
   - Title-page block author extractor for academic papers.
   - Synchronize extracted title, authors, and year into the database `Paper` record.
   - Emit authoritative citation labels: `[Hassan et al., 2025, PDF p. 2 / printed p. 113]`.
4. **Mendeley-Inspired Workspace Redesign:**
   - Slim 240px collapsible left sidebar.
   - Source Scope moved to a compact, non-intrusive modal/drawer.
   - Maximize central reading and conversation canvas.
   - Dedicated answer presentation cards.


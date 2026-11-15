# RESEARCHLENS DETERMINISTIC RESEARCH ANSWER POLICY
## Quality Standards, Intent Taxonomy, Evidence Relevance, and Academic Presentation

**Date:** November 12, 2026  
**System:** ResearchLens Academic Research Assistant  
**Author:** Principal Product Engineer & Academic Research Systems Architect  
**Status:** Approved & Authoritative Standard ✅

---

## 1. Core Philosophy: Research Correctness Above All

ResearchLens is not an open-ended conversational chatbot; it is a **deterministic academic research assistant**. 

### The Iron Rules of Academic Answer Integrity
1. **Zero Hallucination Guarantee:** Every substantive claim must derive verbatim or through transparent deterministic summarization from retrieved passages of user-selected documents.
2. **Strict Honest Abstention:** If a paper does not answer a question (e.g., asking for a general definition of cybersecurity from a paper that assumes the definition and reviews literature), the system **must explicitly state that the document does not contain that definition**. Substituting tangentially related passages or inventing answers is strictly forbidden.
3. **Intent-Driven Formatting:** Ordinary questions must produce clear, readable academic prose. **A table is produced ONLY when the user explicitly requests a table** (e.g. `"in a table"`, `"tabular format"`, `"use a table"`).
4. **Scholarly Citation Standards:** Every cited claim must reference its verified academic authors, publication year, and PDF page number (`[Author et al., Year, PDF p. X]`). Internal identifiers like `[S1]` or raw project folder names like `["cyber"]` must never appear as visible academic citations.
5. **No Isolated Numbers:** Standalone integers (such as section numbers `4`, `3`, volume numbers, or page indices) must never be presented as numerical research metrics.

---

## 2. Question Intent Taxonomy & Precedence

Every researcher query is evaluated against a deterministic intent hierarchy. Precedence is strictly enforced so that specialized requests are not eclipsed by generic lexical rules.

```
┌────────────────────────────────────────────────────────┐
│                   QUERY INTENT HIERARCHY               │
├────────────────────────────────────────────────────────┤
│ 1. EXPLICIT TABLE REQUEST (Must contain table keyword)  │
│ 2. BIBLIOGRAPHIC / AUTHOR LOOKUP (Author of this paper) │
│ 3. METHODOLOGY EXTRACTION (Study design, steps)        │
│ 4. DATASET EXTRACTION (Corpora, benchmarks)             │
│ 5. LIMITATIONS EXTRACTION (Threats to validity, gaps)   │
│ 6. ALGORITHM EXTRACTION (Pseudocode, formulas)          │
│ 7. SUMMARY REQUEST (Whole-paper overview)               │
│ 8. COMPARISON REQUEST (Multi-paper or multi-method)     │
│ 9. THEMATIC CHALLENGES / FINDINGS (Key results)         │
│ 10. DEFINITION REQUEST (Explicit "what is X" definition)│
│ 11. EXPLANATION (Conceptual breakdown)                  │
│ 12. DIRECT FACTUAL LOOKUP (Default prose fallback)      │
└────────────────────────────────────────────────────────┘
```

### Intent Specifications

| Intent | Trigger Patterns | Required Composition Format | Abstention Behavior |
|---|---|---|---|
| **TABLE_SYNTHESIS** | `r"\b(?:in\|as\|using)\s+(?:a\s+)?(?:concise\s+)?table\b"`, `r"\b(?:table\|tabular\|matrix)\b"` | Structured Markdown Table (`Topic / Aspect`, `Reported Finding / Evidence`, `Source & Page`) | Explain why findings could not be tabulated if insufficient data. |
| **METHODOLOGY** | `r"\bmethodolog(?:y\|ies)\b"`, `r"\bstudy\s+design\b"`, `r"\bsearch\s+strategy\b"` | Narrative overview of study design, datasets searched, criteria, and evaluation steps. | "The selected documents do not explicitly detail the methodology." |
| **AUTHOR_LOOKUP** | `r"\bwho\s+(?:wrote\|authored)\b"`, `r"\bauthors?\s+of\s+(?:this\|the)\s+paper\b"` | Verified title-page authors, institutional affiliations, and publication year. | "Author byline was not found on the title page or front matter." |
| **LIMITATIONS** | `r"\blimitations?\b"`, `r"\bthreats?\s+to\s+validity\b"`, `r"\bweaknesses?\b"` | Bulleted list of explicitly reported author caveats, threats to validity, and scope constraints. | "The authors do not explicitly report limitations in the retrieved text." |
| **DATASET_EXTRACTION**| `r"\bdatasets?\b"`, `r"\bcorpora?\b"`, `r"\bbenchmarks?\b"` | Listed datasets with contextual usage (e.g. training, testing, federated learning). | "No specific dataset or corpus was identified in the selected passages." |
| **ALGORITHMS** | `r"\balgorithms?\b"`, `r"\bpseudocode\b"`, `r"\bcomputational\s+steps\b"` | Mathematical or algorithmic procedures, inputs, outputs, and complexity notes. | "No explicit pseudocode or named algorithm was found in the passages." |
| **SUMMARY** | `r"\bsummar(?:y\|ize)\b"`, `r"\boverview\b"` | 8-Section Structured Executive Summary (Problem, Objective, Background, Method, Setup, Findings, Limitations, Conclusion). | Omit sections lacking evidence or mark with transparent unavailable notice. |
| **DEFINITION** | `r"^\s*what\s+is\s+(?!an?\s+algorithm)[\w\s]{2,40}\??$"` | Direct definition quote, key properties, and context. | State clearly if paper uses the term without providing a general definition. |
| **FINDINGS** | `r"\b(?:key\s+)?findings?\b"`, `r"\bresults?\b"`, `r"\bchallenges?\b"` | Structured narrative of author findings with provenance. Distinguish original findings from cited literature. | "No explicit findings were reported in the retrieved text for this query." |
| **EXPLANATION** | `r"\bexplain\b"`, `r"\bhow\s+does\b"`, `r"\bwhy\b"` | Coherent prose paragraphs explaining mechanisms, principles, and impacts. | State what the text says vs what is unaddressed. |

---

## 3. Strict Conversational Scope & Follow-Up Rules

### The Follow-Up Ambiguity Flaw
Previously, any query with 12 words or less was treated as a follow-up to the prior user turn. This polluted fresh questions with earlier table requests.

### Authoritative Follow-Up Rules
A query shall be classified as a conversational follow-up **ONLY if it contains explicit continuation markers**:
- Pronouns referring to prior context: `"it"`, `"they"`, `"this method"`, `"these findings"`.
- Continuation adverbs: `"more in depth"`, `"further"`, `"elaborate"`, `"give an example of that"`, `"explain that simply"`.
- Explicit format shift: `"put that in a table"`, `"summarize those points"`.

If a query introduces a substantive subject (e.g. `"what is cyber security"`, `"who wrote this paper"`, `"what methodology did the authors use"`), it is an **independent research inquiry** and **MUST NOT** inherit the prior turn's format or keywords.

---

## 4. Evidence Extraction & Noise Rejection Policy

### A. Publication Header and Footer Rejection
Every chunk retrieved from SQLite FTS5 must pass through a header-stripping normalizer before fact extraction or display:
- **Journal Banner Headers:** Lines matching `r"International Journal of..."`, `r"Volume \d+.*ISSN.*"`, `r"DOI:10.*"`, `r"www\.\w+\.com"` must be stripped.
- **Running Footers:** Page numbers and copyright notices must not be treated as body text.

### B. Validated Numerical Metrics vs Isolated Digits
A number is valid as a research metric **ONLY IF**:
1. It is accompanied by a recognized unit (`%`, `ms`, `fps`, `Gbps`, `F1`, `accuracy`, `parameters`), OR
2. It occurs in a verified metric context (e.g. `"outperformed baselines by 14.2%"`).
**Strict Prohibition:** Standalone integers representing section numbers (`"4. RESEARCH METHODOLOGY"` -> `4`) or page numbers (`"112"`) must never be extracted as numerical findings.

---

## 5. Scholarly Citation Format Contract

Each cited evidence point must render with authoritative provenance:

### Primary Academic Format
`[Author et al., Year, PDF p. X]`  
Example: `[Hassan et al., 2025, PDF p. 2]`

### Printed Pagination Option (when verified from journal header)
`[Hassan et al., 2025, PDF p. 2 / printed p. 113]`

### Fallback (when authors are genuinely absent)
`["Title of Document", Year, PDF p. X]`  
Example: `["Advances in Cybersecurity", 2025, PDF p. 1]`

**Forbidden in User-Facing Answers:**
- Naked indices: `[S1]`, `[S2]`
- Internal database IDs: `[paper_5d009428-7a4c...]`
- User project aliases: `["cyber", p. 2]`


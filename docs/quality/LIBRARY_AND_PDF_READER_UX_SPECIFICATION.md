# ResearchLens: Library & PDF Reader UX Specification
**Document Reference:** `RL-SPEC-LIBRARY-005`  
**Status:** Approved & Enforced  
**Classification:** Document Intelligence & Reader Integration  

---

## 1. Overview

The Library and PDF Reader interface transforms raw uploaded PDFs into a structured, searchable, and citation-ready scholarly repository. Following Mendeley and Zotero desktop paradigms, the library displays authoritative academic metadata (authors, year, venue, DOI) rather than bare file names.

---

## 2. Library Table Specification

```
+───────────────────────────────────────────────────────────────────────────────────────────────+
| Research Library (2 Papers Indexed · 4,355 Chunks)                     [+ Add Sources]        |
+───────────────────────────────────────────────────────────────────────────────────────────────+
| Title                           | Authors               | Year | Venue             | Status   |
+─────────────────────────────────+───────────────────────+──────+───────────────────+──────────+
| Advances in Cybersecurity:      | Hassan, Hadullo,      | 2025 | Int. J. Computer  | Indexed  |
| A Literature Review             | & Tole                |      | App. Tech. & Res. | (19 ch.) |
+─────────────────────────────────+───────────────────────+──────+───────────────────+──────────+
| Introduction to Algorithms,     | Cormen, Leiserson,    | 2009 | The MIT Press     | Indexed  |
| Third Edition                   | Rivest, & Stein       |      |                   | (4336 ch)|
+─────────────────────────────────+───────────────────────+──────+───────────────────+──────────+
```

### 2.1 Metadata Resolution
When documents are uploaded or indexed:
1. **Title Block Extraction:** The ingestion pipeline inspects page 1 text to extract authoritative titles, author clusters, and publication years.
2. **Metadata Fallback Hierarchy:** If manual metadata is provided in PostgreSQL, it takes authoritative precedence over heuristic title-page parsing.
3. **Chunk Count Indicator:** Displays exact indexed chunk count per document.

---

## 3. Authenticated PDF Reader Integration

### 3.1 Deep Linking & Page Navigation
Clicking any `CitationBadge` (e.g., `[Hassan et al., 2025, p. 2]`) or clicking a document row in the Library activates the authenticated PDF reader:

- **Endpoint:** `/api/v1/documents/{document_id}/file` (protected by JWT Bearer token).
- **Blob Streaming:** `openAuthenticatedPdfSource` fetches the file as an authenticated blob URL, preventing 401 unauthorized errors in native browser PDF readers.
- **Deep-Link URL Fragment:** The reader automatically appends `#page=X`, scrolling directly to the cited page.

### 3.2 Evidence Inspector Co-Location
In split-view mode:
- Left Pane: PDF reader rendering the original document layout.
- Right Pane: Cited passage excerpt, section label, and confidence score, enabling instantaneous researcher verification.


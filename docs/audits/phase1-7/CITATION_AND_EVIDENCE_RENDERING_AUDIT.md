# CITATION AND EVIDENCE RENDERING AUDIT
## Resolution of Top Toolbar Evidence Desynchronization and Academic Citation Format

**Date:** November 12, 2026  
**System:** ResearchLens Academic Research Assistant  
**Author:** Principal Software Architect & QA Architect  
**Status:** Audited, Resolved & Verified ✅

---

## 1. Problem Statement

### Observed Flaws in Localhost
1. **Evidence (0) Toolbar Desynchronization:** An assistant response in the Research Desk chat indicated six sources cited (`6 sources cited`), yet the top toolbar toggle persistently displayed `Evidence (0)`.
2. **Generic Source Tags (S1, S2):** Citation badges rendered literal alphanumeric index tags (`S1`, `S2`) rather than standard academic citation references (`[Author et al., Year, p. X]`).

---

## 2. Root Cause Analysis

### A. Evidence (0) Toolbar Desynchronization
In `frontend/src/components/chat/ThreePaneChatWorkbench.jsx`:
- Line 457 rendered: `<span>Evidence ({sources.length})</span>`.
- `sources` was read from `useCitationStore()`.
- On switching conversations or loading the Research Desk, `useEffect` called `clearSources()`, resetting `sources` to `[]`.
- The synchronization effect (lines 158–173) was gated behind `lastAssistantMsg.id !== lastSyncedMsgIdRef.current` and evaluated only when messages finished loading and were non-pending.
- When messages were loaded from cache or streaming finished, `lastSyncedMsgIdRef.current` prevented `setSources()` from being dispatched, leaving the citation store empty (`sources.length === 0`).
- The toolbar button thus rendered `Evidence (0)`.

### B. Generic Source Tags (S1, S2)
In `frontend/src/components/citations/CitationBadge.jsx`:
- Line 58 rendered: `{sourceId}`.
- Neither `SourceCitation` nor the backend API schema emitted a human-readable academic citation label.
- As a result, the badge displayed the raw chunk identifier `S1`, `S2` instead of authoritative scholarly citations.

---

## 3. Engineering Fixes

### A. Reactive Evidence Toolbar Counter
In `frontend/src/components/chat/ThreePaneChatWorkbench.jsx`:
1. Introduced a reactive `useMemo` aggregation across the entire message history:
   ```javascript
   const conversationSources = useMemo(() => {
     return aggregateConversationSources(messages);
   }, [messages]);

   const activeEvidenceCount = conversationSources.length > 0 ? conversationSources.length : sources.length;
   ```
2. Connected `conversationSources` directly to `setSources`:
   ```javascript
   useEffect(() => {
     if (conversationSources.length > 0) {
       setSources(conversationSources);
     }
   }, [conversationSources, setSources]);
   ```
3. Updated the desktop and mobile toolbar counters to read `activeEvidenceCount`:
   ```javascript
   <PanelRight className="h-3.5 w-3.5" />
   <span>Evidence ({activeEvidenceCount})</span>
   ```
**Result:** The Evidence count is now strictly reactive and synchronized with every turn.

### B. Academic Citation Label Formatter
In `rag/citations/citation_mapper.py`, implemented `format_citation_label()`:
```python
def format_citation_label(
    authors: Optional[List[str]] = None,
    year: Optional[Any] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    title: Optional[str] = None,
    source_id: Optional[str] = None,
) -> str:
    # 1 author:  [Vance, 2025, p. 1]
    # 2 authors: [Vance & Chen, 2025, p. 1]
    # 3+ authors:[Vance et al., 2025, pp. 1-2]
    # Title only:[“Computer Science”, p. 4]
    ...
```

### C. Citation Metadata Contract
Extended `SourceCitation` (`rag/citations/citation_mapper.py`), `RAGResult.to_api_dict()` (`rag/citations/citation_formatter.py`), and `Source` (`backend/app/schemas/citation.py`) to guarantee the full citation contract:
- `source_id`: Alphanumeric link identifier (e.g. `"S1"`)
- `citation_label`: Formatted academic label (e.g. `"[Cormen & Leiserson, 2022, p. 38]"`)
- `paper_id`: Authoritative Paper UUID
- `document_id`: Ingested document UUID
- `chunk_id`: Deterministic chunk identifier
- `author_metadata`: List of author names
- `paper_title`: Authoritative research title
- `publication_year`: Integer publication year
- `original_page_number`: Integer starting page
- `page_start`: Integer starting page
- `page_end`: Integer ending page
- `section_label`: Section header (e.g. `"Methodology"`)
- `evidence_excerpt`: Verbatim text passage
- `text_offset_start`: Integer start offset
- `text_offset_end`: Integer end offset

### D. Frontend Citation Badge Rendering
In `frontend/src/components/citations/CitationBadge.jsx`:
- The badge button now displays `matchedSource?.citation_label || [${sourceId}]`.
- The hover tooltip renders the academic citation label, author list, paper title, section badge, and italicized verbatim excerpt.
- Clicking the badge scrolls to the source passage in the evidence inspector and opens the authenticated PDF viewer.

---

## 4. Verification Results

| Test Scenario | Input Query / Context | Output Citation Label | Evidence Count | Result |
|---|---|---|---|---|
| Cormen Algorithms | "what is an algorithm" | `[Cormen & Leiserson, 2022, pp. 791-793]` | `Evidence (3)` | PASS ✅ |
| Tabular Findings | "Present the relevant findings in a concise table with citations" | `[Cormen & Leiserson, 2022, p. 38]` | `Evidence (2)` | PASS ✅ |
| Paper Summary | "give me the summary" | `["cyber", pp. 2-3]` | `Evidence (5)` | PASS ✅ |
| Multi-Turn Follow-Up | "Explain in more depth" | `[Cormen & Leiserson, 2022, p. 38]` | `Evidence (5)` | PASS ✅ |

All automated unit tests for citation contract (`test_03_academic_citation_label_formatting`, `test_04_citation_mapper_metadata_contract`) and workbench synchronization passed.


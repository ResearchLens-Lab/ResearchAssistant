# Citations, Provenance & Result Formatting

**Path**: `rag/citations/`

## Purpose
Guarantees source provenance from the final answer back to the exact chunk, page, section, and paper in the vector store. Eliminates hallucinated citations.

## Provenance Chain

```
Answer Claim with [S1]
        ↓
CitationMapper (verifies S1 against retrieved chunks)
        ↓
SourceCitation (contains chunk_id, paper_id, document_id, page_start, page_end, section, text, score)
        ↓
RAGResult (returned to FastAPI backend / Next.js UI)
```

## Key Components

### 1. `source_tracker.py`
`SourceTracker`: Maintains an indexed registry of retrieved sources by `source_id` (`S1`, `S2`) and `chunk_id`.

### 2. `citation_mapper.py`
`CitationMapper`: Validates all citation tags extracted from the generated text against real retrieved sources, discarding ungrounded or fabricated citation numbers.

### 3. `citation_formatter.py`
- `SourceCitation`: Typed model for individual supporting evidence.
- `RAGResult`: High-level container (`answer`, `sources: List[SourceCitation]`, `paper_ids`, `metadata`).
  - `to_api_dict()`: Converts to the exact backend JSON schema expected by Abhay's backend and Himanshu's frontend.
  - `to_markdown()`: Generates human-readable markdown with citation footnotes.

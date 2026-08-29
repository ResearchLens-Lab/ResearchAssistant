# Section-Aware Document Chunking

**Path**: `rag/chunking/`

## Purpose
Academic papers contain dense structural context. Chunking must never cut arbitrarily across section boundaries or lose page traceability.

## Key Components

### 1. `metadata.py`
Defines `ChunkMetadata` and `DocumentChunk`:
- `chunk_id`: Deterministic ID formatted as `{paper_id}_c{chunk_index:04d}_p{page_start}-{page_end}`.
- `paper_id`: Identifier of the paper.
- `document_id`: Identifier of the source document.
- `page_start` & `page_end`: Exact page range spanning the chunk.
- `section`: Academic section title (e.g., Abstract, Introduction, Methodology, Results).
- `token_count`: Estimated word/token length.
- `title`: Paper title for fast citation generation.

### 2. `strategies.py`
`SectionAwareChunkingStrategy`:
- Chunks each academic section independently to prevent semantic bleeding.
- Uses sliding window with configurable overlap (`chunk_size=500`, `chunk_overlap=80`).
- Cross-references page offsets against character indices to record the exact starting and ending pages for each chunk.

### 3. `chunker.py`
High-level `DocumentChunker` orchestrating strategy execution and validating non-empty chunk outputs.

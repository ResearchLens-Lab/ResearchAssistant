# Document Ingestion & Normalization

**Path**: `rag/ingestion/`

## Purpose
The ingestion layer extracts and standardizes raw inputs into structured `NormalizedDocument` representations while strictly retaining page boundaries and academic sections.

## Key Components

### 1. `document_loader.py`
- `BaseDocumentLoader`: Abstract interface.
- `PDFDocumentLoader`: Extracts text page-by-page using `pypdf`, preserving exact 1-indexed page numbers.
- `TextDocumentLoader`: Parses markdown, text, or page break markers (`\f` or `--- Page N ---`).
- `DocumentLoaderFactory`: Automatic loader resolution by file extension (`.pdf`, `.txt`, `.md`).

### 2. `document_normalizer.py`
Converts raw page streams into structured models:
- `Page`: `page_number: int`, `text: str`.
- `Section`: `name: str`, `page_start: int`, `page_end: int`, `text: str`.
- `DocumentMetadata`: `paper_id: str`, `document_id: str`, `title: str`, `authors: List[str]`, `year: Optional[int]`, `doi: Optional[str]`.
- `NormalizedDocument`: `document_id`, `paper_id`, `title`, `authors`, `year`, `pages`, `sections`, `metadata`.

### 3. `metadata_mapper.py`
Standardizes user metadata dictionaries and generates deterministic fallbacks for missing identifiers.

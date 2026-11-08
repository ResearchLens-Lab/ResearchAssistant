# Document Ingestion & Normalization

**Path**: `rag/ingestion/`

## Purpose
The ingestion layer extracts and standardizes raw inputs into structured `NormalizedDocument` representations while strictly retaining page boundaries and academic sections.

## Key Components

### 1. `document_loader.py`
- `BaseDocumentLoader`: Abstract interface.
- `PDFDocumentLoader`: Extracts text page-by-page using `pypdf`, preserving exact 1-indexed page numbers.
- `TextDocumentLoader`: Parses markdown, text, or page break markers (`\f` or `--- Page N ---`).
- `DOCXDocumentLoader`, `CSVDocumentLoader`, `XLSXDocumentLoader`, `PPTXDocumentLoader`, `HTMLDocumentLoader`, and `JSONDocumentLoader`: retain useful structure for their supported formats. XLSX reads cached cell values only (`data_only=True`); it does not execute formulas or macros. PPTX extracts slide text and tables without executing embedded content.
- `DocumentLoaderFactory`: Automatic loader resolution for PDF, DOCX, TXT, Markdown, CSV, XLSX, PPTX, HTML, and JSON. XLS/XLSM and scanned-PDF OCR are not supported.

XLSX citations retain sheet and row ranges; PPTX citations retain slide numbers. CSV citations retain row ranges. Non-PDF files do not receive fabricated PDF page numbers.

### 2. `document_normalizer.py`
Converts raw page streams into structured models:
- `Page`: `page_number: int`, `text: str`.
- `Section`: `name: str`, `page_start: int`, `page_end: int`, `text: str`.
- `DocumentMetadata`: `paper_id: str`, `document_id: str`, `title: str`, `authors: List[str]`, `year: Optional[int]`, `doi: Optional[str]`.
- `NormalizedDocument`: `document_id`, `paper_id`, `title`, `authors`, `year`, `pages`, `sections`, `metadata`.

### 3. `metadata_mapper.py`
Standardizes user metadata dictionaries and generates deterministic fallbacks for missing identifiers.

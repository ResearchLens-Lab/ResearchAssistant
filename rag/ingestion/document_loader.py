"""
Document loaders for PDF, Markdown, and Text research papers.
Preserves page-level structure, equations, tables, and line integrity.
"""

import os
import re
import csv
import json
from html.parser import HTMLParser
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import Counter

from rag.ingestion.document_normalizer import Page, NormalizedDocument, DocumentMetadata, DocumentNormalizer, Section
from rag.ingestion.metadata_mapper import MetadataMapper
from rag.ingestion.preflight import PDFPreflightAnalyzer, DocumentCategory
from rag.ingestion.ocr_engine import LocalOCREngine
from rag.ingestion.structure_extractor import StructureExtractor

logger = logging.getLogger(__name__)


def _parallel_ocr_worker(args: tuple) -> tuple:
    file_path, page_num, dpi = args
    import pymupdf
    from rag.ingestion.ocr_engine import LocalOCREngine
    engine = LocalOCREngine(default_dpi=dpi)
    with pymupdf.open(str(file_path)) as doc:
        p = doc[page_num - 1]
        res = engine.ocr_page(p, page_num, dpi=dpi)
        return page_num, res.text or "", res.confidence


class BaseDocumentLoader(ABC):
    """
    Abstract interface for document loaders.
    """

    @abstractmethod
    def load(self, file_path: str, metadata: Optional[Dict[str, Any]] = None, progress_callback=None, cancel_event=None) -> NormalizedDocument:
        """
        Loads document from file_path and returns a NormalizedDocument.
        """
        pass


class PDFDocumentLoader(BaseDocumentLoader):
    """
    Extracts text from PDFs page by page using PyMuPDF, retaining the source page
    numbers used by citations. PyMuPDF avoids pypdf's Python-level parsing cost
    on large, image-heavy research PDFs.
    """

    def __init__(self, normalizer: Optional[DocumentNormalizer] = None):
        self.normalizer = normalizer or DocumentNormalizer()

    @staticmethod
    def _filter_repeated_headers_footers(pages: List[Page]) -> List[Page]:
        """Filter out repeating page headers, running heads, and footers across pages."""
        if len(pages) < 2:
            return pages
        first_lines = []
        last_lines = []
        for p in pages:
            lines = [line.strip() for line in p.text.split("\n") if line.strip()]
            if lines:
                first_lines.extend(lines[:3])
                last_lines.extend(lines[-3:])
        threshold = 2 if len(pages) == 2 else max(2, int(len(pages) * 0.45))
        rep_headers = {l for l, c in Counter(first_lines).items() if c >= threshold and len(l) < 120}
        rep_footers = {l for l, c in Counter(last_lines).items() if c >= threshold and len(l) < 120}
        page_num_pat = re.compile(r"^(?:page\s+)?[-–—]?\s*\d+\s*[-–—]?(?:\s*of\s*\d+)?$", re.IGNORECASE)

        cleaned = []
        for p in pages:
            lines = p.text.split("\n")
            out = []
            for i, line in enumerate(lines):
                s = line.strip()
                if not s:
                    out.append(line)
                    continue
                if s in rep_headers and i < 3:
                    continue
                if s in rep_footers and i >= len(lines) - 3:
                    continue
                if page_num_pat.match(s) and (i < 2 or i >= len(lines) - 2):
                    continue
                out.append(line)
            cleaned.append(
                Page(
                    page_number=p.page_number,
                    text="\n".join(out),
                    is_ocr=getattr(p, "is_ocr", False),
                    ocr_confidence=getattr(p, "ocr_confidence", None),
                )
            )
        return cleaned

    def load(self, file_path: str, metadata: Optional[Dict[str, Any]] = None, progress_callback=None, cancel_event=None) -> NormalizedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        meta = MetadataMapper.map_metadata(
            raw_metadata=metadata,
            file_path=str(path.absolute()),
        )

        pages: List[Page] = []
        structured_sections: List[Section] = []

        try:
            import pymupdf

            # 1. Preflight Analysis
            if progress_callback:
                progress_callback({"stage": "inspecting", "progress": 5, "progress_type": "estimated"})

            preflight_analyzer = PDFPreflightAnalyzer()
            preflight = preflight_analyzer.analyze(str(path))

            if preflight.category == DocumentCategory.PASSWORD_PROTECTED:
                raise ValueError("PDF is password-protected and cannot be opened without a password.")
            if preflight.category == DocumentCategory.CORRUPT:
                raise ValueError(f"Corrupt or unreadable PDF: {preflight.preflight_error or 'Unknown parsing error'}")

            ocr_engine = LocalOCREngine()
            ocr_needed_pages = set(preflight.pages_requiring_ocr)

            # Checkpoint file for resilient resumption across application restarts
            doc_id = (metadata or {}).get("document_id") or path.stem
            file_hash = (metadata or {}).get("file_hash")
            if not file_hash and path.is_file():
                try:
                    import hashlib
                    h = hashlib.sha256()
                    with path.open("rb") as f_in:
                        h.update(f_in.read(2 * 1024 * 1024))
                        h.update(str(path.stat().st_size).encode("utf-8"))
                    file_hash = h.hexdigest()
                except Exception:
                    file_hash = None

            checkpoint_file = path.parent / f".ocr-{doc_id}.json"
            hash_checkpoint_file = path.parent / f".ocr-{file_hash}.json" if file_hash else None
            saved_ocr_pages: Dict[str, Dict[str, Any]] = {}

            # 1. Check doc_id checkpoint
            if checkpoint_file.is_file():
                try:
                    saved_ocr_pages = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                    logger.info("Resumed %d cached OCR pages from checkpoint for %s", len(saved_ocr_pages), doc_id)
                except Exception as exc:
                    logger.warning("Could not read OCR checkpoint for %s: %s", doc_id, exc)

            # 2. Check file_hash checkpoint
            if not saved_ocr_pages and hash_checkpoint_file and hash_checkpoint_file.is_file():
                try:
                    saved_ocr_pages = json.loads(hash_checkpoint_file.read_text(encoding="utf-8"))
                    logger.info("Resumed %d cached OCR pages from hash checkpoint for %s", len(saved_ocr_pages), file_hash)
                except Exception as exc:
                    logger.warning("Could not read hash OCR checkpoint for %s: %s", file_hash, exc)

            def _save_checkpoint_atomic(data: dict) -> None:
                tmp_file = checkpoint_file.parent / f"{checkpoint_file.name}.tmp"
                try:
                    tmp_file.write_text(json.dumps(data), encoding="utf-8")
                    os.replace(tmp_file, checkpoint_file)
                    if hash_checkpoint_file:
                        try:
                            hash_checkpoint_file.write_text(json.dumps(data), encoding="utf-8")
                        except Exception:
                            pass
                except Exception as exc:
                    logger.debug("Checkpoint write notice: %s", exc)
                    if tmp_file.is_file():
                        tmp_file.unlink(missing_ok=True)

            with pymupdf.open(str(path)) as reader:
                if reader.is_encrypted and not reader.authenticate(""):
                    raise ValueError("PDF is password-protected and cannot be opened without a password.")
                if meta.title == "Untitled Research Paper":
                    title = (reader.metadata or {}).get("title")
                    if title:
                        meta.title = str(title)

                page_count = len(reader)

                # Fast parallel extraction for uncached OCR pages across CPU cores
                uncached_ocr_indices = [idx for idx in sorted(ocr_needed_pages) if str(idx) not in saved_ocr_pages]
                if len(uncached_ocr_indices) > 2 and ocr_engine.is_available():
                    chunk_size = min(12, max(4, len(uncached_ocr_indices)))
                    max_workers = min(4, os.cpu_count() or 4)
                    try:
                        from concurrent.futures import ProcessPoolExecutor, as_completed
                        with ProcessPoolExecutor(max_workers=max_workers) as executor:
                            tasks = [(str(path), p_idx, ocr_engine.default_dpi) for p_idx in uncached_ocr_indices]
                            for i in range(0, len(tasks), chunk_size):
                                if cancel_event is not None and cancel_event.is_set():
                                    _save_checkpoint_atomic(saved_ocr_pages)
                                    raise RuntimeError("Ingestion cancelled during extraction.")
                                batch = tasks[i:i + chunk_size]
                                futures = [executor.submit(_parallel_ocr_worker, item) for item in batch]
                                for fut in as_completed(futures):
                                    p_num, p_text, p_conf = fut.result()
                                    saved_ocr_pages[str(p_num)] = {"text": p_text, "confidence": p_conf}
                                _save_checkpoint_atomic(saved_ocr_pages)
                                if progress_callback:
                                    completed_count = min(len(saved_ocr_pages), page_count)
                                    progress_val = min(50, max(10, round(10 + 40 * completed_count / max(page_count, 1))))
                                    progress_callback({
                                        "stage": "ocr_processing",
                                        "progress": progress_val,
                                        "progress_type": "actual",
                                        "completed_pages": completed_count,
                                        "total_pages": page_count,
                                    })
                    except Exception as mp_exc:
                        logger.info("ProcessPool OCR notice (%s); proceeding with serial fallback", mp_exc)

                for idx, pdf_page in enumerate(reader, start=1):
                    if cancel_event is not None and cancel_event.is_set():
                        # Save current progress to checkpoint atomically before aborting
                        _save_checkpoint_atomic(saved_ocr_pages)
                        raise RuntimeError("Ingestion cancelled during extraction.")

                    # Check if page needs OCR
                    if idx in ocr_needed_pages and ocr_engine.is_available():
                        page_key = str(idx)
                        if page_key in saved_ocr_pages:
                            cached = saved_ocr_pages[page_key]
                            pages.append(
                                Page(
                                    page_number=idx,
                                    text=cached.get("text", "") or "",
                                    is_ocr=True,
                                    ocr_confidence=cached.get("confidence", 0.9),
                                )
                            )
                        else:
                            ocr_res = ocr_engine.ocr_page(pdf_page, idx)
                            pages.append(
                                Page(
                                    page_number=idx,
                                    text=ocr_res.text or "",
                                    is_ocr=True,
                                    ocr_confidence=ocr_res.confidence,
                                )
                            )
                            saved_ocr_pages[page_key] = {
                                "text": ocr_res.text or "",
                                "confidence": ocr_res.confidence,
                            }
                            # Checkpoint every 5 pages or on final page
                            if idx % 5 == 0 or idx == page_count:
                                _save_checkpoint_atomic(saved_ocr_pages)

                        if progress_callback and (idx == 1 or idx % 2 == 0 or idx == page_count):
                            progress_val = min(50, max(10, round(10 + 40 * min(idx, page_count) / max(page_count, 1))))
                            progress_callback({
                                "stage": "ocr_processing",
                                "progress": progress_val,
                                "progress_type": "actual",
                                "completed_pages": min(idx, page_count),
                                "total_pages": page_count,
                            })
                    else:
                        page_text = pdf_page.get_text("text") or ""
                        pages.append(Page(page_number=idx, text=page_text, is_ocr=False))

                        if progress_callback and (idx == 1 or idx % 10 == 0 or idx == page_count):
                            progress_val = min(30, max(5, round(5 + 25 * min(idx, page_count) / max(page_count, 1))))
                            progress_callback({
                                "stage": "extracting_text",
                                "progress": progress_val,
                                "progress_type": "estimated",
                                "completed_pages": min(idx, page_count),
                                "total_pages": page_count,
                            })

                if not any(page.text.strip() for page in pages):
                    if not ocr_engine.is_available():
                        raise ValueError("PDF contains no extractable text; scanned PDFs require OCR, which is not enabled.")
                    raise ValueError("PDF contains no extractable text even after OCR processing.")

                pages = self._filter_repeated_headers_footers(pages)

                # Structure & Outline Extraction
                if progress_callback:
                    progress_callback({"stage": "structuring", "progress": 25, "progress_type": "estimated"})

                try:
                    extractor = StructureExtractor()
                    sec_nodes = extractor.extract_structure(reader, [(p.page_number, p.text) for p in pages])
                    for s_node in sec_nodes:
                        sec_pages = [p for p in pages if s_node.page_start <= p.page_number <= s_node.page_end]
                        is_sec_ocr = any(getattr(p, "is_ocr", False) for p in sec_pages) if sec_pages else False
                        sec_conf = (
                            sum(getattr(p, "ocr_confidence", 1.0) or 1.0 for p in sec_pages) / max(1, len(sec_pages))
                            if sec_pages and is_sec_ocr else 1.0
                        )
                        structured_sections.append(
                            Section(
                                name=s_node.title,
                                page_start=s_node.page_start,
                                page_end=s_node.page_end,
                                text=s_node.raw_text,
                                extra={
                                    "heading_path": s_node.heading_path,
                                    "section_type": s_node.section_type.value,
                                    "page_label_start": s_node.page_label_start,
                                    "page_label_end": s_node.page_label_end,
                                    "extraction_method": "ocr" if is_sec_ocr else "native",
                                    "extraction_confidence": round(sec_conf, 3),
                                },
                            )
                        )
                except Exception as struct_err:
                    logger.warning("Structure extraction exception; falling back to normalizer: %s", struct_err)

        except Exception as e:
            logger.error("Failed to load PDF exception_type=%s", type(e).__name__)
            if isinstance(e, ValueError):
                raise
            raise RuntimeError(f"Could not read this PDF ({type(e).__name__}). Check that it is a valid, unencrypted PDF.") from e

        if structured_sections:
            return NormalizedDocument(
                document_id=meta.document_id,
                paper_id=meta.paper_id,
                owner_id=meta.owner_id,
                title=meta.title,
                authors=meta.authors,
                year=meta.year,
                pages=pages,
                sections=structured_sections,
                metadata=meta,
            )

        return self.normalizer.normalize(pages=pages, metadata=meta)


class TextDocumentLoader(BaseDocumentLoader):
    """
    Loads plain text, markdown, or research paper fixtures.
    Supports optional page-break markers (e.g., '--- Page 2 ---' or '\f' form feeds).
    """

    def __init__(self, normalizer: Optional[DocumentNormalizer] = None):
        self.normalizer = normalizer or DocumentNormalizer()

    def load(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> NormalizedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path.suffix or 'Unknown'} file is not valid UTF-8 text.") from exc
        if not content.strip():
            raise ValueError(f"{path.name} contains no extractable text.")
        return self.load_text(content=content, metadata=metadata, file_path=str(path.absolute()))

    def load_text(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> NormalizedDocument:
        if not file_path and metadata and not metadata.get("source_format"):
            metadata = {**metadata, "source_format": "text"}
        meta = MetadataMapper.map_metadata(
            raw_metadata=metadata,
            file_path=file_path,
        )

        pages: List[Page] = []
        # Check for explicit form feed page breaks or comment markers
        if "\f" in content:
            raw_pages = content.split("\f")
            for idx, p_text in enumerate(raw_pages, start=1):
                pages.append(Page(page_number=idx, text=p_text))
        elif re.search(r"<!--\s*page:\s*(\d+)\s*-->|---+\s*page\s*(\d+)\s*---+", content, re.IGNORECASE):
            parts = re.split(r"<!--\s*page:\s*\d+\s*-->|---+\s*page\s*\d+\s*---+", content, flags=re.IGNORECASE)
            page_num = 1
            for part in parts:
                if part.strip():
                    pages.append(Page(page_number=page_num, text=part))
                    page_num += 1
        else:
            # Split approximately every 500 words or preserve as single page if small
            paragraphs = content.split("\n\n")
            current_page_text: List[str] = []
            current_word_count = 0
            page_num = 1

            for para in paragraphs:
                words = len(para.split())
                if current_word_count + words > 500 and current_page_text:
                    pages.append(Page(page_number=page_num, text="\n\n".join(current_page_text)))
                    page_num += 1
                    current_page_text = [para]
                    current_word_count = words
                else:
                    current_page_text.append(para)
                    current_word_count += words

            if current_page_text:
                pages.append(Page(page_number=page_num, text="\n\n".join(current_page_text)))

        if not pages:
            pages = [Page(page_number=1, text="")]

        return self.normalizer.normalize(pages=pages, metadata=meta)


class DocumentLoaderFactory:
    """
    Factory resolving the appropriate loader by file extension.
    """

    @staticmethod
    def get_loader(file_path: str) -> BaseDocumentLoader:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return PDFDocumentLoader()
        elif ext in {".txt", ".md", ".markdown", ".tex"}:
            return TextDocumentLoader()
        elif ext == ".docx":
            return DOCXDocumentLoader()
        elif ext == ".csv":
            return CSVDocumentLoader()
        elif ext == ".xlsx":
            return XLSXDocumentLoader()
        elif ext == ".pptx":
            return PPTXDocumentLoader()
        elif ext == ".json":
            return JSONDocumentLoader()
        elif ext in {".html", ".htm"}:
            return HTMLDocumentLoader()
        elif ext == ".zip":
            raise ValueError("ZIP archives must be expanded by the authenticated document upload service.")
        raise ValueError(f"Unsupported document format '{ext or 'unknown'}'. Supported: PDF, DOCX, TXT, Markdown, CSV, XLSX, PPTX, HTML, JSON.")


class DOCXDocumentLoader(BaseDocumentLoader):
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        try:
            from docx import Document as WordDocument
        except ImportError as exc:
            raise RuntimeError("DOCX support requires python-docx.") from exc
        path = Path(file_path)
        doc = WordDocument(str(path))
        blocks = []
        for para in doc.paragraphs:
            if para.text.strip():
                style = para.style.name if para.style else ""
                blocks.append((f"# {para.text.strip()}" if style.lower().startswith("heading") else para.text.strip()))
        for table in doc.tables:
            if not table.rows:
                continue
            headers = [cell.text.strip() or f"Column {i + 1}" for i, cell in enumerate(table.rows[0].cells)]
            blocks.append("Table columns: " + " | ".join(headers))
            for row_number, row in enumerate(table.rows[1:], start=2):
                blocks.append(f"Row {row_number}: " + "; ".join(
                    f"{headers[i]}: {cell.text.strip()}" for i, cell in enumerate(row.cells)
                ))

        # Extract OMML equations (from RAG-Anything technique)
        try:
            from rag.ingestion.omml_extractor import extract_omml_equations
            eqs = extract_omml_equations(str(path))
            if eqs:
                eq_text = "\n\n".join(f"$$\n{eq['text']}\n$$" for eq in eqs if eq.get("text", "").strip())
                if eq_text:
                    blocks.append(f"### Equations\n\n{eq_text}")
        except Exception as exc:
            logger.debug("DOCX OMML equation extraction skipped: %s", exc)

        text = "\n\n".join(blocks)
        if not text.strip():
            raise ValueError(f"{path.name} contains no extractable text.")
        return TextDocumentLoader().load_text(text, metadata, str(path.absolute()))


class CSVDocumentLoader(BaseDocumentLoader):
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        path = Path(file_path)
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        if not rows or not any(cell.strip() for row in rows for cell in row):
            raise ValueError(f"{path.name} contains no tabular data.")
        headers = rows[0]
        text = "\n".join(f"Row {i}: " + "; ".join(f"{h}: {v}" for h, v in zip(headers, row)) for i, row in enumerate(rows[1:], 2))
        return TextDocumentLoader().load_text(f"Columns: {' | '.join(headers)}\n\n{text or 'Headers only.'}", metadata, str(path.absolute()))


class XLSXDocumentLoader(BaseDocumentLoader):
    """Extract cached cell values only; formulas and macros are never executed."""
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX support requires openpyxl.") from exc
        path = Path(file_path)
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        pages = []
        for sheet_index, sheet in enumerate(workbook.worksheets, start=1):
            rows = list(sheet.iter_rows(values_only=True))
            nonempty = [(i, row) for i, row in enumerate(rows, start=1) if any(v is not None and str(v).strip() for v in row)]
            if not nonempty:
                continue
            header_row, header_values = nonempty[0]
            headers = [str(value).strip() if value is not None else f"Column {i}" for i, value in enumerate(header_values, start=1)]
            lines = [f"Sheet: {sheet.title}", "Columns: " + " | ".join(headers)]
            for row_num, values in nonempty[1:]:
                fields = [f"{headers[i]}: {value}" for i, value in enumerate(values) if value is not None and i < len(headers)]
                if fields:
                    lines.append(f"Row {row_num}: " + "; ".join(fields))
            pages.append(Page(page_number=sheet_index, text="\n".join(lines)))
        workbook.close()
        if not pages:
            raise ValueError(f"{path.name} contains no extractable cell values.")
        meta = MetadataMapper.map_metadata(metadata, file_path=str(path.absolute()))
        return DocumentNormalizer().normalize(pages, meta)


class PPTXDocumentLoader(BaseDocumentLoader):
    """Extract slide text and tables in shape order without running embedded code."""
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        try:
            from pptx import Presentation
        except ImportError as exc:
            raise RuntimeError("PPTX support requires python-pptx.") from exc
        path = Path(file_path)
        deck = Presentation(str(path))
        pages = []
        for slide_number, slide in enumerate(deck.slides, start=1):
            title_shape = slide.shapes.title
            title = title_shape.text.strip() if title_shape and title_shape.text.strip() else ""
            lines = [f"Slide {slide_number}: {title}" if title else f"Slide {slide_number}"]
            for shape in slide.shapes:
                if shape == title_shape:
                    continue
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    lines.append(shape.text.strip())
                if getattr(shape, "has_table", False):
                    table = shape.table
                    headers = [cell.text.strip() or f"Column {i + 1}" for i, cell in enumerate(table.rows[0].cells)]
                    lines.append("Table columns: " + " | ".join(headers))
                    for row_index, row in enumerate(table.rows[1:], start=2):
                        lines.append(f"Table row {row_index}: " + "; ".join(f"{headers[i]}: {cell.text.strip()}" for i, cell in enumerate(row.cells)))
            text = "\n".join(lines)
            if text.strip():
                pages.append(Page(page_number=slide_number, text=text))
        if not pages:
            raise ValueError(f"{path.name} contains no extractable slide text.")
        meta = MetadataMapper.map_metadata(metadata, file_path=str(path.absolute()))
        return DocumentNormalizer().normalize(pages, meta)


class JSONDocumentLoader(BaseDocumentLoader):
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        path = Path(file_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return TextDocumentLoader().load_text(json.dumps(data, ensure_ascii=False, indent=2), metadata, str(path.absolute()))


class HTMLDocumentLoader(BaseDocumentLoader):
    def load(self, file_path: str, metadata=None) -> NormalizedDocument:
        class TextExtractor(HTMLParser):
            def __init__(self): super().__init__(); self.parts=[]; self.hidden=0
            def handle_starttag(self, tag, attrs):
                if tag in {"script", "style", "noscript"}: self.hidden += 1
                if tag in {"p", "div", "h1", "h2", "h3", "li", "tr", "br"} and not self.hidden: self.parts.append("\n")
            def handle_endtag(self, tag):
                if tag in {"script", "style", "noscript"}: self.hidden=max(0,self.hidden-1)
            def handle_data(self, data):
                if not self.hidden and data.strip(): self.parts.append(data.strip())
        path=Path(file_path); parser=TextExtractor(); parser.feed(path.read_text(encoding="utf-8"))
        text="\n".join(parser.parts)
        if not text.strip(): raise ValueError(f"{path.name} contains no extractable text.")
        return TextDocumentLoader().load_text(text, metadata, str(path.absolute()))

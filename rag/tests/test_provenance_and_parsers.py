from pathlib import Path

import pytest

from rag.ingestion.document_loader import DocumentLoaderFactory
from rag.ingestion.document_normalizer import Page
from rag.chunking.strategies import SectionAwareChunkingStrategy


def test_pdf_page_ranges_survive_extractor_whitespace_changes():
    strategy = SectionAwareChunkingStrategy()
    pages = [Page(page_number=i, text=text) for i, text in enumerate(
        ["page one", "page two", "distinctive passage\nwith wrapped lines", "cross-page continuation"], 1
    )]
    offsets = strategy._build_page_index(pages)
    text = "\n\n".join(page.text for page in pages)
    assert strategy._find_page_range_for_text(text, "distinctive passage with wrapped lines", offsets, 1, 4) == (3, 3)
    assert strategy._find_page_range_for_text(text, "distinctive passage with wrapped lines cross-page continuation", offsets, 1, 4) == (3, 4)


def test_unsupported_binary_extension_is_rejected():
    with pytest.raises(ValueError, match="Unsupported document format"):
        DocumentLoaderFactory.get_loader("payload.exe")


def test_pdf_extraction_keeps_original_page_numbers_and_reports_ocr_requirement(tmp_path: Path):
    from pymupdf import Document as PdfDocument
    from rag.ingestion.document_loader import PDFDocumentLoader

    path = tmp_path / "multipage.pdf"
    with PdfDocument() as pdf:
        for content in ("", "Supporting evidence. " * 700, "Distinctive evidence on source page three."):
            page = pdf.new_page()
            if content:
                page.insert_text((72, 72), content)
        pdf.save(path)
    extraction_events = []
    document = PDFDocumentLoader().load(str(path), {"paper_id": "p", "document_id": "pdf", "owner_id": "test_owner"}, extraction_events.append)
    assert any(e.get("completed_pages") == 3 for e in extraction_events)
    assert any(e.get("total_pages") == 3 for e in extraction_events)
    assert any(e.get("stage") == "extracting_text" for e in extraction_events)
    assert [page.page_number for page in document.pages] == [1, 2, 3]
    chunks = SectionAwareChunkingStrategy().chunk(document)
    evidence_chunk = next(chunk for chunk in chunks if "Distinctive evidence" in chunk.text)
    assert evidence_chunk.metadata.page_start == 2
    assert evidence_chunk.metadata.page_end == 3

    scanned = tmp_path / "scanned.pdf"
    with PdfDocument() as pdf:
        pdf.new_page()
        pdf.save(scanned)
    with pytest.raises(ValueError, match="OCR"):
        PDFDocumentLoader().load(str(scanned), {"paper_id": "p", "document_id": "scanned", "owner_id": "test_owner"})


def test_large_pdf_is_extracted_pagewise_without_losing_page_provenance(tmp_path: Path):
    from pymupdf import Document as PdfDocument
    from rag.ingestion.document_loader import PDFDocumentLoader

    path = tmp_path / "many-pages.pdf"
    with PdfDocument() as pdf:
        for page_number in range(1, 251):
            page = pdf.new_page()
            page.insert_text((72, 72), f"Page marker source-page-{page_number:03d}. " + "Research text. " * 40)
        pdf.save(path)
    document = PDFDocumentLoader().load(str(path), {"paper_id": "p", "document_id": "large", "owner_id": "test_owner"})
    assert document.total_pages == 250
    assert "source-page-250" in document.pages[-1].text


def test_text_and_csv_loaders_preserve_source_filename(tmp_path: Path):
    text = tmp_path / "notes.md"
    text.write_text("# Findings\n\nEvidence appears here.", encoding="utf-8")
    doc = DocumentLoaderFactory.get_loader(str(text)).load(str(text), {"paper_id": "p", "document_id": "d", "owner_id": "test_owner"})
    assert doc.metadata.filename == "notes.md"
    assert "Evidence appears here" in doc.full_text

    csv = tmp_path / "results.csv"
    csv.write_text("metric,value\nrecall,0.91\n", encoding="utf-8")
    table_doc = DocumentLoaderFactory.get_loader(str(csv)).load(str(csv), {"paper_id": "p", "document_id": "csv", "owner_id": "test_owner"})
    assert "metric: recall" in table_doc.full_text


def test_xlsx_loader_preserves_sheet_columns_and_row_locator(tmp_path: Path):
    from openpyxl import Workbook
    path = tmp_path / "metrics.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Evaluation Results"
    sheet.append(["Metric", "Score"])
    sheet.append(["Recall@5", 0.91])
    workbook.save(path)
    doc = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "xlsx", "owner_id": "test_owner"})
    chunk = SectionAwareChunkingStrategy().chunk(doc)[0]
    assert "Sheet: Evaluation Results" in chunk.text
    assert "Metric: Recall@5" in chunk.text
    assert chunk.metadata.page_start is None
    assert "Sheet Evaluation Results" in chunk.metadata.locator
    assert "row 2" in chunk.metadata.locator


def test_pptx_loader_preserves_slide_title_and_locator(tmp_path: Path):
    from pptx import Presentation
    from pptx.util import Inches
    path = tmp_path / "findings.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Key Results"
    slide.shapes.add_textbox(Inches(1), Inches(2), Inches(5), Inches(1)).text_frame.text = "Accuracy reached 91 percent."
    deck.save(path)
    doc = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "pptx", "owner_id": "test_owner"})
    chunk = SectionAwareChunkingStrategy().chunk(doc)[0]
    assert "Slide 1: Key Results" in chunk.text
    assert "Accuracy reached 91 percent" in chunk.text
    assert chunk.metadata.page_start is None
    assert chunk.metadata.locator == "Slide 1"


def test_docx_loader_preserves_heading_and_table_row_locator(tmp_path: Path):
    from docx import Document
    path = tmp_path / "notes.docx"
    document = Document()
    document.add_heading("Methodology", level=1)
    document.add_paragraph("The study used a controlled evaluation.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Metric"
    table.rows[0].cells[1].text = "Value"
    row = table.add_row()
    row.cells[0].text = "Recall"
    row.cells[1].text = "0.91"
    document.save(path)
    normalized = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "docx", "owner_id": "test_owner"})
    assert any(section.name == "Methodology" for section in normalized.sections)
    chunks = SectionAwareChunkingStrategy().chunk(normalized)
    assert any("Metric: Recall" in chunk.text and "row 2" in chunk.metadata.locator.lower() for chunk in chunks)

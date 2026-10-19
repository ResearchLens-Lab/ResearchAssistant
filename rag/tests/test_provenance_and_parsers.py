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


def test_text_and_csv_loaders_preserve_source_filename(tmp_path: Path):
    text = tmp_path / "notes.md"
    text.write_text("# Findings\n\nEvidence appears here.", encoding="utf-8")
    doc = DocumentLoaderFactory.get_loader(str(text)).load(str(text), {"paper_id": "p", "document_id": "d"})
    assert doc.metadata.filename == "notes.md"
    assert "Evidence appears here" in doc.full_text

    csv = tmp_path / "results.csv"
    csv.write_text("metric,value\nrecall,0.91\n", encoding="utf-8")
    table_doc = DocumentLoaderFactory.get_loader(str(csv)).load(str(csv), {"paper_id": "p", "document_id": "csv"})
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
    doc = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "xlsx"})
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
    doc = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "pptx"})
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
    normalized = DocumentLoaderFactory.get_loader(str(path)).load(str(path), {"paper_id": "p", "document_id": "docx"})
    assert any(section.name == "Methodology" for section in normalized.sections)
    chunks = SectionAwareChunkingStrategy().chunk(normalized)
    assert any("Metric: Recall" in chunk.text and "row 2" in chunk.metadata.locator.lower() for chunk in chunks)

from pathlib import Path

import pytest

from rag.document_intelligence.extractor import DocumentIntelligenceExtractor
from rag.document_intelligence.store import ExtractionStore
from rag.ingestion.document_normalizer import DocumentMetadata, DocumentNormalizer, Page


def _doc(text: str, doc_id: str = "doc-fixture"):
    metadata = DocumentMetadata(paper_id="paper-fixture", document_id=doc_id, title="Fixture", filename="fixture.md", source_format="md", owner_id="test_user_fixture")
    return DocumentNormalizer().normalize([Page(page_number=1, text=text)], metadata)


def test_section_hierarchy_offsets_and_exact_evidence():
    text = "# Abstract\nWe demonstrate that the approach improves accuracy.\n## Methods\nWe propose a deterministic method.\n"
    result = DocumentIntelligenceExtractor().extract_normalized(_doc(text), file_type=".md")
    assert [s.classification for s in result.sections] == ["abstract", "methods"]
    assert result.sections[1].parent_section_id == result.sections[0].section_id
    record = next(r for r in result.knowledge_records if r.category == "claim")
    source = result.pages[record.page_number - 1]["text"]
    assert source[record.char_start:record.char_end] == record.exact_text
    assert record.review_status == "pending" and record.confidence < 1
    assert record.block_id in {b.block_id for b in result.blocks}


def test_plain_academic_headings_capture_abstract_and_keywords():
    text = "Abstract\nWe propose an approach for this task.\nKeywords: graphs, algorithms\nMethods\nWe use dynamic programming.\n"
    result = DocumentIntelligenceExtractor().extract_normalized(_doc(text))
    assert result.abstract and "We propose" in result.abstract
    assert result.keywords == ["graphs", "algorithms"]
    assert [section.classification for section in result.sections] == ["abstract", "methods"]


def test_references_and_citation_are_unverified_and_linked():
    text = "# Introduction\nPrior work supports this [1].\n# References\n[1] Ada Author. “Reliable Systems.” Journal of Tests, 2021. https://example.org/paper\n"
    result = DocumentIntelligenceExtractor().extract_normalized(_doc(text))
    assert len(result.references) == 1
    ref = result.references[0]
    assert ref.cited_in_text is True
    assert ref.citation_pages == [1]
    assert ref.year == 2021 and ref.title == "Reliable Systems"
    assert ref.bibliographic_status == "parsed_unverified"
    assert result.citation_markers


def test_missing_pdf_text_reports_ocr_limitation():
    doc = _doc(" ")
    result = DocumentIntelligenceExtractor().extract_normalized(doc, file_type=".pdf")
    assert result.extraction_status == "needs_ocr"
    assert any("OCR is unavailable" in issue for issue in result.quality_issues)


def test_image_only_pdf_is_recorded_as_needs_ocr(tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "image_only.pdf"
    pdf = pymupdf.open()
    pdf.new_page(); pdf.new_page()
    pdf.save(path); pdf.close()
    result = DocumentIntelligenceExtractor().extract_file(path, "doc-scanned")
    assert result.extraction_status == "needs_ocr"
    assert result.page_count == 2
    assert all(not page["text"] for page in result.pages)


def test_idempotent_versioned_store_and_review_history(tmp_path: Path):
    text = "# Results\nResults show that performance improves.\n"
    result = DocumentIntelligenceExtractor().extract_normalized(_doc(text))
    store = ExtractionStore(tmp_path)
    path, created = store.save(result)
    assert created and path.exists()
    same, created_again = store.save(result)
    assert same == path and not created_again
    record = result.knowledge_records[0]
    event = store.review(result.document_id, result.run_id, record.record_id, "approve", "reviewer")
    loaded = store.get(result.document_id)
    assert event.action == "approve"
    assert next(r for r in loaded.knowledge_records if r.record_id == record.record_id).review_status == "approved"
    assert len(store.list_review_events(result.document_id)) == 1


def test_correction_requires_exact_source_match(tmp_path: Path):
    text = "# Results\nResults show that performance improves.\n"
    result = DocumentIntelligenceExtractor().extract_normalized(_doc(text))
    store = ExtractionStore(tmp_path)
    store.save(result)
    record = result.knowledge_records[0]
    with pytest.raises(ValueError, match="exactly match"):
        store.review(result.document_id, result.run_id, record.record_id, "correct", "reviewer",
                     {"exact_text": "invented evidence"})


def test_duplicate_paragraphs_have_position_distinct_stable_ids():
    text = "# Methods\nWe propose a method.\nWe propose a method.\n"
    extractor = DocumentIntelligenceExtractor()
    first = extractor.extract_normalized(_doc(text))
    second = extractor.extract_normalized(_doc(text))
    assert first.run_id == second.run_id
    assert len({r.record_id for r in first.knowledge_records}) == 2
    assert [r.record_id for r in first.knowledge_records] == [r.record_id for r in second.knowledge_records]


def test_docx_omml_adapter_preserves_equations_without_fabricated_page(monkeypatch, tmp_path: Path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "equation.docx"
    docx.Document().save(path)
    from rag.ingestion import omml_extractor
    monkeypatch.setattr(omml_extractor, "extract_omml_equations", lambda _: [
        {"index": 0, "text": r"x^2", "text_format": "latex", "raw_omml": "<m:oMath/>"}
    ])
    result = DocumentIntelligenceExtractor().extract_file(path, "doc-equation")
    assert len(result.equations) == 1
    assert result.equations[0].text == r"x^2"
    assert result.equations[0].page_number is None
    assert "document order only" in result.equations[0].position_status


def test_failed_run_does_not_replace_last_successful_pointer(tmp_path: Path):
    result = DocumentIntelligenceExtractor().extract_normalized(_doc("# Methods\nWe propose an approach.\n"))
    store = ExtractionStore(tmp_path)
    store.save(result)
    store.save_failure(result.document_id, "ValueError")
    assert store.get(result.document_id).run_id == result.run_id
    assert len(store.list_runs(result.document_id)) == 2

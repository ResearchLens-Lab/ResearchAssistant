from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from rag.document_intelligence.models import (
    DocumentBlock, DocumentIntelligence, EquationRecord, KnowledgeRecord, Position,
    ReferenceRecord, SectionRecord,
)
from rag.ingestion.document_loader import DocumentLoaderFactory
from rag.ingestion.document_normalizer import DocumentNormalizer, Page
from rag.ingestion.metadata_mapper import MetadataMapper


EXTRACTION_VERSION = "phase4-rules-1"
_CLASSIFIERS = [
    ("abstract", r"abstract|summary"), ("introduction", r"introduction|background"),
    ("related_work", r"related\s+work|literature\s+review|prior\s+work"),
    ("methods", r"method(?:ology|s)?|approach|algorithm|system\s+design|implementation"),
    ("experiments", r"experiments?|experimental\s+(?:setup|design)|evaluation"),
    ("results", r"results?|findings|performance"), ("discussion", r"discussion|analysis"),
    ("limitations", r"limitations?|threats\s+to\s+validity"),
    ("future_work", r"future\s+(?:work|research|directions?)"),
    ("conclusion", r"conclusions?|concluding\s+remarks"), ("references", r"references|bibliography"),
]
_KNOWLEDGE = {
    "research_question": r"\b(?:research question|we ask whether|this paper asks)\b",
    "objective": r"\b(?:aims? to|objective is|we seek to|goal of this (?:study|work))\b",
    "problem": r"\b(?:problem addressed|we address the problem|challenge is|problem of)\b",
    "definition": r"\b(?:is defined as|we define|refers to|denotes)\b",
    "method": r"\b(?:we propose|we present|our method|our approach|algorithm)\b",
    "model": r"\b(?:model|architecture)\s+(?:is|was|we)\b",
    "dataset": r"\b(?:dataset|data set|corpus)\b",
    "tool": r"\b(?:implemented using|using the|software|toolkit)\b",
    "metric": r"\b(?:accuracy|precision|recall|f1[- ]score|auc|bleu|rouge|metric)\b",
    "experimental_setting": r"\b(?:we evaluate|experiments? were conducted|experimental setup)\b",
    "finding": r"\b(?:results? show|we find that|our findings indicate|outperforms?)\b",
    "claim": r"\b(?:we demonstrate|we show that|we establish|we prove)\b",
    "limitation": r"\b(?:limitation|limited by|we do not address|future work)\b",
    "contribution": r"\b(?:contributions? (?:are|include)|we contribute|main contribution)\b",
    "conclusion": r"\b(?:in conclusion|we conclude|this work demonstrates)\b",
}


def _stable(prefix: str, *values: str) -> str:
    payload = "\0".join(values).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:20]}"


class DocumentIntelligenceExtractor:
    """Opt-in parser adapter. Offsets address each parser's normalized page text."""

    extraction_version = EXTRACTION_VERSION

    def extract_file(self, path: str | Path, document_id: str, paper_id: str | None = None,
                     private: bool = False) -> DocumentIntelligence:
        started = time.perf_counter()
        path = Path(path)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for batch in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(batch)
        content_hash = digest.hexdigest()
        metadata = {"document_id": document_id, "paper_id": paper_id or f"paper_{document_id}", "filename": path.name}
        try:
            normalized = DocumentLoaderFactory.get_loader(str(path)).load(str(path), metadata=metadata)
        except ValueError as exc:
            # The shared PDF loader correctly rejects image-only inputs for normal
            # indexing. For this opt-in extractor, turn only that known condition
            # into an explicit needs_ocr artifact without changing ingestion behavior.
            if path.suffix.lower() != ".pdf" or "scanned PDFs require OCR" not in str(exc):
                raise
            import pymupdf
            with pymupdf.open(str(path)) as pdf:
                blank_pages = [Page(page_number=i, text="") for i in range(1, len(pdf) + 1)]
            meta = MetadataMapper.map_metadata(metadata, file_path=str(path.absolute()))
            normalized = DocumentNormalizer().normalize(blank_pages, meta)
        result = self.extract_normalized(normalized, content_hash=content_hash, file_type=path.suffix.lower(), private=private)
        if path.suffix.lower() == ".docx":
            try:
                from rag.ingestion.omml_extractor import extract_omml_equations
                result.equations = [EquationRecord(
                    equation_id=_stable("eq", document_id, str(item["index"]), item["text"]),
                    text=item["text"], text_format=item.get("text_format", "latex"), structural_index=item["index"])
                    for item in extract_omml_equations(path) if item.get("text", "").strip()]
            except Exception as exc:
                result.quality_issues.append(f"DOCX equation extraction failed ({type(exc).__name__}); no equations were recorded.")
                if result.extraction_status == "complete": result.extraction_status = "partial"
        result.duration_seconds = round(time.perf_counter() - started, 6)
        return result

    def extract_normalized(self, doc, content_hash: str | None = None, file_type: str | None = None,
                           private: bool = False) -> DocumentIntelligence:
        started = time.perf_counter()
        page_dump = [{"page_number": page.page_number, "text": page.text} for page in doc.pages]
        if content_hash is None:
            content_hash = hashlib.sha256("\f".join(p["text"] for p in page_dump).encode()).hexdigest()
        run_id = _stable("run", doc.document_id, content_hash, EXTRACTION_VERSION)
        pages_by_num = {p["page_number"]: p["text"] for p in page_dump}
        nonempty = [(n, t) for n, t in pages_by_num.items() if t.strip()]
        quality: list[str] = []
        status = "complete"
        if not nonempty:
            status = "needs_ocr" if (file_type or "").lower() == ".pdf" else "partial"
            quality.append("No extractable page text; OCR is unavailable in the current parser path." if status == "needs_ocr" else "No extractable page text.")
        all_text = "\n".join(t for _, t in nonempty)
        if len(nonempty) < len(page_dump):
            quality.append(f"{len(page_dump) - len(nonempty)} page(s) contain no extracted text; page may be image-only.")
            if status == "complete": status = "partial"
        sections: list[SectionRecord] = []
        blocks: list[DocumentBlock] = []
        active: SectionRecord | None = None
        ref_mode = False
        refs: list[ReferenceRecord] = []
        markers: list[dict] = []
        records: list[KnowledgeRecord] = []
        abstract_lines: list[str] = []
        keyword_values: list[str] = []
        citation_to_pages: dict[str, set[int]] = {}
        for page_num, page_text in nonempty:
            offset = 0
            for raw_line in page_text.splitlines(keepends=True):
                visible = raw_line.rstrip("\r\n")
                stripped = visible.strip()
                left = len(visible) - len(visible.lstrip())
                start, end = offset + left, offset + len(visible.rstrip())
                if not stripped:
                    offset += len(raw_line); continue
                heading = self._heading(stripped)
                if heading:
                    name, level = heading
                    cls = self._classify(name)
                    sec_id = _stable("sec", doc.document_id, str(page_num), str(start), name)
                    active = SectionRecord(section_id=sec_id, heading=name, classification=cls or "unknown",
                                           classification_status="classified" if cls else "needs_review",
                                           level=level, parent_section_id=None, page_start=page_num, page_end=page_num)
                    # Infer hierarchy only from heading level; keep parent explicit.
                    parent = next((s for s in reversed(sections) if s.level < level), None)
                    active.parent_section_id = parent.section_id if parent else None
                    sections.append(active)
                    block = self._block(doc.document_id, "heading", stripped, page_num, start, end, active)
                    block.structural_level = level
                    blocks.append(block)
                    if cls == "references": ref_mode = True
                    elif ref_mode and cls not in (None, "references"): ref_mode = False
                    if cls == "abstract": abstract_lines.append("")
                else:
                    if ref_mode and self._reference_like(stripped):
                        ref = self._reference(doc.document_id, stripped, page_num, start, end)
                        refs.append(ref)
                        blocks.append(DocumentBlock(block_id=_stable("blk", doc.document_id, "reference", str(page_num), str(start)),
                                                    block_type="reference", text=stripped,
                                                    position=Position(page_number=page_num, char_start=start, char_end=end),
                                                    section_id=active.section_id if active else None, classification="reference",
                                                    classification_status="classified"))
                    else:
                        block_type = "list_item" if re.match(r"^(?:[-*•▪] |\d+[.)]\s+)", stripped) else "paragraph"
                        if re.match(r"^(?:Table|Fig(?:ure)?\.?\s*\d+|Equation\s*\(?\d+\)?)\s*[:.)]", stripped, re.I): block_type = "caption"
                        block = self._block(doc.document_id, block_type, stripped, page_num, start, end, active)
                        blocks.append(block)
                        kw = re.match(r"^(?:keywords?|index terms?)\s*[:—-]\s*(.*)$", stripped, re.I)
                        if active and not kw:
                            active.text = (active.text + "\n" + stripped).strip()
                            active.page_end = page_num
                            if active.classification == "abstract": abstract_lines.append(stripped)
                        if kw: keyword_values.extend(x.strip() for x in re.split(r"[,;]", kw.group(1)) if x.strip())
                        for marker in re.finditer(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]|\(([^()]*\b(?:19|20)\d{2}[a-z]?[^()]*)\)", stripped):
                            key = marker.group(1) or marker.group(2)
                            markers.append({"marker": marker.group(0), "key": key, "page_number": page_num,
                                            "char_start": start + marker.start(), "char_end": start + marker.end(),
                                            "section_id": active.section_id if active else None})
                            for cited_number in re.findall(r"\d+", key):
                                citation_to_pages.setdefault(cited_number, set()).add(page_num)
                        for category, pattern in _KNOWLEDGE.items():
                            if re.search(pattern, stripped, re.I):
                                rid = _stable("kn", doc.document_id, category, str(page_num), str(start), stripped)
                                records.append(KnowledgeRecord(record_id=rid, category=category, exact_text=stripped,
                                    document_id=doc.document_id, page_number=page_num,
                                    section_id=active.section_id if active else None, block_id=block.block_id,
                                    char_start=start, char_end=end, extraction_method="deterministic_pattern",
                                    extraction_version=EXTRACTION_VERSION, confidence=0.55,
                                    uncertainty="Pattern match only; candidate requires human verification."))
                offset += len(raw_line)
        for reference in refs:
            key = reference.reference_number
            if key and key in citation_to_pages:
                reference.cited_in_text = True
                reference.citation_pages = sorted(citation_to_pages[key])
        if not refs and any(s.classification == "references" for s in sections): quality.append("References heading found, but no entries matched the conservative reference pattern.")
        page_map = {p["page_number"]: p["text"] for p in page_dump}
        for record in records:
            source = page_map.get(record.page_number)
            if source is None or record.char_end > len(source) or source[record.char_start:record.char_end] != record.exact_text:
                quality.append(f"Knowledge record {record.record_id} failed exact evidence validation.")
        known_ref_numbers = {ref.reference_number for ref in refs if ref.reference_number}
        unresolved = sorted({number for key in citation_to_pages for number in re.findall(r"\d+", key)} - known_ref_numbers)
        if unresolved:
            quality.append("Some numeric in-text citation markers have no matching parsed bibliography entry: " + ", ".join(unresolved[:20]))
        if any(section.classification_status == "needs_review" for section in sections):
            quality.append("One or more section headings remain unclassified and need review.")
        if any(ref.title is None or ref.year is None for ref in refs):
            quality.append("One or more bibliography entries have incomplete parsed metadata; review raw entries.")
        return DocumentIntelligence(
            run_id=run_id, content_hash=content_hash, document_id=doc.document_id, paper_id=doc.paper_id,
            filename=doc.metadata.filename, file_type=file_type or doc.metadata.source_format,
            title=doc.title, authors=doc.authors, year=doc.year, doi=doc.metadata.doi,
            abstract="\n".join(abstract_lines).strip() or None, keywords=list(dict.fromkeys(keyword_values)),
            page_count=len(page_dump), extraction_status=status,
            private_source=private,
            structure_capabilities=self._capabilities(file_type or doc.metadata.source_format), pages=page_dump,
            sections=sections, blocks=blocks, knowledge_records=records, references=refs,
            citation_markers=markers, quality_issues=quality, duration_seconds=round(time.perf_counter()-started, 6))

    @staticmethod
    def _heading(line: str) -> tuple[str, int] | None:
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m: return m.group(2), len(m.group(1))
        sec_m = re.match(r"^(?:Section|Unit|Module|Chapter|Part)\s+([0-9IVXLCDM]+)\s*[:.]?\s*(.*)$", line, re.I)
        if sec_m:
            title = sec_m.group(2).strip()
            return f"Section {sec_m.group(1)}: {title}" if title else f"Section {sec_m.group(1)}", 1
        m = re.match(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+(.{2,100})$", line)
        if m and len(line) < 110: return m.group(2).strip(), m.group(1).count(".") + 1
        if len(line) <= 80 and line.isupper() and re.search(r"[A-Z]", line) and len(line.split()) <= 10:
            return line.title(), 1
        if len(line) <= 60 and len(line.split()) <= 8 and not re.search(r"[.!?;:]$", line):
            if DocumentIntelligenceExtractor._classify(line):
                return line, 1
        return None

    @staticmethod
    def _classify(text: str) -> str | None:
        for name, pattern in _CLASSIFIERS:
            if re.search(rf"\b(?:{pattern})\b", text, re.I): return name
        return None

    @staticmethod
    def _block(doc_id: str, kind: str, text: str, page: int, start: int, end: int, section: SectionRecord | None) -> DocumentBlock:
        return DocumentBlock(block_id=_stable("blk", doc_id, kind, str(page), str(start)), block_type=kind, text=text,
            position=Position(page_number=page, char_start=start, char_end=end), section_id=section.section_id if section else None,
            classification=section.classification if section else "unknown",
            classification_status=section.classification_status if section else "unknown")

    @staticmethod
    def _reference_like(text: str) -> bool:
        return bool(re.match(r"^(?:\[\d+\]|\d+[.)])\s+", text) or re.search(r"\b(?:19|20)\d{2}\b", text) and len(text) > 35)

    @staticmethod
    def _reference(doc_id: str, text: str, page: int, start: int, end: int) -> ReferenceRecord:
        num = re.match(r"^(?:\[(\d+)\]|(\d+)[.)])\s*(.*)$", text)
        body = num.group(3) if num else text
        year_match = re.search(r"\b((?:19|20)\d{2})\b", body)
        doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", body, re.I)
        url_match = re.search(r"https?://\S+", body, re.I)
        title_match = re.search(r"[“\"]([^”\"]{8,})[”\"]", body)
        authors_raw = body.split(".", 1)[0]
        authors = [a.strip() for a in re.split(r",|\band\b|&", authors_raw) if len(a.strip()) > 1][:10]
        return ReferenceRecord(reference_id=_stable("ref", doc_id, str(page), str(start)), raw_text=text,
            reference_number=(num.group(1) or num.group(2)) if num else None, authors=authors,
            title=title_match.group(1).strip().rstrip(".,;:") if title_match else None, year=int(year_match.group(1)) if year_match else None,
            doi=doi_match.group(0).rstrip(".,;") if doi_match else None,
            url=url_match.group(0).rstrip(".,;") if url_match else None,
            page_number=page, char_start=start, char_end=end)

    @staticmethod
    def _capabilities(file_type: str | None) -> dict[str, str]:
        ext = (file_type or "").lower().lstrip(".")
        base = {"page_text": "available", "character_offsets": "page-local offsets into normalized parser text",
                "figure_visual_interpretation": "unavailable; no visual model is used"}
        if ext == "docx":
            base.update(tables="parser flattens into text; cell structure not retained by normalized output",
                        equations="existing OMML extractor can emit LaTeX, but exact page/block position unavailable")
        elif ext in {"pptx", "csv", "xlsx"}:
            base["tables"] = "flattened by existing parser; source row/column structure is not retained in normalized output"
        elif ext == "pdf":
            base.update(tables="not structurally exposed by current PDF text adapter", figures="captions may be text-detected; image references unavailable",
                        equations="plain text only; no reliable math structure")
        else:
            base.update(tables="only explicit text patterns; native cells unavailable", equations="plain text only")
        return base

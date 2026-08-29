"""
Document loaders for PDF, Markdown, and Text research papers.
Preserves page-level structure and line integrity.
"""

import os
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from rag.ingestion.document_normalizer import Page, NormalizedDocument, DocumentMetadata, DocumentNormalizer
from rag.ingestion.metadata_mapper import MetadataMapper

logger = logging.getLogger(__name__)


class BaseDocumentLoader(ABC):
    """
    Abstract interface for document loaders.
    """

    @abstractmethod
    def load(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> NormalizedDocument:
        """
        Loads document from file_path and returns a NormalizedDocument.
        """
        pass


class PDFDocumentLoader(BaseDocumentLoader):
    """
    Extracts text from PDF documents page by page using pypdf.
    """

    def __init__(self, normalizer: Optional[DocumentNormalizer] = None):
        self.normalizer = normalizer or DocumentNormalizer()

    def load(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> NormalizedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        meta = MetadataMapper.map_metadata(
            raw_metadata=metadata,
            file_path=str(path.absolute()),
        )

        pages: List[Page] = []
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))

            # Attempt to extract title from PDF metadata if not provided
            if meta.title == "Untitled Research Paper" and reader.metadata and reader.metadata.title:
                meta.title = str(reader.metadata.title)

            for idx, pdf_page in enumerate(reader.pages, start=1):
                extracted_text = pdf_page.extract_text() or ""
                pages.append(Page(page_number=idx, text=extracted_text))

        except Exception as e:
            logger.error("Failed to load PDF via pypdf: %s. Error: %s", file_path, e)
            raise RuntimeError(f"Error parsing PDF file {file_path}: {e}") from e

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

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.load_text(content=content, metadata=metadata, file_path=str(path.absolute()))

    def load_text(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> NormalizedDocument:
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
        elif ext in {".txt", ".md", ".json", ".tex"}:
            return TextDocumentLoader()
        else:
            # Default to text loader
            return TextDocumentLoader()

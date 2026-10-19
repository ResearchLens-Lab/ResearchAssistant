"""
Standardizes raw metadata into valid DocumentMetadata instances.
Ensures critical identifiers (paper_id, document_id) are deterministic and present.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from rag.ingestion.document_normalizer import DocumentMetadata


class MetadataMapper:
    """
    Normalizes metadata dictionaries into strongly-typed DocumentMetadata.
    """

    @staticmethod
    def map_metadata(
        raw_metadata: Optional[Dict[str, Any]] = None,
        paper_id: Optional[str] = None,
        document_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> DocumentMetadata:
        data = raw_metadata.copy() if raw_metadata else {}

        resolved_paper_id = paper_id or data.get("paper_id") or f"paper_{uuid.uuid4().hex[:8]}"
        resolved_doc_id = document_id or data.get("document_id") or f"doc_{resolved_paper_id}"

        title = data.get("title") or "Untitled Research Paper"
        authors = data.get("authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]

        year = data.get("year")
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None

        doi = data.get("doi")

        # Reserve remaining keys in extra dict
        reserved_keys = {"paper_id", "document_id", "title", "authors", "year", "doi", "file_path"}
        extra = {k: v for k, v in data.items() if k not in reserved_keys}

        return DocumentMetadata(
            paper_id=str(resolved_paper_id),
            document_id=str(resolved_doc_id),
            title=str(title),
            authors=authors,
            year=year,
            doi=doi,
            file_path=file_path or data.get("file_path"),
            filename=data.get("filename") or (file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if file_path else None),
            source_format=(Path(file_path).suffix.lower().lstrip(".") if file_path else data.get("source_format")),
            extra=extra,
        )

"""Strict upload validation for supported document formats."""
import os
from typing import Optional

from backend.app.core.exceptions import RequestValidationAppError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".xlsx", ".pptx", ".html", ".htm", ".json"}


def validate_document_upload(filename: Optional[str], content_type: Optional[str], content: bytes, max_size_bytes: int) -> None:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise RequestValidationAppError("Unsupported format. Upload PDF, DOCX, TXT, Markdown, CSV, XLSX, PPTX, HTML, or JSON.")
    if not content:
        raise RequestValidationAppError("Uploaded file is empty.")
    if len(content) > max_size_bytes:
        raise RequestValidationAppError(f"File exceeds the maximum allowed size of {max_size_bytes // (1024 * 1024)} MB.")
    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise RequestValidationAppError("File does not appear to be a valid PDF.")
    if ext == ".docx" and not content.startswith(b"PK"):
        raise RequestValidationAppError("File does not appear to be a valid DOCX archive.")
    if ext in {".xlsx", ".pptx"} and not content.startswith(b"PK"):
        raise RequestValidationAppError(f"File does not appear to be a valid {ext[1:].upper()} archive.")
    if ext in {".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".json"}:
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RequestValidationAppError("Text documents must be UTF-8 encoded.") from exc


# Backwards compatible name for clients importing the former PDF validator.
validate_pdf_upload = validate_document_upload

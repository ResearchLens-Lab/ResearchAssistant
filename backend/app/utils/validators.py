"""Strict upload validation for supported document formats."""
import os
import codecs
from pathlib import Path
from typing import Optional

from backend.app.core.exceptions import RequestValidationAppError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".tex", ".csv", ".xlsx", ".pptx", ".html", ".htm", ".json"}


def resolve_safe_path_in_dir(
    folder: Path, filename: Optional[str], fallback: str = "document.txt"
) -> Path:
    """Strip directory components from a user-supplied filename and verify
    the resolved destination stays strictly inside `folder`."""
    raw_name = (filename or "").replace("\\", "/")
    clean_name = Path(raw_name).name.strip()
    if not clean_name or clean_name in {".", ".."}:
        clean_name = fallback
    resolved_folder = folder.resolve()
    dest = (resolved_folder / clean_name).resolve()
    if not dest.is_relative_to(resolved_folder) or dest == resolved_folder:
        raise RequestValidationAppError("Invalid filename.")
    return dest


def validate_document_file(filename: Optional[str], content_type: Optional[str], path: Path, size: int, max_size_bytes: int) -> None:
    """Validate a staged upload without loading its entire body into memory."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise RequestValidationAppError("Unsupported format. Upload PDF, DOCX, TXT, Markdown, CSV, XLSX, PPTX, HTML, or JSON.")
    if size <= 0:
        raise RequestValidationAppError("Uploaded file is empty.")
    if size > max_size_bytes:
        raise RequestValidationAppError(f"File exceeds the maximum allowed size of {max_size_bytes // (1024 * 1024)} MB.")
    with path.open("rb") as stream:
        prefix = stream.read(8)
        if ext == ".pdf" and not prefix.startswith(b"%PDF-"):
            raise RequestValidationAppError("File does not appear to be a valid PDF.")
        if ext in {".docx", ".xlsx", ".pptx"} and not prefix.startswith(b"PK"):
            raise RequestValidationAppError(f"File does not appear to be a valid {ext[1:].upper()} archive.")
        if ext in {".txt", ".md", ".markdown", ".tex", ".csv", ".html", ".htm", ".json"}:
            decoder = codecs.getincrementaldecoder("utf-8-sig")()
            stream.seek(0)
            try:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                raise RequestValidationAppError("Text documents must be UTF-8 encoded.") from exc


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
    if ext in {".txt", ".md", ".markdown", ".tex", ".csv", ".html", ".htm", ".json"}:
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RequestValidationAppError("Text documents must be UTF-8 encoded.") from exc


# Backwards compatible name for clients importing the former PDF validator.
validate_pdf_upload = validate_document_upload

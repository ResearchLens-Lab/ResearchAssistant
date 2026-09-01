"""Upload validation helpers."""

from typing import Optional

from backend.app.core.exceptions import RequestValidationAppError

PDF_MAGIC = b"%PDF-"
ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
}


def validate_pdf_upload(
    filename: Optional[str],
    content_type: Optional[str],
    content: bytes,
    max_size_bytes: int,
) -> None:
    """Validates an uploaded research-paper PDF; raises 400 VALIDATION_ERROR."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise RequestValidationAppError("Only PDF files are supported.")
    if content_type and content_type.lower() not in ALLOWED_PDF_CONTENT_TYPES:
        raise RequestValidationAppError(
            f"Unsupported content type '{content_type}'. Expected application/pdf."
        )
    if len(content) == 0:
        raise RequestValidationAppError("Uploaded file is empty.")
    if len(content) > max_size_bytes:
        raise RequestValidationAppError(
            f"File exceeds the maximum allowed size of {max_size_bytes // (1024 * 1024)} MB."
        )
    # Check the file signature rather than trusting the extension alone.
    if not content.startswith(PDF_MAGIC):
        raise RequestValidationAppError("File does not appear to be a valid PDF.")

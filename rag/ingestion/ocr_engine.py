"""
Local OCR Engine using PyMuPDF and bundled Tesseract language data.
Provides offline, deterministic OCR extraction for scanned PDF pages
with quality scoring, rotation correction, and retry capabilities.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pymupdf

logger = logging.getLogger(__name__)

# Common English stopwords used to evaluate lexical plausibility of OCR text
COMMON_ENGLISH_WORDS = {
    "the", "of", "and", "a", "to", "in", "is", "you", "that", "it",
    "he", "was", "for", "on", "are", "as", "with", "his", "they", "i",
    "at", "be", "this", "have", "from", "or", "one", "had", "by", "word",
    "but", "not", "what", "all", "were", "we", "when", "your", "can", "said",
    "there", "use", "an", "each", "which", "she", "do", "how", "their", "if",
    "algorithm", "data", "input", "output", "step", "function", "set", "time",
}


@dataclass
class OCRResult:
    page_number: int
    text: str
    confidence: float  # [0.0 - 1.0]
    dpi_used: int
    execution_time_seconds: float
    char_count: int
    word_count: int
    printable_ratio: float
    is_successful: bool
    warning: Optional[str] = None


class LocalOCREngine:
    """Offline OCR engine utilizing PyMuPDF's internal Tesseract C++ bindings."""

    DEFAULT_DPI = 100
    RETRY_DPI = 150

    def __init__(
        self,
        tessdata_path: Optional[str | Path] = None,
        default_dpi: int = DEFAULT_DPI,
        retry_dpi: int = RETRY_DPI,
    ):
        self.default_dpi = default_dpi
        self.retry_dpi = retry_dpi

        # Resolve tessdata directory
        if tessdata_path:
            self.tessdata_path = Path(tessdata_path).resolve()
        elif "RESEARCHLENS_TESSDATA_PATH" in os.environ:
            self.tessdata_path = Path(os.environ["RESEARCHLENS_TESSDATA_PATH"]).resolve()
        else:
            # Look in rag/resources/tessdata relative to this file
            current_dir = Path(__file__).resolve().parent
            # current_dir is rag/ingestion -> parent is rag -> resources/tessdata
            candidate = current_dir.parent / "resources" / "tessdata"
            self.tessdata_path = candidate.resolve()

        if not (self.tessdata_path / "eng.traineddata").exists():
            logger.warning(
                "eng.traineddata not found at %s. OCR extraction will fail if invoked.",
                self.tessdata_path,
            )

    def is_available(self) -> bool:
        """Check if local OCR language data is present."""
        return (self.tessdata_path / "eng.traineddata").exists()

    def evaluate_text_quality(self, text: str) -> tuple[float, float, int, int]:
        """
        Calculates quality metrics for extracted OCR text:
        returns: (confidence_score, printable_ratio, char_count, word_count)
        Penalizes control characters, private-use code points, recognizes formula/numeric tokens,
        and ensures empty or meaningless text is never evaluated as successful.
        """
        if not text or not text.strip():
            return 0.0, 0.0, 0, 0

        stripped = text.strip()
        char_count = len(stripped)
        if char_count == 0 or not re.search(r"\S", stripped):
            return 0.0, 0.0, 0, 0

        printable_count = sum(1 for ch in stripped if ch.isprintable() and not ch.isspace())
        printable_ratio = printable_count / max(1, char_count)

        # Detect corrupt characters: ASCII controls (except \t, \n, \r), Unicode replacement char, and private-use area
        corrupt_chars = sum(
            1 for ch in stripped
            if (ord(ch) < 32 and ch not in ("\t", "\n", "\r"))
            or (0xE000 <= ord(ch) <= 0xF8FF)
            or (0xF0000 <= ord(ch) <= 0x10FFFD)
            or ch == "\ufffd"
            or ch == "\u0017"
        )
        corrupt_ratio = corrupt_chars / max(1, char_count)
        corrupt_penalty = min(1.0, corrupt_ratio * 4.0)

        # Word-level evaluation & formula/numeric token detection
        tokens = re.findall(r"\b[A-Za-z]+\b", stripped.lower())
        formula_tokens = re.findall(r"\b\d+(?:\.\d+)?\b|[=+\-*/<>≤≥∑∫ΘΩ^_{}\[\]()]", stripped)
        word_count = len(tokens)

        if word_count == 0:
            if formula_tokens and char_count >= 10:
                math_conf = max(0.0, (0.4 * printable_ratio) - corrupt_penalty)
                return round(math_conf, 3), round(printable_ratio, 3), char_count, 0
            return 0.0, round(printable_ratio, 3), char_count, 0

        # Stopword / English vocabulary match
        matching_words = sum(1 for w in tokens if w in COMMON_ENGLISH_WORDS)
        vocab_match_ratio = matching_words / max(1, word_count)

        # Average word length penalty (gibberish often has tiny or huge words)
        avg_word_len = sum(len(w) for w in tokens) / word_count
        len_penalty = 1.0
        if avg_word_len < 2.5 or avg_word_len > 12.0:
            len_penalty = 0.6

        # Formula / math presence bonus for STEM textbooks
        math_bonus = min(0.15, len(formula_tokens) / max(1, char_count))

        confidence = (
            (printable_ratio * 0.25)
            + (min(1.0, vocab_match_ratio * 3.5 + math_bonus) * 0.50)
            + (len_penalty * 0.20)
            - (corrupt_penalty * 0.60)
        )
        confidence = max(0.0, min(1.0, confidence))
        return confidence, printable_ratio, char_count, word_count

    def ocr_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        dpi: Optional[int] = None,
    ) -> OCRResult:
        """Runs OCR on a single PyMuPDF page object."""
        target_dpi = dpi or self.default_dpi
        start_time = time.perf_counter()

        if not self.is_available():
            return OCRResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                dpi_used=target_dpi,
                execution_time_seconds=0.0,
                char_count=0,
                word_count=0,
                printable_ratio=0.0,
                is_successful=False,
                warning="Local OCR language data (eng.traineddata) is missing.",
            )

        try:
            tp = page.get_textpage_ocr(
                language="eng",
                dpi=target_dpi,
                tessdata=str(self.tessdata_path),
                full=False,
            )
            raw_text = tp.extractText() or ""
        except Exception as exc:
            logger.error("OCR failed for page %d at %d DPI: %s", page_number, target_dpi, exc)
            return OCRResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                dpi_used=target_dpi,
                execution_time_seconds=time.perf_counter() - start_time,
                char_count=0,
                word_count=0,
                printable_ratio=0.0,
                is_successful=False,
                warning=f"OCR engine exception: {exc}",
            )

        conf, print_ratio, chars, words = self.evaluate_text_quality(raw_text)

        # Retry with higher DPI if confidence is marginal and not already at retry_dpi
        if conf < 0.45 and target_dpi < self.retry_dpi and chars > 20:
            logger.debug("Page %d OCR confidence low (%.2f); retrying with %d DPI", page_number, conf, self.retry_dpi)
            retry_res = self.ocr_page(page, page_number, dpi=self.retry_dpi)
            if retry_res.confidence > conf:
                return retry_res

        elapsed = time.perf_counter() - start_time
        has_alphanumeric = bool(re.search(r"[A-Za-z0-9]", raw_text))
        success = chars > 30 and conf >= 0.30 and has_alphanumeric
        warn = None
        if not success:
            warn = "Extracted text quality below acceptable confidence threshold"

        return OCRResult(
            page_number=page_number,
            text=raw_text,
            confidence=round(conf, 3),
            dpi_used=target_dpi,
            execution_time_seconds=round(elapsed, 3),
            char_count=chars,
            word_count=words,
            printable_ratio=round(print_ratio, 3),
            is_successful=success,
            warning=warn,
        )

    def ocr_pages(
        self,
        doc: pymupdf.Document,
        pages_to_process: List[int],
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[Any] = None,
    ) -> Dict[int, OCRResult]:
        """
        Executes OCR on a set of 1-indexed page numbers.
        Yields progress and honors cancellation events.
        """
        results: Dict[int, OCRResult] = {}
        total = len(pages_to_process)
        if total == 0:
            return results

        for idx, page_num in enumerate(pages_to_process, start=1):
            if cancel_event is not None and cancel_event.is_set():
                logger.info("OCR batch cancelled at page %d", page_num)
                break

            zero_idx = page_num - 1
            if 0 <= zero_idx < len(doc):
                page = doc[zero_idx]
                res = self.ocr_page(page, page_num)
                results[page_num] = res

            if progress_callback:
                progress_val = round(20 + (50 * idx / max(1, total)))
                progress_callback({
                    "stage": "ocr_processing",
                    "progress": progress_val,
                    "progress_type": "actual",
                    "completed_pages": idx,
                    "total_pages": total,
                    "current_page": page_num,
                })

        return results

"""
Universal PDF Preflight Analyzer.
Inspects printable character ratio, embedded text length, image coverage,
page rotation, font corruption, and classifies document into:
DIGITAL, SCANNED, MIXED, BROKEN_FONTS, PASSWORD_PROTECTED, or CORRUPT.
"""

from __future__ import annotations

import enum
import logging
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf

logger = logging.getLogger(__name__)


class DocumentCategory(str, enum.Enum):
    DIGITAL = "DIGITAL"
    SCANNED = "SCANNED"
    MIXED = "MIXED"
    BROKEN_FONTS = "BROKEN_FONTS"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    CORRUPT = "CORRUPT"


@dataclass
class PagePreflightMetrics:
    page_number: int  # 1-indexed PDF physical page
    page_label: str  # Roman / Arabic label from PDF catalog if present
    native_text_length: int
    printable_ratio: float
    image_count: int
    image_area_ratio: float  # Fraction of page area covered by raster images [0.0 - 1.0]
    rotation_angle: int  # 0, 90, 180, 270
    is_scanned: bool
    is_broken_font: bool
    requires_ocr: bool
    ocr_confidence: Optional[float] = None
    warning: Optional[str] = None


@dataclass
class PreflightReport:
    file_path: str
    total_pages: int
    category: DocumentCategory
    pages_requiring_ocr: List[int] = field(default_factory=list)
    page_metrics: List[PagePreflightMetrics] = field(default_factory=list)
    average_printable_ratio: float = 1.0
    scanned_page_ratio: float = 0.0
    digital_page_ratio: float = 1.0
    detected_title: Optional[str] = None
    detected_author: Optional[str] = None
    is_encrypted: bool = False
    is_repaired: bool = False
    preflight_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_pages": self.total_pages,
            "category": self.category.value,
            "pages_requiring_ocr": self.pages_requiring_ocr,
            "ocr_page_count": len(self.pages_requiring_ocr),
            "scanned_page_ratio": round(self.scanned_page_ratio, 3),
            "digital_page_ratio": round(self.digital_page_ratio, 3),
            "average_printable_ratio": round(self.average_printable_ratio, 3),
            "detected_title": self.detected_title,
            "is_encrypted": self.is_encrypted,
            "preflight_error": self.preflight_error,
        }


class PDFPreflightAnalyzer:
    """Fast, non-destructive preflight analysis of PDF documents."""

    # Thresholds
    MIN_TEXT_CHARS_FOR_DIGITAL = 80
    MIN_PRINTABLE_RATIO = 0.70
    MIN_SCANNED_IMAGE_COVERAGE = 0.35
    MAX_GLYPH_CORRUPTION_RATIO = 0.20

    def __init__(
        self,
        min_text_chars: int = MIN_TEXT_CHARS_FOR_DIGITAL,
        min_image_coverage: float = MIN_SCANNED_IMAGE_COVERAGE,
    ):
        self.min_text_chars = min_text_chars
        self.min_image_coverage = min_image_coverage

    def analyze(self, file_path: str | Path, password: str = "") -> PreflightReport:
        p = Path(file_path)
        if not p.exists():
            return PreflightReport(
                file_path=str(p),
                total_pages=0,
                category=DocumentCategory.CORRUPT,
                preflight_error=f"File not found: {p}",
            )

        try:
            doc = pymupdf.open(str(p))
        except Exception as exc:
            logger.error("Preflight failed to open PDF file=%s error=%s", p.name, exc)
            return PreflightReport(
                file_path=str(p),
                total_pages=0,
                category=DocumentCategory.CORRUPT,
                preflight_error=f"Corrupt or unreadable PDF: {exc}",
            )

        with doc:
            if doc.is_encrypted:
                auth_success = doc.authenticate(password)
                if not auth_success:
                    return PreflightReport(
                        file_path=str(p),
                        total_pages=len(doc),
                        category=DocumentCategory.PASSWORD_PROTECTED,
                        is_encrypted=True,
                        preflight_error="Document is password protected and cannot be decrypted.",
                    )

            total_pages = len(doc)
            if total_pages == 0:
                return PreflightReport(
                    file_path=str(p),
                    total_pages=0,
                    category=DocumentCategory.CORRUPT,
                    preflight_error="PDF has 0 pages.",
                )

            page_metrics: List[PagePreflightMetrics] = []
            pages_requiring_ocr: List[int] = []

            # Page labels mapping
            page_labels = {}
            try:
                for idx, lbl in enumerate(doc.get_page_labels()):
                    page_labels[idx + 1] = str(lbl)
            except Exception:
                pass

            total_printable_ratio = 0.0

            for page_idx in range(total_pages):
                page_num = page_idx + 1
                page = doc[page_idx]
                page_rect = page.rect
                page_area = max(1.0, page_rect.width * page_rect.height)

                # 1. Text extraction
                text = page.get_text("text") or ""
                text_len = len(text.strip())

                # 2. Printable character ratio
                printable_count = sum(1 for ch in text if ch.isprintable() and not ch.isspace())
                printable_ratio = (printable_count / max(1, text_len)) if text_len > 0 else 1.0
                total_printable_ratio += printable_ratio

                # 3. Unicode / font corruption check
                # Check for replacement characters, cid references, or high non-printable
                replacement_chars = text.count("\ufffd") + len(re.findall(r"\(cid:\d+\)", text))
                is_broken_font = (
                    text_len > 100
                    and (
                        (replacement_chars / max(1, text_len)) > self.MAX_GLYPH_CORRUPTION_RATIO
                        or printable_ratio < self.MIN_PRINTABLE_RATIO
                    )
                )

                # 4. Image coverage
                image_list = page.get_images(full=True)
                total_img_area = 0.0
                for img_info in image_list:
                    # img_info: (xref, smask, width, height, bpc, colorspace, ...)
                    try:
                        img_rects = page.get_image_rects(img_info[0])
                        for rect in img_rects:
                            total_img_area += rect.width * rect.height
                    except Exception:
                        pass

                image_area_ratio = min(1.0, total_img_area / page_area)

                # 5. Determine if page is scanned or requires OCR
                rotation = page.rotation % 360
                is_scanned = (
                    text_len < self.min_text_chars
                    and (image_area_ratio >= self.min_image_coverage or len(image_list) > 0)
                )
                requires_ocr = is_scanned or (is_broken_font and text_len > 50)

                warn = None
                if is_broken_font:
                    warn = "Broken font mappings detected; text may contain replacement glyphs"
                elif is_scanned:
                    warn = "Scanned raster page with negligible extractable text"

                if requires_ocr:
                    pages_requiring_ocr.append(page_num)

                page_label = page_labels.get(page_num, str(page_num))

                page_metrics.append(
                    PagePreflightMetrics(
                        page_number=page_num,
                        page_label=page_label,
                        native_text_length=text_len,
                        printable_ratio=printable_ratio,
                        image_count=len(image_list),
                        image_area_ratio=image_area_ratio,
                        rotation_angle=rotation,
                        is_scanned=is_scanned,
                        is_broken_font=is_broken_font,
                        requires_ocr=requires_ocr,
                        warning=warn,
                    )
                )

            avg_printable = total_printable_ratio / total_pages
            ocr_count = len(pages_requiring_ocr)
            scanned_ratio = ocr_count / total_pages
            digital_ratio = 1.0 - scanned_ratio

            # Overall Category Classification
            if ocr_count == total_pages or (scanned_ratio >= 0.85 and total_pages > 2):
                category = DocumentCategory.SCANNED
            elif ocr_count == 0:
                has_any_broken = any(m.is_broken_font for m in page_metrics)
                category = DocumentCategory.BROKEN_FONTS if has_any_broken else DocumentCategory.DIGITAL
            else:
                category = DocumentCategory.MIXED

            # Detect title & author from PDF metadata
            meta = doc.metadata or {}
            detected_title = meta.get("title") or None
            detected_author = meta.get("author") or None

            return PreflightReport(
                file_path=str(p),
                total_pages=total_pages,
                category=category,
                pages_requiring_ocr=pages_requiring_ocr,
                page_metrics=page_metrics,
                average_printable_ratio=avg_printable,
                scanned_page_ratio=scanned_ratio,
                digital_page_ratio=digital_ratio,
                detected_title=detected_title,
                detected_author=detected_author,
                is_encrypted=doc.is_encrypted,
                is_repaired=doc.is_repaired,
            )

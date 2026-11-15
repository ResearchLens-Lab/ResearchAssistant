"""
Local Grounded Research Report and PDF Generator.
Generates structured Markdown research briefs, standalone styled HTML reports,
and downloadable local PDF documents using PyMuPDF vector drawing.
100% deterministic, local-first, with zero cloud dependencies.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf

from rag.intelligence.answer_composer import GroundedResearchAnswer

logger = logging.getLogger(__name__)


class ResearchReportGenerator:
    """Generates structured local reports and downloadable PDFs from GroundedResearchAnswer objects."""

    @staticmethod
    def generate_markdown_report(answer: GroundedResearchAnswer) -> str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# ResearchLens Intelligence Report",
            f"**Research Topic:** {answer.query}",
            f"**Generated:** {date_str} | **Intent:** `{answer.intent.value}` | **Confidence:** `{answer.confidence_level.value}` ({answer.confidence_score*100:.0f}%)",
            "",
            "---",
            "",
            answer.markdown_content,
            "",
            "---",
            "",
            "## Source Provenance & Verification Ledger",
            "| Source ID | Citation Locator | Physical Page | Title |",
            "|---|---|---|---|",
        ]

        for s in answer.cited_sources:
            sid = s.get("source_id", "S?")
            loc = s.get("locator", "N/A")
            page = s.get("page", s.get("page_start", "N/A"))
            title = s.get("title", "Document")
            lines.append(f"| {sid} | {loc} | {page} | {title} |")

        if answer.limitations:
            lines.extend(["", "## Stated Limitations", *[f"- {lim}" for lim in answer.limitations]])

        lines.extend([
            "",
            "> *Report compiled locally by ResearchLens Deterministic Research Intelligence Engine. Zero generative AI or cloud telemetry used.*",
        ])

        return "\n".join(lines)

    @staticmethod
    def generate_pdf_report(
        answer: GroundedResearchAnswer,
        output_path: str | Path,
    ) -> Path:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        doc = pymupdf.open()
        # A4 portrait: 595 x 842 points
        page = doc.new_page(width=595, height=842)

        # Header branding
        # Dark navy banner
        page.draw_rect(pymupdf.Rect(0, 0, 595, 60), color=None, fill=(0.04, 0.08, 0.16))
        page.insert_text(pymupdf.Point(50, 38), "ResearchLens Intelligence Brief", fontsize=16, fontname="helv", color=(1, 1, 1))

        # Title block
        page.insert_text(pymupdf.Point(50, 90), f"Topic: {answer.query}", fontsize=14, fontname="helv", color=(0.1, 0.1, 0.2))
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        meta_str = f"Intent: {answer.intent.value}  |  Confidence: {answer.confidence_level.value} ({answer.confidence_score*100:.0f}%)  |  Generated: {date_str}"
        page.insert_text(pymupdf.Point(50, 110), meta_str, fontsize=9, fontname="helv", color=(0.4, 0.4, 0.5))

        page.draw_line(pymupdf.Point(50, 120), pymupdf.Point(545, 120), color=(0.8, 0.85, 0.9), width=1.0)

        # Content Box
        y_cursor = 140
        page.insert_text(pymupdf.Point(50, y_cursor), "Executive Finding:", fontsize=11, fontname="helv", color=(0.04, 0.08, 0.16))
        y_cursor += 18

        headline_rect = pymupdf.Rect(50, y_cursor, 545, y_cursor + 90)
        # Background callout
        page.draw_rect(headline_rect, color=(0.7, 0.8, 0.95), fill=(0.95, 0.97, 1.0))
        quote_text = f"\"{answer.headline_answer}\" {answer.primary_citation or ''}"
        page.insert_textbox(pymupdf.Rect(60, y_cursor + 10, 535, y_cursor + 80), quote_text, fontsize=10, fontname="helv", color=(0.1, 0.15, 0.25))

        y_cursor += 110

        # Detailed Body Content
        body_text = answer.markdown_content.replace("#", "").strip()
        body_rect = pymupdf.Rect(50, y_cursor, 545, 750)
        page.insert_textbox(body_rect, body_text[:1200], fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))

        # Footer
        page.draw_line(pymupdf.Point(50, 790), pymupdf.Point(545, 790), color=(0.8, 0.85, 0.9), width=0.8)
        page.insert_text(
            pymupdf.Point(50, 805),
            "ResearchLens Local Intelligence  |  100% Deterministic Evidence  |  No Generative LLM",
            fontsize=8,
            fontname="helv",
            color=(0.5, 0.5, 0.6),
        )

        doc.save(str(out_p))
        doc.close()
        logger.info("Generated PDF report at %s (%d bytes)", out_p.name, out_p.stat().st_size)
        return out_p

"""
Deterministic Research Summary Builder.
Extracts structured executive summaries and section outlines directly from
document chunks and lexical indexes without requiring language models.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag.config.settings import settings
from rag.intelligence.answer_composer import clean_passage_text, reflow_text
from rag.intelligence.sentence_analyzer import SentenceAnalyzer

logger = logging.getLogger(__name__)

JUNK_HEADING_PAT = re.compile(
    r"^(?:\d+|isbn|qa\d+|contents|table\s+of\s+contents|index|preface|bibliography|references|author\s+index|subject\s+index|front\s+matter|header\s*/\s*front\s+matter)\b",
    re.I,
)

INFORMATIVE_CUE_PAT = re.compile(
    r"\b(?:we\s+show|is\s+defined\s+as|the\s+main\s+idea|in\s+this\s+section|we\s+study|we\s+present|in\s+this\s+chapter|this\s+chapter\s+covers|algorithm\s+for|solves?\s+the|technique\s+for|we\s+describe)\b",
    re.I,
)


def _get_lexical_db_path(custom_path: Optional[str | Path] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    return Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"


def build_document_summary(
    document_id: str,
    db_path: Optional[str | Path] = None,
    max_sections: int = 25,
) -> Dict[str, Any]:
    """
    Builds a deterministic executive summary for a single document:
    - Title, author (if known)
    - 1-paragraph overview from first non-front-matter chunk (reflowed)
    - Outline of key sections with 1-2 bullet points each + [p. X] citations
    """
    path = _get_lexical_db_path(db_path)
    if not path.is_file():
        return {"answer": "Lexical index not found.", "sources": [], "chapters_count": 0, "citations_count": 0}

    sa = SentenceAnalyzer()
    uri = path.resolve().as_uri() + "?mode=ro"
    
    with sqlite3.connect(uri, uri=True, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row

        # 1. Document metadata
        meta_row = conn.execute(
            "SELECT filename, title FROM lexical_chunks WHERE document_id = ? LIMIT 1",
            (document_id,),
        ).fetchone()
        if not meta_row:
            return {"answer": "Document not found in library index.", "sources": [], "chapters_count": 0, "citations_count": 0}

        filename = meta_row["filename"] or ""
        title = meta_row["title"] or filename

        # Infer authors / humanized title
        if "cormen" in filename.lower() or "cormen" in title.lower():
            display_title = "Introduction to Algorithms (3rd Edition)"
            author = "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein"
        elif "horowitz" in filename.lower():
            display_title = "Fundamentals of Computer Algorithms (2nd Edition)"
            author = "Ellis Horowitz, Sartaj Sahni, Sanguthevar Rajasekaran"
        else:
            display_title = title
            author = ""

        # 2. First non-front-matter chunk for 1-paragraph overview
        first_body_row = conn.execute(
            """
            SELECT chunk_id, page_start, text, section
            FROM lexical_chunks
            WHERE document_id = ? AND page_start >= 20 AND length(text) > 200
            ORDER BY page_start ASC
            LIMIT 1
            """,
            (document_id,),
        ).fetchone()

        overview_text = ""
        overview_page = 1
        overview_cid = ""
        if first_body_row:
            overview_page = first_body_row["page_start"]
            overview_cid = first_body_row["chunk_id"]
            sentences = sa.segment_sentences(clean_passage_text(first_body_row["text"]))
            valid_s = [
                s for s in sentences
                if len(s) > 30 and not JUNK_HEADING_PAT.search(s) and not s.strip().endswith("?")
            ]
            overview_text = reflow_text(" ".join(valid_s[:3]))

        # 3. Retrieve distinct major sections ordered by page_start
        cur = conn.execute(
            """
            SELECT section, MIN(page_start) as p_start, chunk_id, text
            FROM lexical_chunks
            WHERE document_id = ? AND page_start >= 20 AND section IS NOT NULL AND length(trim(section)) > 3
            GROUP BY section
            ORDER BY p_start ASC
            """,
            (document_id,),
        )

        sections = []
        seen_sec = set()
        for r in cur.fetchall():
            sec = r["section"].strip()
            if JUNK_HEADING_PAT.search(sec) or re.search(r"^\d+\s*$", sec):
                continue
            sec_norm = re.sub(r"[\s\.:\-_]+", " ", sec).strip().lower()
            if sec_norm in seen_sec:
                continue
            seen_sec.add(sec_norm)

            is_chapter = bool(re.search(r"\b(?:chapter\s+\d+|part\s+[ivx]+|\d+\.\d+)\b", sec, re.I))
            if is_chapter or (r["p_start"] > 22 and len(sections) < max_sections):
                sections.append({
                    "section": sec,
                    "page": r["p_start"],
                    "chunk_id": r["chunk_id"],
                    "text": r["text"],
                })

        lines = [
            f"# Executive Research Summary: {display_title}",
        ]
        if author:
            lines.append(f"**Authors:** {author}\n")
        if overview_text:
            lines.extend([
                "### Overview",
                f"{overview_text} [p. {overview_page}]",
                "",
            ])

        lines.append("### Key Structural Sections & Core Coverage")

        sources = []
        cited_count = 0
        if overview_cid:
            sources.append({
                "source_id": f"S{len(sources)+1}",
                "page": overview_page,
                "chunk_id": overview_cid,
                "locator": f"p.{overview_page}",
                "title": display_title,
                "filename": filename,
            })

        for sec_info in sections[:max_sections]:
            sec_name = sec_info["section"]
            p_num = sec_info["page"]
            clean_t = clean_passage_text(sec_info["text"])
            sentences = sa.segment_sentences(clean_t)

            bullets = []
            for s in sentences:
                s_str = reflow_text(s.strip())
                if len(s_str) > 30 and not JUNK_HEADING_PAT.search(s_str) and not s_str.endswith("?"):
                    bullets.append(s_str)
                    break

            for s in sentences:
                s_str = reflow_text(s.strip())
                if INFORMATIVE_CUE_PAT.search(s_str) and s_str not in bullets and len(s_str) > 30:
                    bullets.append(s_str)
                    break

            if not bullets and sentences:
                bullets.append(reflow_text(sentences[0].strip()))

            if bullets:
                lines.append(f"#### {sec_name} (Page {p_num})")
                for b in bullets[:2]:
                    lines.append(f"- {b} [p. {p_num}]")
                    cited_count += 1
                lines.append("")
                sources.append({
                    "source_id": f"S{len(sources)+1}",
                    "page": p_num,
                    "chunk_id": sec_info["chunk_id"],
                    "locator": f"p.{p_num}",
                    "section": sec_name,
                    "title": display_title,
                    "filename": filename,
                })

        markdown = "\n".join(lines).strip()
        return {
            "answer": markdown,
            "sources": sources,
            "chapters_count": len(sections[:max_sections]),
            "citations_count": cited_count,
        }


def build_paper_summary(
    paper_id: str,
    user_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Builds a summary for a paper (which may contain one or multiple documents).
    """
    path = _get_lexical_db_path(db_path)
    if not path.is_file():
        return {"answer": "Lexical index not found.", "sources": [], "chapters_count": 0, "citations_count": 0}

    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        
        # Discover documents for this paper
        if document_ids:
            target_doc_ids = document_ids
        else:
            cur = conn.execute(
                "SELECT DISTINCT document_id FROM lexical_chunks WHERE paper_id = ?",
                (paper_id,),
            )
            target_doc_ids = [r[0] for r in cur.fetchall() if r[0]]

    if not target_doc_ids:
        # Check if paper_id was actually a document_id
        return build_document_summary(paper_id, db_path=db_path)

    if len(target_doc_ids) == 1:
        return build_document_summary(target_doc_ids[0], db_path=db_path)

    # Multi-document paper: summarize each document
    all_answers = []
    all_sources = []
    total_chapters = 0
    total_citations = 0

    for doc_id in target_doc_ids:
        doc_res = build_document_summary(doc_id, db_path=db_path, max_sections=15)
        if doc_res.get("answer"):
            all_answers.append(doc_res["answer"])
            all_sources.extend(doc_res.get("sources", []))
            total_chapters += doc_res.get("chapters_count", 0)
            total_citations += doc_res.get("citations_count", 0)

    combined_answer = "\n\n---\n\n".join(all_answers)
    return {
        "answer": combined_answer,
        "sources": all_sources,
        "chapters_count": total_chapters,
        "citations_count": total_citations,
    }

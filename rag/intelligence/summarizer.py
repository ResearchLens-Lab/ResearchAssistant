"""
Deterministic Research Summary Builder.
Extracts structured executive summaries and section outlines directly from
document chunks, lexical indexes, and structured metadata without requiring language models.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rag.config.settings import settings
from rag.intelligence.answer_composer import clean_passage_text, reflow_text
from rag.intelligence.sentence_analyzer import SentenceAnalyzer
from rag.ingestion.structure_extractor import is_valid_heading_title

logger = logging.getLogger(__name__)

OVERVIEW_SIGNALS = re.compile(
    r"\b(?:is\s+defined\s+as|introduces|covers|studies|provides\s+a\s+comprehensive|algorithms?\s+(?:are|lie|is)|we\s+present|primary\s+goal|fundamental|objective\s+of|this\s+book)\b",
    re.I,
)

EXERCISE_OR_PROBLEM = re.compile(
    r"\b(?:homework|exercises?|problem\s+\d+|solution|city\s+\"a\"|flight,\s*by\s*bus|copyright|all\s+rights\s+reserved|isbn|explain\s+how|show\s+that|prove\s+that|design\s+an?\s+algorithm|suppose\s+that|assume\s+that|what\s+is\s+the|find\s+the|calculate|determine\s+whether)\b",
    re.I,
)

EXERCISE_INSTRUCTION = re.compile(
    r"^(?:[a-z0-9\.\-]+\s+|\([a-z0-9]+\)\s+)?(?:fill\s+in|show\s+that|prove\s+that|argue\s+that|give\s+(?:an?|a\s+formula|an?\s+algorithm|pseudocode)|find\s+(?:an?|the)|compute\s+(?:the|an?)|suppose\s+that|assume\s+that|draw\s+the|trace\s+the|write\s+(?:an?|pseudocode)|consider\s+the\s+problem\s+of|describe\s+how\s+to|how\s+(?:many|much|long)|what\s+is\s+the|which\s+of\s+the|state\s+whether|determine\s+(?:whether|if|the)|hint\s*:|present\s+an?|see\s+if\s+you\s+can|analyze\s+the\s+(?:running\s+time|complexity))\b|^(?:Analyze|Present|Explain|Describe|Design|Implement|Develop|Formulate|Devise|Construct|Demonstrate)\s+(?:an?|the|how)\b",
    re.I,
)

TRANSITION_SENTENCE = re.compile(
    r"\b(?:as\s+we\s+shall\s+see|in\s+the\s+next\s+section|in\s+this\s+section|in\s+this\s+chapter|the\s+following\s+pseudocode|see\s+figure|shown\s+in\s+figure|refer\s+to\s+table|illustrated\s+in|recall\s+from\s+section|discussed\s+above)\b",
    re.I,
)

FIGURE_OR_TABLE = re.compile(
    r"\b(?:Figure\s+\d+|Table\s+\d+|Caption)\b",
    re.I,
)

FRONT_MATTER_SIGNS = re.compile(
    r"\b(?:isbn|publisher|printed\s+in|all\s+rights\s+reserved|copyright\s+page|contents|table\s+of\s+contents|editorial\s+board|library\s+of\s+congress|madison\s+avenue|typeset\s+by|exam\s+i|exam\s+ii|exam\s+iii|assignment\s+[i|v|x]+|semester\s*-|syllabus)\b",
    re.I,
)

JUNK_HEADING_PAT = re.compile(
    r"^(?:isbn|qa\d+|contents|table\s+of\s+contents|index|acknowledgements?|copyright\s+page|title\s+page|other\s+books\s+by|bibliography|references|author\s+index|subject\s+index|front\s+matter|header\s*/\s*front\s+matter)\b|^\d+\s*$",
    re.I,
)

PSEUDOCODE_OR_CODE = re.compile(
    r"\b(?:spawn|sync|return\s+[a-z]|let\s+[a-z]Œ|\bfor\s+i\s*=|while\s*\(|def\s+[a-z_]+\(|class\s+[A-Z])\b|//|/\*|Problems\s+for\s+Chapter",
    re.I,
)


def is_repetitive_text(s: str) -> bool:
    """Detects repetitive table/diagram/matrix fragments."""
    words = [w.lower() for w in re.findall(r"\b\w+\b", s)]
    if len(words) >= 6:
        max_count = max(words.count(w) for w in set(words))
        if max_count / len(words) > 0.20:
            return True
    for n in (2, 3):
        if len(words) >= n * 3:
            ngrams = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
            if ngrams and max(ngrams.count(ng) for ng in set(ngrams)) >= 3:
                return True
    return False


FIGURE_LAYOUT_DESCRIPTION = re.compile(
    r"\b(?:above\s+and\s+below|on\s+the\s+left|on\s+the\s+right|in\s+the\s+tree\s+shown|in\s+part\s+\([a-z]\)|the\s+node\s+at\s+index|the\s+number\s+within\s+the\s+circle|the\s+shaded|dashed\s+lines?|horizontal\s+axis|vertical\s+axis|points?\s+in\s+the\s+plane)\b",
    re.I,
)

PROOF_STEP_PREFIX = re.compile(
    r"^(?:Initialization|Maintenance|Termination|Base\s+case|Inductive\s+step|Step\s+\d+)\s*:",
    re.I,
)

DAMAGED_OCR_OR_LIGATURE = re.compile(
    r"[\x80-\x9f]|Œ|‚|\b(?:AŒ|TŒ|bi=2c|O\.[a-z0-9]|C\s+1\b)",
)


def is_genuine_section_title(title: str) -> bool:
    """Rejects prefatory running sentences mistakenly matched as headings."""
    if not title:
        return False
    t = title.strip()
    if len(t) < 3 or len(t) > 65:
        return False
    # Reject exercise/problem sections
    if re.search(r"\b(?:exercises?|problems?|solutions?|additional\s+exercises?)\b", t, re.I):
        return False
    # Reject raw DNA/nucleotide sequence tokens
    if re.match(r"^[ACGTUacgtu\s]+$", t) and len(t) > 6:
        return False
    # Reject generic single-word titles or single verbs
    words = t.split()
    if len(words) == 1 and t.lower() in (
        "delete", "insert", "search", "extract", "sort", "merge", "conclusion",
        "discussion", "methodology", "related", "work", "background", "results",
        "overview", "table", "figure", "case", "proof"
    ):
        return False
    # Reject headings ending in incomplete modifiers
    if re.search(r"\b(?:simplified|additional|some|various|certain|following)\s*$", t, re.I):
        return False
    # Reject index entries like "Witness, 969" or page reference headings
    if re.search(r",\s*\d+$", t):
        return False
    # Reject problem labels like "I: 73" or single letters before colons
    if re.match(r"^[A-Z]\s*:\s*\d+", t):
        return False
    # Reject variable/formula sequences like "Tp T1 T1"
    if not any(len(w) >= 3 and w.isalpha() for w in words):
        return False
    if re.search(r"\b[A-Za-z]\d+\b", t):
        return False
    m = re.match(r"^Chapter\s+\d+:\s*(.+)$", t, re.I)
    if m:
        sub = m.group(1).strip()
        if not sub or not sub[0].isupper():
            return False
        if sub[0] in "([{\"'`)]},;:!?.|\\/":
            return False
        if re.search(r"\b(?:provides|gives|shows|contains|discusses|defines|deﬁnes|presents|explains|lists|introduces|using|computing|then\s+goes|for\s+more)\b", sub, re.I):
            return False
        if sub.endswith((".", ",", ";", ":", "-")):
            return False
        if len(sub.split()) > 7:
            return False
    if re.search(r"\b(?:provides|gives|shows|contains|discusses|defines|deﬁnes|presents|explains|lists|using|computing)\b", t, re.I):
        return False
    if t.endswith((".", ",", ";", ":", "-")):
        return False
    return is_strict_heading(t)


def score_bullet_sentence(s: str) -> float:
    """Strictly evaluates whether a sentence is a substantive section summary bullet."""
    if len(s) < 35 or len(s) > 280:
        return -100.0
    if not s.strip().endswith("."):
        return -100.0
    if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
        return -100.0
    # Avoid hanging abbreviations or incomplete fragments
    if re.search(r"\b(?:c|e\.g|i\.e|al|etc|vs|p|pp)\.$", s, re.I):
        return -100.0
    if re.search(r"[,;:\-]\s*$", s[:-1]):
        return -100.0
    if FIGURE_LAYOUT_DESCRIPTION.search(s) or FIGURE_OR_TABLE.search(s):
        return -100.0
    if PROOF_STEP_PREFIX.search(s):
        return -100.0
    if DAMAGED_OCR_OR_LIGATURE.search(s):
        return -100.0
    if EXERCISE_INSTRUCTION.search(s) or EXERCISE_OR_PROBLEM.search(s):
        return -100.0
    if TRANSITION_SENTENCE.search(s):
        return -100.0
    if is_repetitive_text(s):
        return -100.0
    # Reject back-of-the-book index entries with multiple page numbers
    if len(re.findall(r",\s*\d+\b", s)) >= 3:
        return -100.0
    if PSEUDOCODE_OR_CODE.search(s):
        return -100.0
    words = re.findall(r"\b\w+\b", s.lower())
    if len(words) < 7:
        return -100.0
    if len(set(words)) / len(words) < 0.60:
        return -100.0
    num_digits = sum(1 for w in words if w.isdigit())
    if num_digits / len(words) > 0.15:
        return -100.0

    score = 1.0
    s_low = s.lower()
    # High-value definitions and algorithmic explanations
    if re.search(r"\b(?:is\s+an?\s+algorithm|is\s+a\s+(?:method|technique|data\s+structure|procedure|framework)|solves\s+the|designed\s+to|computes\s+the|finds\s+the|operates\s+by|works\s+by|introduces\s+the|main\s+idea|fundamental\s+concept)\b", s_low):
        score += 5.0
    if re.search(r"\b(?:running\s+time|worst-case|time\s+complexity|space\s+complexity|in\s+O\(|in\s+\w+\s+time)\b", s_low):
        score += 3.0
    if re.search(r"\b(?:algorithm|sorting|recurrence|dynamic\s+programming|graph|shortest\s+path|spanning\s+tree|search)\b", s_low):
        score += 2.0
    return score


def _get_lexical_db_path(custom_path: Optional[str | Path] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    # If explicit CHROMA_PERSIST_DIR is set to a non-default directory
    p = Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"
    if str(settings.chroma_persist_dir) not in (".", ".chroma") and p.is_file():
        return p
    # Check standard Desktop library directory
    desktop_lex = Path.home() / "Documents" / "ResearchLens Library" / "indexes" / "researchlens_lexical.sqlite3"
    if desktop_lex.is_file():
        return desktop_lex
    return p


def _get_library_db_path() -> Path:
    try:
        from backend.app.core.config import get_settings
        db_url = get_settings().database_url
        if "sqlite" in db_url:
            clean = re.sub(r"^sqlite\+[a-z0-9]+:\/\/\/", "", db_url)
            clean = re.sub(r"^sqlite:\/\/\/", "", clean)
            p = Path(clean)
            if p.is_file():
                return p
    except Exception:
        pass

    desktop_db = Path.home() / "Documents" / "ResearchLens Library" / "library.sqlite3"
    if desktop_db.is_file():
        return desktop_db

    p = Path(settings.chroma_persist_dir).parent / "library.sqlite3"
    if p.is_file():
        return p

    return desktop_db


def is_strict_heading(title: str) -> bool:
    """Strict heading filter for summary sections."""
    if not title:
        return False
    title = title.strip()
    if len(title) < 3 or len(title) > 70:
        return False
    # Reject opening/closing parens, brackets, punctuation
    if title[0] in "([{\"'`)]},;:!?.|\\/":
        return False
    if title[-1] in ")]},;:!?.|\\/`":
        return False
    if not (title[0].isupper() or title[0].isdigit()):
        return False
    # If starts with digit, must be a section number like "1.1", "1.2.3"
    if title[0].isdigit() and not re.match(r"^\d+(?:\.\d+)+\b", title):
        return False
    # Reject appendix exercise labels like "B.4-6"
    if re.match(r"^[A-Z]\.\d+[\-\d]*\b", title):
        return False
    # Reject math expressions or formulas with operators
    if re.search(r"[=<>\+\*\/_~]", title) or re.search(r"\b[A-Z0-9]+\s+[CD]\s+[A-Z0-9]+", title):
        return False
    words = title.split()
    if len(words) > 8:
        return False
    if sum(1 for w in words if len(w) == 1) > len(words) * 0.3:
        return False
    # Reject colon followed by lowercase or comma
    if re.search(r":\s*[,a-z]", title):
        return False
    # Reject sentence continuations
    if re.search(r"\b(?:gives|using|which|where|when|that|and)\b", title.lower()) and len(words) > 3:
        return False
    # Reject repetitive characters
    if re.search(r"(.)\1{3,}", title):
        return False
    return is_valid_heading_title(title)


def clean_display_title(filename: str, raw_title: str = "") -> str:
    """Derives a clean document display title without hardcoded author lookups."""
    fn_clean = ""
    if filename and not filename.startswith("doc_"):
        fn_clean = re.sub(r"\.[^.]+$", "", filename)
        fn_clean = fn_clean.replace("_", " ").replace("-", " ")
        fn_clean = " ".join(fn_clean.split()).strip()

    raw_clean = raw_title.strip() if raw_title and not raw_title.startswith("doc_") else ""

    # If raw_clean is short/generic or filename has more specific title info, prefer filename
    if fn_clean and (not raw_clean or len(fn_clean) > len(raw_clean)):
        return fn_clean
    return raw_clean or fn_clean or "Research Document"


def build_document_summary(
    document_id: str,
    db_path: Optional[str | Path] = None,
    max_sections: int = 10,
    start_source_idx: int = 1,
) -> Dict[str, Any]:
    """
    Builds a deterministic executive summary for a single document:
    - 1-paragraph overview from first substantive introductory chunk (with precise citation)
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
            "SELECT filename, title, paper_id FROM lexical_chunks WHERE document_id = ? LIMIT 1",
            (document_id,),
        ).fetchone()
        if not meta_row:
            return {"answer": "Document not found in library index.", "sources": [], "chapters_count": 0, "citations_count": 0}

        filename = meta_row["filename"] or ""
        paper_id = meta_row["paper_id"] or ""
        display_title = clean_display_title(filename, meta_row["title"] or "")

        # 2. Overview Selection
        cand_chunks = conn.execute(
            """
            SELECT c.chunk_id, c.page_start, c.page_end, c.section, c.text,
                   m.section_type, m.printed_page_label
            FROM lexical_chunks c
            LEFT JOIN lexical_metadata m ON c.chunk_id = m.chunk_id
            WHERE c.document_id = ?
              AND (m.section_type IS NULL OR m.section_type NOT IN ('index', 'bibliography', 'exercises', 'table_figure'))
              AND (c.section IS NULL OR (c.section NOT LIKE '%Index%' AND c.section NOT LIKE '%Contents%'))
              AND length(c.text) > 120
            ORDER BY c.page_start ASC
            LIMIT 100
            """,
            (document_id,),
        ).fetchall()

        scored_sentences = []
        for chk in cand_chunks:
            sec = (chk["section"] or "").lower()
            # Skip chunks on early TOC pages when section says "Chapter N"
            if chk["page_start"] <= 13 and re.search(r"chapter\s+[4-9]|\bchapter\s+\d{2,}", sec):
                continue

            t = chk["text"]
            lines_t = [l.strip() for l in t.split("\n") if l.strip()]
            if len(lines_t) > 5 and sum(1 for l in lines_t if l.isdigit() or len(l) < 5) > len(lines_t) * 0.4:
                continue
            if FRONT_MATTER_SIGNS.search(t[:200]):
                continue

            sentences = sa.segment_sentences(clean_passage_text(t))
            for s in sentences:
                s_clean = reflow_text(s)
                if len(s_clean) < 45 or len(s_clean) > 300:
                    continue
                if not s_clean[0].isupper() or not s_clean.endswith("."):
                    continue
                if EXERCISE_OR_PROBLEM.search(s_clean) or PSEUDOCODE_OR_CODE.search(s_clean):
                    continue

                score = 0.0
                if OVERVIEW_SIGNALS.search(s_clean):
                    score += 3.0
                if "algorithm" in s_clean.lower() or "research" in s_clean.lower():
                    score += 2.0
                # Prioritize opening sections (Introduction, Chapter 1, Preface)
                if any(k in sec for k in ("intro", "chapter 1", "chapter 01", "preface", "overview")):
                    score += 5.0
                elif any(k in sec for k in ("chapter 2", "chapter 3", "chapter 4", "chapter 5")):
                    score += 1.0

                scored_sentences.append((score, s_clean, chk))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)

        sources: List[Dict[str, Any]] = []
        lines: List[str] = []
        source_counter = start_source_idx

        if scored_sentences:
            top_s = scored_sentences[0]
            sid = f"S{source_counter}"
            source_counter += 1
            p_start = top_s[2]["page_start"]
            lines.append(f"{top_s[1]} [{sid}] [p. {p_start}]\n")
            sources.append({
                "source_id": sid,
                "document_id": document_id,
                "paper_id": paper_id,
                "chunk_id": top_s[2]["chunk_id"],
                "page": p_start,
                "page_start": p_start,
                "page_end": top_s[2]["page_end"],
                "locator": f"p. {p_start}",
                "section": top_s[2]["section"] or "Overview",
                "title": display_title,
                "filename": filename,
                "paper_title": display_title,
                "citation_label": f"[{sid}]",
                "text": top_s[1],
            })

        # 3. Retrieve Key Sections
        sec_rows = conn.execute(
            """
            SELECT c.section, c.chunk_id, c.page_start, c.page_end, c.text,
                   m.printed_page_label, m.section_type
            FROM lexical_chunks c
            LEFT JOIN lexical_metadata m ON c.chunk_id = m.chunk_id
            WHERE c.document_id = ?
              AND c.section IS NOT NULL AND length(trim(c.section)) > 3
              AND length(c.text) > 150
              AND (c.page_end - c.page_start) <= 30
            ORDER BY c.page_start ASC
            """,
            (document_id,),
        ).fetchall()

        seen_sec = set()
        valid_sections = []
        for r in sec_rows:
            sec_name = r["section"].strip()
            stype = r["section_type"]
            if stype in ("front_matter", "index", "bibliography", "exercises"):
                continue
            if not is_genuine_section_title(sec_name) or JUNK_HEADING_PAT.search(sec_name):
                continue
            # Skip fake TOC sections on early pages (page_start <= 22)
            if r["page_start"] <= 22:
                continue
            # Reject isolated generic single-word headings that are often diagram/table columns
            if sec_name.lower() in ("conclusion", "discussion", "methodology", "related work"):
                continue
            # Skip sections whose text is TOC dot leaders or syllabus
            if re.search(r"\.{4,}|\-{4,}", r["text"]):
                continue
            if FRONT_MATTER_SIGNS.search(r["text"][:150]):
                continue

            sentences = sa.segment_sentences(clean_passage_text(r["text"]))
            scored = [(score_bullet_sentence(s), reflow_text(s)) for s in sentences]
            scored = [x for x in scored if x[0] > 0]
            if not scored:
                continue

            # Pick highest scoring sentence in the chunk
            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_sent = scored[0]

            norm_name = re.sub(r"[^a-z0-9]+", " ", sec_name.lower()).strip()
            if norm_name in seen_sec:
                continue
            seen_sec.add(norm_name)
            valid_sections.append((r, best_sent, best_score))

        if valid_sections:
            lines.append("#### Key Sections\n")
            # Representative stratified selection across the document's page span
            if len(valid_sections) <= max_sections:
                selected_sections = [(x[0], x[1]) for x in valid_sections]
            else:
                valid_sections.sort(key=lambda x: x[0]["page_start"])
                min_p = valid_sections[0][0]["page_start"]
                max_p = valid_sections[-1][0]["page_start"]
                span = max(1, max_p - min_p)
                step = span / max_sections

                strata: List[List[Any]] = [[] for _ in range(max_sections)]
                for item in valid_sections:
                    p = item[0]["page_start"]
                    b_idx = min(max_sections - 1, int((p - min_p) / step))
                    strata[b_idx].append(item)

                selected_sections = []
                for bucket in strata:
                    if bucket:
                        best = max(bucket, key=lambda x: x[2])
                        selected_sections.append((best[0], best[1]))

                if len(selected_sections) < max_sections:
                    used_chunks = {s[0]["chunk_id"] for s in selected_sections}
                    remaining = [x for x in valid_sections if x[0]["chunk_id"] not in used_chunks]
                    remaining.sort(key=lambda x: x[2], reverse=True)
                    for item in remaining:
                        if len(selected_sections) >= max_sections:
                            break
                        selected_sections.append((item[0], item[1]))

                selected_sections.sort(key=lambda x: x[0]["page_start"])

            for sec_row, bullet in selected_sections:
                sec_name = sec_row["section"].strip()
                p_start = sec_row["page_start"]
                lbl = sec_row["printed_page_label"]
                page_str = f"Page {p_start}" if not lbl or lbl == str(p_start) else f"Page {p_start} (labeled {lbl})"

                sid = f"S{source_counter}"
                source_counter += 1
                lines.append(f"- **{sec_name}** ({page_str}): {bullet} [{sid}] [p. {p_start}]")
                sources.append({
                    "source_id": sid,
                    "document_id": document_id,
                    "paper_id": paper_id,
                    "chunk_id": sec_row["chunk_id"],
                    "page": p_start,
                    "page_start": p_start,
                    "page_end": sec_row["page_end"],
                    "locator": f"p. {p_start}",
                    "section": sec_name,
                    "title": display_title,
                    "filename": filename,
                    "paper_title": display_title,
                    "citation_label": f"[{sid}]",
                    "text": bullet,
                })

        return {
            "answer": "\n".join(lines).strip(),
            "sources": sources,
            "chapters_count": len(valid_sections[:max_sections]),
            "citations_count": len(sources),
        }


def build_paper_summary(
    paper_id: str,
    user_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Builds a summary for a project/paper, deduplicating exact-content sources
    using verified hashes within the authorized scope.
    """
    lib_path = _get_library_db_path()
    distinct_docs = []

    if lib_path.is_file():
        try:
            with sqlite3.connect(lib_path, timeout=10.0) as lib_conn:
                lib_conn.row_factory = sqlite3.Row
                query = "SELECT id, filename, storage_path, file_hash_sha256, chunk_count FROM documents WHERE paper_id = ? AND processing_status = 'indexed'"
                params = [paper_id]
                if document_ids:
                    placeholders = ",".join("?" for _ in document_ids)
                    query += f" AND id IN ({placeholders})"
                    params.extend(document_ids)

                rows = lib_conn.execute(query, params).fetchall()

                # Deduplicate by SHA-256 hash
                doc_groups: Dict[str, List[Any]] = {}
                for row in rows:
                    h = row["file_hash_sha256"]
                    if not h and row["storage_path"]:
                        p = Path(row["storage_path"])
                        if p.exists():
                            h = hashlib.sha256(p.read_bytes()).hexdigest()
                    key = h or row["filename"]
                    doc_groups.setdefault(key, []).append(row)

                for _, grp in doc_groups.items():
                    best = max(grp, key=lambda x: x["chunk_count"] or 0)
                    distinct_docs.append(best["id"])
        except Exception as exc:
            logger.warning("Failed deduplicating via library.sqlite3: %s", exc)

    if not distinct_docs:
        # Fallback to lexical chunks discovery
        path = _get_lexical_db_path(db_path)
        if path.is_file():
            uri = path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=10.0) as conn:
                cur = conn.execute(
                    "SELECT DISTINCT document_id FROM lexical_chunks WHERE paper_id = ?",
                    (paper_id,),
                )
                distinct_docs = [r[0] for r in cur.fetchall() if r[0]]

    if not distinct_docs:
        return build_document_summary(paper_id, db_path=db_path)

    if len(distinct_docs) == 1:
        return build_document_summary(distinct_docs[0], db_path=db_path)

    # Multi-document project: summarize each distinct document with unified citation numbering
    all_answers = []
    all_sources = []
    total_chapters = 0

    for doc_id in distinct_docs:
        doc_res = build_document_summary(
            doc_id,
            db_path=db_path,
            max_sections=8,
            start_source_idx=len(all_sources) + 1,
        )
        if doc_res.get("answer"):
            srcs = doc_res.get("sources") or []
            doc_title = srcs[0].get("title", "Document") if srcs else "Document"
            all_answers.append(f"### {doc_title}\n\n" + doc_res["answer"])
            all_sources.extend(srcs)
            total_chapters += doc_res.get("chapters_count", 0)

    combined_answer = "\n\n---\n\n".join(all_answers)
    return {
        "answer": combined_answer,
        "sources": all_sources,
        "chapters_count": total_chapters,
        "citations_count": len(all_sources),
    }

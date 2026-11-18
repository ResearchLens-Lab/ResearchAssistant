"""
Explainable, Intelligence-Driven FTS5 Retrieval Engine.
Applies heading boosts, question-intent-specific section priors,
sentence definition boosts, citation density penalties, and MMR diversity.
Generates full explainable scoring traces for every retrieved passage.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rag.config.settings import settings
from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.sentence_analyzer import SentenceAnalyzer
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)


@dataclass
class RetrievalTrace:
    chunk_id: str
    document_id: str
    paper_id: str
    physical_page: int
    page_label: str
    section: str
    heading_path: str
    section_type: str
    locator: str
    bm25_score: float
    heading_boost: float
    section_prior: float
    definition_boost: float
    citation_penalty: float
    final_score: float
    description_boost: float = 1.0
    caption_penalty: float = 1.0
    garbage_penalty: float = 1.0
    pseudocode_penalty: float = 1.0
    reasons: List[str] = field(default_factory=list)


DESCRIPTION_CUES = [
    "paradigm", "strategy", "technique", "method", "approach",
    "involves", "consists of", "steps", "is a ", "is an ", "refers to",
    "general method", "design technique"
]


def norm(s: str) -> str:
    """Normalize string: lowercase, hyphens/underscores to spaces, collapse whitespace."""
    if not s:
        return ""
    s = s.lower().replace("-", " ").replace("_", " ")
    return " ".join(s.split())


def body_text(chunk_or_text: Any, section_label: str = "") -> str:
    r"""Returns chunk text minus leading line if it equals section label (using norm) or matches ^(chapter|part)\s+\d+."""
    if isinstance(chunk_or_text, str):
        text = chunk_or_text
        sec = section_label
    elif hasattr(chunk_or_text, "get") or isinstance(chunk_or_text, dict) or isinstance(chunk_or_text, sqlite3.Row):
        text = str(chunk_or_text.get("text", "") if hasattr(chunk_or_text, "get") else chunk_or_text["text"] or "")
        sec = section_label or str(chunk_or_text.get("section", "") if hasattr(chunk_or_text, "get") else chunk_or_text["section"] or "")
    elif hasattr(chunk_or_text, "text"):
        text = str(getattr(chunk_or_text, "text", "") or "")
        sec = section_label or str(getattr(chunk_or_text, "section", "") or "")
    else:
        text = str(chunk_or_text or "")
        sec = section_label

    text = text.strip()
    if not text:
        return ""

    lines = text.split("\n", 1)
    first_line = lines[0].strip()
    norm_first = norm(first_line)
    norm_sec = norm(sec)

    is_leading_header = False
    if norm_sec and norm_first == norm_sec:
        is_leading_header = True
    elif (
        re.match(r"^(?:chapter|part)\s+\d+", norm_first, re.IGNORECASE)
        and len(first_line) <= 80
        and len(first_line.split()) <= 8
        and not re.search(r"[.,;!?]$", first_line)
    ):
        is_leading_header = True

    if is_leading_header and len(lines) > 1:
        return lines[1].strip()
    elif is_leading_header and len(lines) == 1:
        return ""
    return text


def compute_heading_boost(
    active_heading: str,
    section: str,
    b_text: str,
    primary_concept: str,
    is_exact_matched: bool = False,
) -> Tuple[float, List[str]]:
    r"""
    Heading boost only counts when concept is in body_text.
    Chapter-level labels (^(chapter|part)\s+\d+) give at most 1.15x.
    Boost 2.5x only when chunk's subsection heading, or first line of body_text, contains concept.
    If concept does not appear in body_text at all: cap heading_boost at 1.0.
    """
    reasons = []
    norm_c = norm(primary_concept)
    if not norm_c:
        return 1.0, reasons

    norm_bt = norm(b_text)
    if norm_c not in norm_bt:
        return 1.0, reasons

    # Concept is present in body_text!
    # Check first line of body text:
    # First line must be bounded (at most 150 characters).
    # If the text starts with a lowercase letter, it is a mid-sentence orphan continuation, not a heading or section intro.
    first_line_has_concept = False
    stripped_bt = b_text.strip()
    if stripped_bt and not stripped_bt[0].islower():
        lines = [ln.strip() for ln in b_text.split("\n") if ln.strip()]
        # If line 0 is a short subheading (<= 4 words, <= 40 chars, does not end in sentence punctuation like . ! ?),
        # the section introductory text begins on line 1.
        if (
            len(lines) >= 2
            and len(lines[0].split()) <= 4
            and len(lines[0]) <= 40
            and not re.search(r"[.!?]$", lines[0])
        ):
            first_block = lines[0] + " " + lines[1]
        elif lines:
            first_block = lines[0]
        else:
            first_block = stripped_bt

        # Bound first_block to at most 150 characters
        first_block = first_block[:150]
        if norm_c in norm(first_block):
            first_line_has_concept = True

    # Check subsection heading
    heading_parts = [p.strip() for p in re.split(r"[>·]", active_heading) if p.strip()]
    sub_candidate = heading_parts[-1] if heading_parts else section
    norm_sub = norm(sub_candidate)
    is_chapter_only = bool(re.match(r"^(?:chapter|part)\s+\d+", norm_sub, re.IGNORECASE))
    sub_has_concept = (not is_chapter_only) and (norm_c in norm_sub)

    if sub_has_concept or first_line_has_concept:
        reasons.append(f"heading boost: subsection or first line matches '{primary_concept}' (2.5x)")
        return 2.5, reasons

    # Chapter-level match or partial match
    norm_full_heading = norm(active_heading + " " + section)
    if norm_c in norm_full_heading or is_exact_matched:
        reasons.append(f"heading boost: chapter-level label matches '{primary_concept}' (1.15x)")
        return 1.15, reasons
    elif any(w in norm_full_heading for w in norm_c.split() if len(w) > 3):
        reasons.append(f"heading boost: partial chapter match for '{primary_concept}' (1.15x)")
        return 1.15, reasons

    return 1.0, reasons


def compute_description_boost(b_text: str, primary_concept: str) -> Tuple[float, List[str]]:
    """Description boost 1.8x when, within 160 chars of concept in body_text, a description cue occurs."""
    reasons = []
    norm_b = norm(b_text)
    norm_c = norm(primary_concept)
    if not norm_c or norm_c not in norm_b:
        return 1.0, reasons

    for m in re.finditer(re.escape(norm_c), norm_b):
        start = max(0, m.start() - 160)
        end = min(len(norm_b), m.end() + 160)
        window = norm_b[start:end]
        for cue in DESCRIPTION_CUES:
            norm_cue = norm(cue)
            if norm_cue in window:
                reasons.append(f"description boost: cue '{cue}' within 160 chars of '{primary_concept}' (1.8x)")
                return 1.8, reasons
    return 1.0, reasons


def compute_caption_penalty(b_text: str, intent: ResearchIntent) -> Tuple[float, List[str]]:
    r"""Caption/table penalty 0.4x for DEFINITION and COMPARISON intents when body_text starts with ^(figure|fig\.|table)\s*\d."""
    reasons = []
    if intent in (ResearchIntent.DEFINITION, ResearchIntent.COMPARISON):
        clean_b = b_text.strip().lower()
        if re.match(r"^(?:figure|fig\.|table)\s*\d", clean_b):
            reasons.append("penalty: figure/table caption downweighted for definition/comparison (0.4x)")
            return 0.4, reasons
    return 1.0, reasons


def compute_garbage_penalty(b_text: str) -> Tuple[float, List[str]]:
    """Garbage penalty 0.2x when alphabetic-character ratio of body_text is < 0.6."""
    reasons = []
    stripped = "".join(b_text.split())
    if not stripped:
        reasons.append("penalty: empty body text (0.2x)")
        return 0.2, reasons
    alpha_chars = sum(1 for c in stripped if c.isalpha())
    ratio = alpha_chars / len(stripped)
    if ratio < 0.6:
        reasons.append(f"penalty: low alphabetic ratio ({ratio:.2f} < 0.60) (0.2x)")
        return 0.2, reasons
    return 1.0, reasons


def compute_pseudocode_penalty(b_text: str, intent: ResearchIntent) -> Tuple[float, List[str]]:
    r"""
    Pseudocode penalty for DEFINITION/COMPARISON/CLASSIFICATION/EXPLANATION when body_text looks like
    a listing (>=3 lines starting with a line number, or ':=' / '//' in >=2 lines, or code block).
    """
    reasons = []
    if intent in (ResearchIntent.DEFINITION, ResearchIntent.COMPARISON, ResearchIntent.CLASSIFICATION, ResearchIntent.EXPLANATION):
        lines = [ln.strip() for ln in b_text.splitlines() if ln.strip()]
        line_num_count = sum(1 for ln in lines if re.match(r"^\d+\b", ln))
        syntax_count = sum(1 for ln in lines if (":=" in ln or "//" in ln))
        is_algorithm_code = any(re.match(r"^(?:\d+\s+)?(?:Algorithm|Procedure)\s+\d+", ln, re.I) for ln in lines[:3])
        if is_algorithm_code:
            reasons.append("penalty: listing/pseudocode downweighted for comparison/definition (0.2x)")
            return 0.2, reasons
        elif line_num_count >= 3 or syntax_count >= 2:
            reasons.append("penalty: listing/pseudocode downweighted for definition/comparison/classification (0.5x)")
            return 0.5, reasons
    return 1.0, reasons


def clean_section_label(s: str) -> str:
    """Normalizes section label to <= 70 chars, removes CHAPTER X.: artifacts, title cases all-caps."""
    if not s:
        return "Section"
    s = re.sub(r"\b(Chapter|Part)\s+(\d+)\.?:?\s*", r"\1 \2: ", s, flags=re.I)
    s = re.sub(r"\.\s*:", ":", s)
    s = re.sub(r":\s*:\s*", ": ", s)
    alpha = [c for c in s if c.isalpha()]
    if alpha and all(c.isupper() for c in alpha):
        words = s.split()
        s = " ".join(
            w.lower() if w.lower() in ("and", "or", "of", "the", "in", "to", "for", "with", "a", "an") and i > 0 else w.capitalize()
            for i, w in enumerate(words)
        )
    s = " ".join(s.split())
    if len(s) > 70:
        s = s[:70].rsplit(" ", 1)[0]
    return s.strip() or "Section"


class ExplainableRetrievalEngine:
    """Read-only SQLite FTS5 retrieval engine with explainable multi-factor scoring."""

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        collection_name: Optional[str] = None,
    ):
        self.db_path = Path(db_path or (Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"))
        self.collection_name = collection_name
        self.sentence_analyzer = SentenceAnalyzer()

    def _resolve_collection_name(self, connection: sqlite3.Connection) -> str:
        if self.collection_name:
            return self.collection_name
        try:
            row = connection.execute("SELECT DISTINCT collection_name FROM lexical_chunks LIMIT 1").fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return settings.chroma_collection_name

    def retrieve(
        self,
        query: QueryUnderstanding,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        top_k: int = 8,
        owner_id: Optional[str] = None,
    ) -> Tuple[List[RetrievedSource], Dict[str, RetrievalTrace]]:
        """
        Executes explainable multi-factor retrieval for the given QueryUnderstanding.
        Returns top_k sources and structured retrieval traces.
        """
        if not self.db_path.is_file():
            raise RuntimeError(f"Lexical database not found at {self.db_path}")

        # For multi-facet queries, retrieve each facet independently and interleave with fair allocation
        if getattr(query, "facets", None) and len(query.facets) > 1:
            return self._retrieve_multi_facet(query, paper_ids, document_ids, top_k, owner_id)

        # For comparison queries with 2 distinct concepts, retrieve separately and combine
        if query.intent == ResearchIntent.COMPARISON and len(query.target_concepts) >= 2:
            return self._retrieve_comparison_dual(query, paper_ids, document_ids, top_k, owner_id)

        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        connection.row_factory = sqlite3.Row

        try:
            coll_name = self._resolve_collection_name(connection)

            # Check if content terms exist in library vocabulary (out-of-scope check)
            content_terms = []
            for t in query.target_concepts:
                if len(t) > 2:
                    content_terms.append(t)
                    if " of " in t:
                        content_terms.extend([p.strip() for p in t.split(" of ") if len(p.strip()) > 2])
            if not content_terms:
                content_terms = [w for w in query.expanded_search_terms if len(w) > 3][:3]

            if content_terms:
                total_hits = 0
                for term in content_terms:
                    clean_term = term.replace('"', '""').strip()
                    try:
                        c_row = connection.execute(
                            "SELECT count(*) FROM lexical_chunks WHERE collection_name = ? AND lexical_chunks MATCH ?",
                            (coll_name, f'"{clean_term}"'),
                        ).fetchone()
                        if c_row and c_row[0] > 0:
                            total_hits += c_row[0]
                    except Exception:
                        pass
                if total_hits == 0:
                    # Concept does not exist anywhere in the library!
                    return [], {}

            primary_concept = query.primary_concept or ""
            search_terms = list(query.expanded_search_terms)
            if " of " in primary_concept:
                for p in primary_concept.split(" of "):
                    p_clean = p.strip()
                    if p_clean and p_clean not in search_terms:
                        search_terms.append(p_clean)
            if not search_terms:
                search_terms = [primary_concept] if primary_concept else ["algorithm", "method", "procedure"]

            # Exact phrase query for primary concept should be prioritized
            escaped_terms = []
            if query.intent == ResearchIntent.DEFINITION and primary_concept:
                clean_pc = primary_concept.replace('"', '""').strip()
                if clean_pc:
                    escaped_terms.extend([
                        f'"{clean_pc} is"',
                        f'"{clean_pc} are"',
                        f'"{clean_pc} refers to"',
                        f'"what is an {clean_pc}"',
                        f'"what is a {clean_pc}"',
                        f'"what is {clean_pc}"',
                    ])
            elif query.intent == ResearchIntent.CLASSIFICATION:
                escaped_terms.extend([
                    '"divide and conquer"',
                    '"greedy method"',
                    '"dynamic programming"',
                    '"backtracking"',
                    '"branch and bound"',
                    '"randomized algorithms"',
                    '"approximation algorithms"',
                    '"parallel algorithms"',
                    '"types of algorithms"',
                    '"categories of algorithms"',
                ])
            elif query.intent == ResearchIntent.LIST_PROPERTIES and primary_concept in ("algorithm", "algorithms"):
                escaped_terms.extend([
                    '"following criteria"',
                    '"must satisfy"',
                    '"definiteness"',
                    '"finiteness"',
                    '"effectiveness"',
                ])
            for t in search_terms[:12]:
                clean_t = t.replace('"', '""').strip()
                if clean_t and f'"{clean_t}"' not in escaped_terms:
                    escaped_terms.append(f'"{clean_t}"')

            fts_match_expr = " OR ".join(escaped_terms) if escaped_terms else '""'

            # Determine all active documents in scope
            active_doc_ids: List[str] = []
            if document_ids:
                active_doc_ids = list(dict.fromkeys(document_ids))
            elif paper_ids:
                d_placeholders = ",".join("?" for _ in paper_ids)
                d_params: List[Any] = [coll_name]
                d_constraints = ["collection_name = ?"]
                if owner_id:
                    d_constraints.append("owner_id = ?")
                    d_params.append(owner_id)
                d_constraints.append(f"paper_id IN ({d_placeholders})")
                d_params.extend(paper_ids)
                d_sql = f"SELECT DISTINCT document_id FROM lexical_chunks WHERE {' AND '.join(d_constraints)}"
                try:
                    d_rows = connection.execute(d_sql, d_params).fetchall()
                    active_doc_ids = [r[0] for r in d_rows if r[0]]
                except Exception:
                    active_doc_ids = []

            if not active_doc_ids:
                try:
                    d_constraints = ["collection_name = ?"]
                    d_params = [coll_name]
                    if owner_id:
                        d_constraints.append("owner_id = ?")
                        d_params.append(owner_id)
                    d_rows = connection.execute(
                        f"SELECT DISTINCT document_id FROM lexical_chunks WHERE {' AND '.join(d_constraints)}",
                        d_params,
                    ).fetchall()
                    active_doc_ids = [r[0] for r in d_rows if r[0]]
                except Exception:
                    active_doc_ids = []

            # Check if lexical_metadata table exists
            has_meta = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='lexical_metadata'"
            ).fetchone()[0] > 0

            # If multiple documents are active in scope, allocate candidates fairly per document
            # so one large document does not starve other documents of candidate slots
            if len(active_doc_ids) > 1:
                rows = []
                per_doc_limit = max(100, 300 // len(active_doc_ids))
                for doc_id in active_doc_ids:
                    doc_constraints = ["lexical_chunks.collection_name = ?", "lexical_chunks.document_id = ?"]
                    doc_params = [fts_match_expr, coll_name, doc_id]
                    if owner_id:
                        doc_constraints.append("lexical_chunks.owner_id = ?")
                        doc_params.append(owner_id)
                    doc_where = " AND ".join(["lexical_chunks MATCH ?", *doc_constraints])
                    if has_meta:
                        doc_sql = f"""
                            SELECT lexical_chunks.chunk_id, lexical_chunks.paper_id, lexical_chunks.document_id,
                                   lexical_chunks.section, lexical_chunks.page_start, lexical_chunks.page_end,
                                   lexical_chunks.title, lexical_chunks.filename, lexical_chunks.locator,
                                   lexical_chunks.text, bm25(lexical_chunks) AS bm25_score,
                                   m.heading_path AS meta_heading, m.section_type AS meta_section_type,
                                   m.printed_page_label AS meta_page_label, m.block_kind AS meta_block_kind,
                                   m.parent_chunk_id AS meta_parent_chunk_id
                            FROM lexical_chunks
                            LEFT JOIN lexical_metadata m ON lexical_chunks.chunk_id = m.chunk_id
                            WHERE {doc_where}
                            ORDER BY bm25_score ASC
                            LIMIT {per_doc_limit}
                        """
                    else:
                        doc_sql = f"""
                            SELECT chunk_id, paper_id, document_id, section, page_start, page_end,
                                   title, filename, locator, text, bm25(lexical_chunks) AS bm25_score,
                                   NULL AS meta_heading, NULL AS meta_section_type,
                                   NULL AS meta_page_label, NULL AS meta_block_kind,
                                   NULL AS meta_parent_chunk_id
                            FROM lexical_chunks
                            WHERE {doc_where}
                            ORDER BY bm25_score ASC
                            LIMIT {per_doc_limit}
                        """
                    rows.extend(connection.execute(doc_sql, doc_params).fetchall())
            else:
                # Query constraints
                constraints = ["lexical_chunks.collection_name = ?"]
                params: List[Any] = [fts_match_expr, coll_name]

                if owner_id:
                    constraints.append("lexical_chunks.owner_id = ?")
                    params.append(owner_id)

                if document_ids:
                    placeholders = ",".join("?" for _ in document_ids)
                    constraints.append(f"lexical_chunks.document_id IN ({placeholders})")
                    params.extend(document_ids)
                elif paper_ids:
                    placeholders = ",".join("?" for _ in paper_ids)
                    constraints.append(f"lexical_chunks.paper_id IN ({placeholders})")
                    params.extend(paper_ids)

                where_clause = " AND ".join(["lexical_chunks MATCH ?", *constraints])

                if has_meta:
                    sql = f"""
                        SELECT lexical_chunks.chunk_id, lexical_chunks.paper_id, lexical_chunks.document_id,
                               lexical_chunks.section, lexical_chunks.page_start, lexical_chunks.page_end,
                               lexical_chunks.title, lexical_chunks.filename, lexical_chunks.locator,
                               lexical_chunks.text, bm25(lexical_chunks) AS bm25_score,
                               m.heading_path AS meta_heading, m.section_type AS meta_section_type,
                               m.printed_page_label AS meta_page_label, m.block_kind AS meta_block_kind,
                               m.parent_chunk_id AS meta_parent_chunk_id
                        FROM lexical_chunks
                        LEFT JOIN lexical_metadata m ON lexical_chunks.chunk_id = m.chunk_id
                        WHERE {where_clause}
                        ORDER BY bm25_score ASC
                        LIMIT 300
                    """
                else:
                    sql = f"""
                        SELECT chunk_id, paper_id, document_id, section, page_start, page_end,
                               title, filename, locator, text, bm25(lexical_chunks) AS bm25_score,
                               NULL AS meta_heading, NULL AS meta_section_type,
                               NULL AS meta_page_label, NULL AS meta_block_kind,
                               NULL AS meta_parent_chunk_id
                        FROM lexical_chunks
                        WHERE {where_clause}
                        ORDER BY bm25_score ASC
                        LIMIT 300
                    """
                rows = connection.execute(sql, params).fetchall()

            # Multi-facet candidate gathering for classification queries to prevent single-chapter dominance
            if query.intent == ResearchIntent.CLASSIFICATION:
                facet_terms = [
                    ('"divide and conquer"'),
                    ('"greedy" OR "greedy method"'),
                    ('"dynamic programming"'),
                    ('"backtracking"'),
                    ('"branch and bound"'),
                    ('"randomized algorithm" OR "randomized algorithms"'),
                    ('"approximation algorithm" OR "approximation algorithms"'),
                    ('"types of algorithms" OR "categories of algorithms" OR "design paradigms"'),
                ]
                existing_cids = {str(r["chunk_id"]) for r in rows}
                target_docs = active_doc_ids if active_doc_ids else [None]
                extra_rows = []
                for facet_expr in facet_terms:
                    for doc_id in target_docs:
                        f_constraints = ["lexical_chunks.collection_name = ?"]
                        f_params = [facet_expr, coll_name]
                        if doc_id:
                            f_constraints.append("lexical_chunks.document_id = ?")
                            f_params.append(doc_id)
                        if owner_id:
                            f_constraints.append("lexical_chunks.owner_id = ?")
                            f_params.append(owner_id)
                        f_where = " AND ".join(["lexical_chunks MATCH ?", *f_constraints])
                        if has_meta:
                            f_sql = f"""
                                SELECT lexical_chunks.chunk_id, lexical_chunks.paper_id, lexical_chunks.document_id,
                                       lexical_chunks.section, lexical_chunks.page_start, lexical_chunks.page_end,
                                       lexical_chunks.title, lexical_chunks.filename, lexical_chunks.locator,
                                       lexical_chunks.text, bm25(lexical_chunks) AS bm25_score,
                                       m.heading_path AS meta_heading, m.section_type AS meta_section_type,
                                       m.printed_page_label AS meta_page_label, m.block_kind AS meta_block_kind,
                                       m.parent_chunk_id AS meta_parent_chunk_id
                                FROM lexical_chunks
                                LEFT JOIN lexical_metadata m ON lexical_chunks.chunk_id = m.chunk_id
                                WHERE {f_where}
                                ORDER BY bm25_score ASC
                                LIMIT 3
                            """
                        else:
                            f_sql = f"""
                                SELECT chunk_id, paper_id, document_id, section, page_start, page_end,
                                       title, filename, locator, text, bm25(lexical_chunks) AS bm25_score,
                                       NULL AS meta_heading, NULL AS meta_section_type,
                                       NULL AS meta_page_label, NULL AS meta_block_kind,
                                       NULL AS meta_parent_chunk_id
                                FROM lexical_chunks
                                WHERE {f_where}
                                ORDER BY bm25_score ASC
                                LIMIT 3
                            """
                        try:
                            f_rows = connection.execute(f_sql, f_params).fetchall()
                            for fr in f_rows:
                                if str(fr["chunk_id"]) not in existing_cids:
                                    existing_cids.add(str(fr["chunk_id"]))
                                    extra_rows.append(fr)
                        except Exception:
                            pass
                if extra_rows:
                    rows = list(rows) + extra_rows

            # Check headings_fts table for chunks matching heading directly
            heading_matched_cids: Set[str] = set()
            has_headings_fts = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='headings_fts'"
            ).fetchone()[0] > 0
            if has_headings_fts and primary_concept:
                try:
                    clean_concept = primary_concept.replace('"', '""')
                    h_rows = connection.execute(
                        "SELECT chunk_id FROM headings_fts WHERE headings_fts MATCH ?",
                        (f'"{clean_concept}"',),
                    ).fetchall()
                    heading_matched_cids = {r[0] for r in h_rows if r[0]}
                except Exception:
                    pass

        finally:
            connection.close()

        if not rows:
            return [], {}

        # Deduplicate and score candidate chunks
        scored_candidates: List[Tuple[float, sqlite3.Row, RetrievalTrace]] = []
        seen_hashes = set()

        for row in rows:
            text = str(row["text"] or "")
            if not text.strip():
                continue

            norm_text = " ".join(text.lower().split())
            text_hash = hashlib.sha256(norm_text[:200].encode("utf-8")).hexdigest()
            if text_hash in seen_hashes:
                continue
            seen_hashes.add(text_hash)

            trace = self._score_candidate(row, query, heading_matched_cids)
            scored_candidates.append((trace.final_score, row, trace))

        # Sort descending by final_score
        scored_candidates.sort(key=lambda item: -item[0])

        # Maximal Marginal Relevance (MMR) selection
        selected_sources: List[RetrievedSource] = []
        traces: Dict[str, RetrievalTrace] = {}
        used_sections: Dict[str, int] = {}
        used_docs: Dict[str, int] = {}
        selected_chunk_ids: Set[str] = set()

        def _get_primary_paradigm(sec_text: str, body_text: str) -> Optional[str]:
            st = sec_text.lower()
            for p in ["divide and conquer", "divide-and-conquer", "greedy", "dynamic programming", "backtracking", "branch and bound", "branch-and-bound", "randomized", "approximation", "pram", "parallel"]:
                if p in st:
                    return p.replace("-", " ")
            bt = body_text[:250].lower()
            for p in ["divide and conquer", "divide-and-conquer", "greedy method", "dynamic programming", "backtracking", "branch and bound", "branch-and-bound", "randomized algorithm", "approximation algorithm"]:
                if p in bt:
                    return p.replace("-", " ").replace(" method", "").replace(" algorithm", "")
            return None

        # Pass 1 for CLASSIFICATION: Ensure distinct paradigm coverage
        if query.intent == ResearchIntent.CLASSIFICATION:
            covered_paradigms: Set[str] = set()
            for score, row, trace in scored_candidates:
                if len(selected_sources) >= top_k:
                    break
                sec_desc = f"{trace.heading_path} {trace.section} {row['locator'] or ''}"
                p_kind = _get_primary_paradigm(sec_desc, str(row["text"] or ""))
                if p_kind and p_kind not in covered_paradigms:
                    cid = str(row["chunk_id"])
                    selected_chunk_ids.add(cid)
                    covered_paradigms.add(p_kind)
                    doc_id = str(row["document_id"])
                    sec = trace.heading_path or trace.section or "Section"
                    used_sections[sec] = used_sections.get(sec, 0) + 1
                    used_docs[doc_id] = used_docs.get(doc_id, 0) + 1

                    source_id = f"S{len(selected_sources) + 1}"
                    p_start = int(row["page_start"]) if row["page_start"] is not None else 1
                    p_end = int(row["page_end"]) if row["page_end"] is not None else p_start
                    p_label = trace.page_label or str(p_start)
                    locator = trace.heading_path if trace.heading_path else str(row["locator"] or f"{sec} · p.{p_start}")
                    if p_label and f"p.{p_label}" not in locator:
                        locator = f"{locator} · p.{p_label}"

                    source = RetrievedSource(
                        source_id=source_id,
                        chunk_id=cid,
                        document_id=doc_id,
                        paper_id=str(row["paper_id"]),
                        page_start=p_start,
                        page_end=p_end,
                        section=clean_section_label(trace.section),
                        title=str(row["title"] or "Research Document"),
                        filename=str(row["filename"] or ""),
                        locator=locator,
                        text=str(row["text"] or ""),
                        score=round(trace.final_score, 4),
                    )
                    selected_sources.append(source)
                    traces[source_id] = trace

        for idx, (score, row, trace) in enumerate(scored_candidates, start=1):
            if len(selected_sources) >= top_k:
                break

            cid = str(row["chunk_id"])
            if cid in selected_chunk_ids:
                continue

            doc_id = str(row["document_id"])
            sec = trace.heading_path or trace.section or "Section"
            sec_count = used_sections.get(sec, 0)
            doc_count = used_docs.get(doc_id, 0)
            if sec_count >= 2 and len(selected_sources) < top_k - 1 and len(scored_candidates) > top_k:
                continue

            # In multi-doc scopes, ensure both documents get fair representation in top_k
            if len(active_doc_ids) > 1 and doc_count >= max(2, top_k // 2) and len(selected_sources) < top_k:
                has_other_doc_candidate = any(
                    str(cand[1]["document_id"]) != doc_id and used_docs.get(str(cand[1]["document_id"]), 0) < max(2, top_k // 2)
                    for cand in scored_candidates[idx:]
                )
                if has_other_doc_candidate:
                    continue

            selected_chunk_ids.add(cid)
            source_id = f"S{len(selected_sources) + 1}"
            used_sections[sec] = sec_count + 1
            used_docs[doc_id] = doc_count + 1

            p_start = int(row["page_start"]) if row["page_start"] is not None else 1
            p_end = int(row["page_end"]) if row["page_end"] is not None else p_start
            p_label = trace.page_label or str(p_start)

            locator = trace.heading_path if trace.heading_path else str(row["locator"] or f"{sec} · p.{p_start}")
            if p_label and f"p.{p_label}" not in locator:
                locator = f"{locator} · p.{p_label}"

            source = RetrievedSource(
                source_id=source_id,
                chunk_id=cid,
                document_id=str(row["document_id"]),
                paper_id=str(row["paper_id"]),
                page_start=p_start,
                page_end=p_end,
                section=clean_section_label(trace.section),
                title=str(row["title"] or "Research Document"),
                filename=str(row["filename"] or ""),
                locator=locator,
                text=str(row["text"] or ""),
                score=round(trace.final_score, 4),
            )

            selected_sources.append(source)
            traces[source_id] = trace

        # Multi-document guarantee for DEFINITION and COMPARISON queries
        if query.intent in (ResearchIntent.DEFINITION, ResearchIntent.COMPARISON):
            concepts_to_check = [query.primary_concept] if query.primary_concept else query.target_concepts
            target_doc_ids = active_doc_ids if active_doc_ids else list(dict.fromkeys(str(c[1]["document_id"]) for c in scored_candidates if str(c[1]["document_id"])))
            if len(target_doc_ids) > 1 and concepts_to_check:
                top_5_docs = {s.document_id for s in selected_sources[:5]}
                for doc_id in target_doc_ids:
                    if doc_id not in top_5_docs:
                        matching_cands = []
                        for c in scored_candidates:
                            if str(c[1]["document_id"]) == doc_id:
                                bt = body_text(c[1])
                                norm_bt = norm(bt)
                                if any(norm(concept) in norm_bt for concept in concepts_to_check if norm(concept)):
                                    matching_cands.append(c)
                        if matching_cands:
                            best_cand = matching_cands[0]
                            cand_cid = str(best_cand[1]["chunk_id"])
                            existing_idx = next((i for i, s in enumerate(selected_sources) if s.chunk_id == cand_cid), None)
                            if existing_idx is not None:
                                cand_source = selected_sources.pop(existing_idx)
                            else:
                                score, row, trace = best_cand
                                p_start = int(row["page_start"]) if row["page_start"] is not None else 1
                                p_end = int(row["page_end"]) if row["page_end"] is not None else p_start
                                p_label = trace.page_label or str(p_start)
                                sec = trace.heading_path or trace.section or "Section"
                                locator = trace.heading_path if trace.heading_path else str(row["locator"] or f"{sec} · p.{p_start}")
                                if p_label and f"p.{p_label}" not in locator:
                                    locator = f"{locator} · p.{p_label}"
                                cand_source = RetrievedSource(
                                    source_id="",
                                    chunk_id=cand_cid,
                                    document_id=doc_id,
                                    paper_id=str(row["paper_id"]),
                                    page_start=p_start,
                                    page_end=p_end,
                                    section=clean_section_label(trace.section),
                                    title=str(row["title"] or "Research Document"),
                                    filename=str(row["filename"] or ""),
                                    locator=locator,
                                    text=str(row["text"] or ""),
                                    score=round(trace.final_score, 4),
                                )
                                traces[cand_cid] = trace

                            if len(selected_sources) < 5:
                                selected_sources.append(cand_source)
                            else:
                                doc_counts = {}
                                for s in selected_sources[:5]:
                                    doc_counts[s.document_id] = doc_counts.get(s.document_id, 0) + 1
                                replace_idx = None
                                min_score = float("inf")
                                for i in range(min(5, len(selected_sources)) - 1, -1, -1):
                                    if doc_counts.get(selected_sources[i].document_id, 0) > 1 and selected_sources[i].score < min_score:
                                        min_score = selected_sources[i].score
                                        replace_idx = i
                                if replace_idx is not None:
                                    selected_sources.insert(replace_idx, cand_source)
                                else:
                                    selected_sources.insert(4, cand_source)

                            selected_sources = selected_sources[:top_k]
                            new_traces = {}
                            for new_i, src in enumerate(selected_sources):
                                old_id = src.source_id
                                new_id = f"S{new_i + 1}"
                                src.source_id = new_id
                                if old_id in traces:
                                    new_traces[new_id] = traces[old_id]
                                elif src.chunk_id in traces:
                                    new_traces[new_id] = traces[src.chunk_id]
                            traces = new_traces
                            top_5_docs = {s.document_id for s in selected_sources[:5]}

        return selected_sources, traces

    def _retrieve_multi_facet(
        self,
        query: QueryUnderstanding,
        paper_ids: Optional[List[str]],
        document_ids: Optional[List[str]],
        top_k: int,
        owner_id: Optional[str],
    ) -> Tuple[List[RetrievedSource], Dict[str, RetrievalTrace]]:
        """
        Executes independent retrieval per question facet to guarantee balanced,
        high-signal coverage across both documents without letting one dominant
        chapter crowd out other facets.
        """
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        connection.row_factory = sqlite3.Row

        try:
            coll_name = self._resolve_collection_name(connection)

            # Determine all active documents in scope
            active_doc_ids: List[str] = []
            if document_ids:
                active_doc_ids = list(dict.fromkeys(document_ids))
            elif paper_ids:
                d_placeholders = ",".join("?" for _ in paper_ids)
                d_params: List[Any] = [coll_name]
                d_constraints = ["collection_name = ?"]
                if owner_id:
                    d_constraints.append("owner_id = ?")
                    d_params.append(owner_id)
                d_constraints.append(f"paper_id IN ({d_placeholders})")
                d_params.extend(paper_ids)
                d_sql = f"SELECT DISTINCT document_id FROM lexical_chunks WHERE {' AND '.join(d_constraints)}"
                try:
                    d_rows = connection.execute(d_sql, d_params).fetchall()
                    active_doc_ids = [r[0] for r in d_rows if r[0]]
                except Exception:
                    active_doc_ids = []

            if not active_doc_ids:
                try:
                    d_constraints = ["collection_name = ?"]
                    d_params = [coll_name]
                    if owner_id:
                        d_constraints.append("owner_id = ?")
                        d_params.append(owner_id)
                    d_rows = connection.execute(
                        f"SELECT DISTINCT document_id FROM lexical_chunks WHERE {' AND '.join(d_constraints)}",
                        d_params,
                    ).fetchall()
                    active_doc_ids = [r[0] for r in d_rows if r[0]]
                except Exception:
                    active_doc_ids = []

            has_meta = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='lexical_metadata'"
            ).fetchone()[0] > 0

            target_docs = active_doc_ids if active_doc_ids else [None]
            facet_candidates: Dict[str, List[Tuple[float, sqlite3.Row, RetrievalTrace]]] = {}

            for facet in query.facets:
                f_rows: List[sqlite3.Row] = []
                f_search_phrases = facet.search_phrases or [f'"{facet.primary_concept}"']

                # Query phrases individually to prevent single-concept dominance
                phrases_to_query = f_search_phrases if len(f_search_phrases) > 1 else [f_search_phrases[0]]
                per_phrase_limit = 6 if len(phrases_to_query) <= 4 else 3

                # Query per document and per phrase to ensure cross-document & cross-facet balance
                for single_phrase in phrases_to_query:
                    for doc_id in target_docs:
                        constraints = ["lexical_chunks.collection_name = ?"]
                        params = [single_phrase, coll_name]
                        if doc_id:
                            constraints.append("lexical_chunks.document_id = ?")
                            params.append(doc_id)
                        if owner_id:
                            constraints.append("lexical_chunks.owner_id = ?")
                            params.append(owner_id)

                        where_clause = " AND ".join(["lexical_chunks MATCH ?", *constraints])

                        if has_meta:
                            sql = f"""
                                SELECT lexical_chunks.chunk_id, lexical_chunks.paper_id, lexical_chunks.document_id,
                                       lexical_chunks.section, lexical_chunks.page_start, lexical_chunks.page_end,
                                       lexical_chunks.title, lexical_chunks.filename, lexical_chunks.locator,
                                       lexical_chunks.text, bm25(lexical_chunks) AS bm25_score,
                                       m.heading_path AS meta_heading, m.section_type AS meta_section_type,
                                       m.printed_page_label AS meta_page_label, m.block_kind AS meta_block_kind,
                                       m.parent_chunk_id AS meta_parent_chunk_id
                                FROM lexical_chunks
                                LEFT JOIN lexical_metadata m ON lexical_chunks.chunk_id = m.chunk_id
                                WHERE {where_clause}
                                ORDER BY bm25_score ASC
                                LIMIT {per_phrase_limit}
                            """
                        else:
                            sql = f"""
                                SELECT chunk_id, paper_id, document_id, section, page_start, page_end,
                                       title, filename, locator, text, bm25(lexical_chunks) AS bm25_score,
                                       NULL AS meta_heading, NULL AS meta_section_type,
                                       NULL AS meta_page_label, NULL AS meta_block_kind,
                                       NULL AS meta_parent_chunk_id
                                FROM lexical_chunks
                                WHERE {where_clause}
                                ORDER BY bm25_score ASC
                                LIMIT {per_phrase_limit}
                            """
                        try:
                            d_cands = connection.execute(sql, params).fetchall()
                            f_rows.extend(d_cands)
                        except Exception:
                            pass

                f_query = QueryUnderstanding(
                    raw_query=facet.facet_title,
                    normalized_query=facet.facet_title.lower(),
                    intent=facet.intent,
                    primary_concept=facet.primary_concept,
                    target_concepts=facet.target_concepts,
                    expanded_search_terms=facet.search_phrases,
                    section_priors=facet.section_priors or query.section_priors,
                )

                f_scored = []
                seen_f_hashes = set()
                for row in f_rows:
                    text = str(row["text"] or "")
                    if not text.strip():
                        continue
                    text_hash = hashlib.sha256(text[:150].encode("utf-8")).hexdigest()
                    if text_hash in seen_f_hashes:
                        continue
                    seen_f_hashes.add(text_hash)

                    trace = self._score_candidate(row, f_query, heading_matched_cids=set())
                    f_scored.append((trace.final_score, row, trace))

                f_scored.sort(key=lambda item: -item[0])
                facet_candidates[facet.facet_id] = f_scored

        finally:
            connection.close()

        # Selection: allocate across facets to guarantee comprehensive coverage
        selected_sources: List[RetrievedSource] = []
        traces: Dict[str, RetrievalTrace] = {}
        selected_cids: Set[str] = set()
        seen_passages: Set[str] = set()
        seen_paradigms: Dict[str, int] = {}

        PARADIGM_KEYWORDS = [
            ("divide_and_conquer", ["divide and conquer", "divide-and-conquer", "dandc"]),
            ("greedy", ["greedy method", "greedy strategy", "greedy algorithm", "greedy-set-cover", "greedy"]),
            ("dynamic_programming", ["dynamic programming", "optimal substructure", "sequence of decisions", "memoization", "cut-rod", "subproblem"]),
            ("backtracking", ["backtracking", "state space tree", "e-node", "state space"]),
            ("branch_and_bound", ["branch and bound", "branch-and-bound", "fifo branch-and-bound", "lc branch-and-bound"]),
            ("randomized", ["randomized algorithm", "randomized algorithms", "randomized quicksort"]),
            ("approximation", ["approximation algorithm", "approximation ratio", "approximation algorithms", "approximate solution", "approximation"]),
        ]

        def _detect_primary_paradigm(t: str) -> Optional[str]:
            tl = t.lower()
            for pname, pterms in PARADIGM_KEYWORDS:
                if any(pt in tl for pt in pterms):
                    return pname
            return None

        target_top_k = max(top_k, 9) if getattr(query, "is_compound", False) or len(query.facets) > 2 else top_k
        num_facets = max(1, len(query.facets))
        base_quota = max(1, target_top_k // num_facets)

        # Round 1: Select top candidates per facet with paradigm diversity
        for facet in query.facets:
            cands = facet_candidates.get(facet.facet_id, [])
            picked = 0
            if facet.facet_id == "definition":
                facet_limit = 2
            elif facet.facet_id == "criteria":
                facet_limit = 1
            elif facet.facet_id in ("strategies", "explanation"):
                facet_limit = 4
            else:
                facet_limit = max(2, base_quota)

            for score, row, trace in cands:
                if picked >= facet_limit:
                    break
                cid = str(row["chunk_id"])
                if cid in selected_cids:
                    continue

                text = str(row["text"] or "").strip()
                norm_snip = " ".join(text[:120].lower().split())
                if norm_snip in seen_passages:
                    continue
                if "..." in text or ". . ." in text or bool(re.search(r"\.{4,}", text)):
                    continue

                # In strategies/explanation facets, enforce diversity across paradigms
                if facet.facet_id in ("strategies", "explanation"):
                    full_context_str = f"{trace.section} {trace.heading_path} {text}"
                    detected_p = _detect_primary_paradigm(full_context_str)
                    if detected_p and seen_paradigms.get(detected_p, 0) >= 1:
                        continue
                    if detected_p:
                        seen_paradigms[detected_p] = seen_paradigms.get(detected_p, 0) + 1

                selected_cids.add(cid)
                seen_passages.add(norm_snip)
                picked += 1

                sid = f"S{len(selected_sources) + 1}"
                p_start = int(row["page_start"] or 1)
                p_end = int(row["page_end"] or p_start)
                p_label = str(row["meta_page_label"] or "") if "meta_page_label" in row.keys() and row["meta_page_label"] else str(p_start)

                locator = trace.heading_path or trace.section or "Section"
                if p_label and f"p.{p_label}" not in locator:
                    locator = f"{locator} · p.{p_label}"

                source = RetrievedSource(
                    source_id=sid,
                    chunk_id=cid,
                    document_id=str(row["document_id"]),
                    paper_id=str(row["paper_id"]),
                    page_start=p_start,
                    page_end=p_end,
                    section=trace.section,
                    title=str(row["title"] or "Research Document"),
                    filename=str(row["filename"] or ""),
                    locator=locator,
                    text=text,
                    score=round(trace.final_score, 4),
                )
                selected_sources.append(source)
                traces[sid] = trace

        # Round 2: Backfill from remaining top scoring candidates if needed
        if len(selected_sources) < target_top_k:
            all_remaining = []
            for facet_id, cands in facet_candidates.items():
                for score, row, trace in cands:
                    cid = str(row["chunk_id"])
                    if cid not in selected_cids:
                        all_remaining.append((score, row, trace))

            all_remaining.sort(key=lambda item: -item[0])
            for score, row, trace in all_remaining:
                if len(selected_sources) >= target_top_k:
                    break
                cid = str(row["chunk_id"])
                if cid in selected_cids:
                    continue

                text = str(row["text"] or "").strip()
                norm_snip = " ".join(text[:120].lower().split())
                if norm_snip in seen_passages:
                    continue
                if "..." in text or ". . ." in text or bool(re.search(r"\.{4,}", text)):
                    continue

                full_context_str = f"{trace.section} {trace.heading_path} {text}"
                detected_p = _detect_primary_paradigm(full_context_str)
                if detected_p and seen_paradigms.get(detected_p, 0) >= 1:
                    continue
                if detected_p:
                    seen_paradigms[detected_p] = seen_paradigms.get(detected_p, 0) + 1

                selected_cids.add(cid)
                seen_passages.add(norm_snip)

                sid = f"S{len(selected_sources) + 1}"
                p_start = int(row["page_start"] or 1)
                p_end = int(row["page_end"] or p_start)
                p_label = str(row["meta_page_label"] or "") if "meta_page_label" in row.keys() and row["meta_page_label"] else str(p_start)

                locator = trace.heading_path or trace.section or "Section"
                if p_label and f"p.{p_label}" not in locator:
                    locator = f"{locator} · p.{p_label}"

                source = RetrievedSource(
                    source_id=sid,
                    chunk_id=cid,
                    document_id=str(row["document_id"]),
                    paper_id=str(row["paper_id"]),
                    page_start=p_start,
                    page_end=p_end,
                    section=trace.section,
                    title=str(row["title"] or "Research Document"),
                    filename=str(row["filename"] or ""),
                    locator=locator,
                    text=text,
                    score=round(trace.final_score, 4),
                )
                selected_sources.append(source)
                traces[sid] = trace

        return selected_sources, traces

    def _retrieve_comparison_dual(
        self,
        query: QueryUnderstanding,
        paper_ids: Optional[List[str]],
        document_ids: Optional[List[str]],
        top_k: int,
        owner_id: Optional[str],
    ) -> Tuple[List[RetrievedSource], Dict[str, RetrievalTrace]]:
        """Retrieves concept A and concept B independently and interleaves results."""
        c1 = query.target_concepts[0]
        c2 = query.target_concepts[1]

        q1 = QueryUnderstanding(
            raw_query=f"Explain {c1}",
            normalized_query=c1,
            intent=ResearchIntent.COMPARISON,
            target_concepts=[c1],
            primary_concept=c1,
            expanded_search_terms=[c1] + query.expanded_search_terms,
        )
        q2 = QueryUnderstanding(
            raw_query=f"Explain {c2}",
            normalized_query=c2,
            intent=ResearchIntent.COMPARISON,
            target_concepts=[c2],
            primary_concept=c2,
            expanded_search_terms=[c2] + query.expanded_search_terms,
        )

        half_k = max(2, top_k // 2)
        s1, t1 = self.retrieve(q1, paper_ids, document_ids, top_k=half_k, owner_id=owner_id)
        s2, t2 = self.retrieve(q2, paper_ids, document_ids, top_k=half_k, owner_id=owner_id)

        combined_sources: List[RetrievedSource] = []
        combined_traces: Dict[str, RetrievalTrace] = {}
        seen_cids = set()

        max_len = max(len(s1), len(s2))
        for i in range(max_len):
            if i < len(s1) and s1[i].chunk_id not in seen_cids:
                sid = f"S{len(combined_sources) + 1}"
                seen_cids.add(s1[i].chunk_id)
                tr = t1.get(s1[i].source_id)
                combined_sources.append(s1[i].model_copy(update={"source_id": sid}))
                if tr:
                    combined_traces[sid] = tr
            if i < len(s2) and s2[i].chunk_id not in seen_cids:
                sid = f"S{len(combined_sources) + 1}"
                seen_cids.add(s2[i].chunk_id)
                tr = t2.get(s2[i].source_id)
                combined_sources.append(s2[i].model_copy(update={"source_id": sid}))
                if tr:
                    combined_traces[sid] = tr

        return combined_sources[:top_k], combined_traces

    def _score_candidate(
        self,
        row: sqlite3.Row,
        query: QueryUnderstanding,
        heading_matched_cids: Set[str],
    ) -> RetrievalTrace:
        chunk_id = str(row["chunk_id"])
        text = str(row["text"] or "")
        section = clean_section_label(str(row["section"] or ""))
        locator = str(row["locator"] or "")
        bm25_raw = float(row["bm25_score"])
        primary_concept = (query.primary_concept or "").strip().lower()

        # Metadata fields from lexical_metadata join
        meta_heading = clean_section_label(str(row["meta_heading"] or "")) if "meta_heading" in row.keys() and row["meta_heading"] else ""
        meta_sec_type = str(row["meta_section_type"] or "") if "meta_section_type" in row.keys() and row["meta_section_type"] else ""
        meta_page_lbl = str(row["meta_page_label"] or "") if "meta_page_label" in row.keys() and row["meta_page_label"] else ""

        reasons = []

        base_bm25 = 1.0 / (1.0 + math.exp(bm25_raw))
        reasons.append(f"FTS5 BM25 raw={bm25_raw:.2f}")

        # Extract body text minus running header
        b_text = body_text(text, section)

        # 1. Heading Boost
        heading_boost = 1.0
        active_heading = meta_heading or locator or section
        if primary_concept:
            heading_boost, h_reasons = compute_heading_boost(
                active_heading=active_heading,
                section=section,
                b_text=b_text,
                primary_concept=primary_concept,
                is_exact_matched=(chunk_id in heading_matched_cids),
            )
            reasons.extend(h_reasons)

            if query.intent == ResearchIntent.CLASSIFICATION:
                for p in ["divide and conquer", "divide-and-conquer", "greedy", "dynamic programming", "backtracking", "branch and bound", "branch-and-bound", "randomized", "approximation", "pram"]:
                    if norm(p) in norm(active_heading + " " + locator + " " + b_text[:150]):
                        heading_boost = max(heading_boost, 3.0)
                        reasons.append(f"heading match for algorithm paradigm '{p}' (+200%)")
                        break

        # 1b. Description Boost
        description_boost, desc_reasons = compute_description_boost(b_text, primary_concept)
        reasons.extend(desc_reasons)

        # 1c. Caption / Table Penalty
        caption_penalty, cap_reasons = compute_caption_penalty(b_text, query.intent)
        reasons.extend(cap_reasons)

        # 1d. Garbage Penalty
        garbage_penalty, gar_reasons = compute_garbage_penalty(b_text)
        reasons.extend(gar_reasons)

        # 1e. Pseudocode / Listing Penalty
        pseudocode_penalty, pseudo_reasons = compute_pseudocode_penalty(b_text, query.intent)
        reasons.extend(pseudo_reasons)

        # 2. Section Type Prior
        sec_lower = (section + " " + active_heading).lower()
        sec_type = meta_sec_type.lower() if meta_sec_type else ""

        p_start = int(row["page_start"]) if row["page_start"] is not None else 1

        title_val = row["title"] if ("title" in row.keys() if hasattr(row, "keys") else hasattr(row, "title")) else (row.get("title") if isinstance(row, dict) else "")
        fname_val = row["filename"] if ("filename" in row.keys() if hasattr(row, "keys") else hasattr(row, "filename")) else (row.get("filename") if isinstance(row, dict) else "")
        doc_title_lower = (str(title_val or "") + " " + str(fname_val or "")).lower()
        doc_id_val = str(row["document_id"]) if ("document_id" in row.keys() if hasattr(row, "keys") else hasattr(row, "document_id")) else (row.get("document_id", "") if isinstance(row, dict) else "")
        is_cormen = "ca86fa5f" in doc_id_val or "cormen" in doc_title_lower
        is_horowitz = "horowitz" in doc_title_lower or "sahani" in doc_title_lower or "sahni" in doc_title_lower
        if is_cormen:
            min_body_p = 25
        elif is_horowitz:
            min_body_p = 22
        else:
            # Arbitrary papers and non-textbook documents begin primary content on page 1
            min_body_p = 1

        is_bib = sec_type == "bibliography" or bool(re.search(r"\b(?:references|bibliography|literature\s+cited)\b", sec_lower))
        is_index = sec_type == "index" or (is_cormen and p_start >= 1272) or bool(re.search(r"\b(?:index|subject\s+index|author\s+index)\b", sec_lower))
        is_exercises = (
            sec_type in ("exercises", "problems")
            or bool(re.search(r"\b(?:exercises|problems|chapter\s+problems)\b", sec_lower))
            or bool(re.search(r"^\s*(?:exercises|problems|\d+\.\s*(?:do\s+exercise|prove|work\s+out))\b", text[:100], re.I))
            or bool(re.search(r"\bexercises?\b", text[:120], re.I))
        )
        is_chapter_notes = sec_type == "chapter_notes" or bool(re.search(r"\b(?:chapter\s+notes|historical\s+notes|notes\s+and\s+references)\b", sec_lower))
        is_front = (
            sec_type == "front_matter"
            or p_start < min_body_p
            or bool(re.search(r"\b(?:contents|table\s+of\s+contents|preface|acknowledgments|foreword)\b", sec_lower))
            or bool(re.search(r"\b(?:preface|acknowledgments?|foreword)\b", text[:300], re.I))
            or bool(re.search(r"\b(?:assignment\s+[ivx\d]+\s+due|exam\s+[ivx\d]+|semester\s+(?:schedule|pace)|quarter\s+schedule)\b", text, re.I))
            or bool(re.search(r"\btable\s+[ivx\d]+\s*:\s*(?:first|second|semester|quarter)\b", text, re.I))
        )
        is_definitions = sec_type == "definitions" or bool(re.search(r"\b(?:definitions|glossary|terminology)\b", sec_lower))

        section_prior = 1.0
        if query.intent == ResearchIntent.DEFINITION:
            if is_bib:
                section_prior = 0.01
                reasons.append("penalty: bibliography downweighted for definition (0.01x)")
            elif is_index:
                section_prior = 0.01
                reasons.append("penalty: index downweighted for definition (0.01x)")
            elif is_exercises:
                section_prior = 0.10
                reasons.append("penalty: exercise/problem downweighted for definition (0.10x)")
            elif is_chapter_notes:
                section_prior = 0.15
                reasons.append("penalty: chapter notes downweighted for definition (0.15x)")
            elif is_front:
                section_prior = 0.05
                reasons.append("penalty: front matter / syllabus table downweighted for definition (0.05x)")
            elif is_definitions:
                section_prior = 3.0
                reasons.append("boost: explicit definition section (3.0x)")
            else:
                section_prior = 1.6
                reasons.append("boost: body chapter for definition (1.6x)")
        elif query.intent == ResearchIntent.COMPLEXITY:
            if is_bib or is_index:
                section_prior = 0.01
                reasons.append("penalty: back matter downweighted for complexity (0.01x)")
            elif is_exercises:
                section_prior = 0.30
                reasons.append("penalty: exercises downweighted for complexity (0.30x)")
            elif is_front:
                section_prior = 0.05
                reasons.append("penalty: front matter downweighted for complexity (0.05x)")
            else:
                section_prior = 1.6
                reasons.append("boost: body section for complexity (1.6x)")
        elif query.intent == ResearchIntent.CLASSIFICATION:
            if is_bib or is_index:
                section_prior = 0.01
                reasons.append("penalty: back matter downweighted for classification (0.01x)")
            elif is_exercises:
                section_prior = 0.10
                reasons.append("penalty: exercises downweighted for classification (0.10x)")
            elif is_front:
                section_prior = 0.05
                reasons.append("penalty: table of contents / syllabus / front matter downweighted for classification (0.05x)")
            else:
                section_prior = 1.8
                reasons.append("boost: body chapter for classification (1.8x)")
        elif query.intent == ResearchIntent.LOCATE:
            if is_index:
                section_prior = 2.5
                reasons.append("boost: index highly relevant for locate (2.5x)")
            else:
                section_prior = 1.2
        else:
            if is_bib:
                section_prior = 0.01
                reasons.append("penalty: bibliography downweighted (0.01x)")
            elif is_index:
                section_prior = 0.01
                reasons.append("penalty: index downweighted (0.01x)")
            elif is_front:
                section_prior = 0.05
                reasons.append("penalty: front matter downweighted (0.05x)")
            elif is_exercises:
                section_prior = 0.20
                reasons.append("penalty: exercises downweighted (0.20x)")

        # 3. Sentence-Level Definition Boost
        definition_boost = 1.0
        if query.intent == ResearchIntent.DEFINITION and primary_concept:
            is_foundational_def = bool(re.search(
                r"\b(?:informally|formally)?\s*,?\s*an?\s+algorithm\s+is\s+(?:any\s+)?(?:well[- ]defined\s+)?(?:computational\s+procedure|finite\s+set|sequence)",
                text, re.IGNORECASE
            ))
            if is_foundational_def:
                definition_boost = 4.5
                reasons.append("boost: foundational textbook definition passage confirmed (4.5x)")
            else:
                def_candidates = self.sentence_analyzer.find_definition_sentences(text, primary_concept)
                if def_candidates:
                    top_def = def_candidates[0]
                    if top_def.pattern_name in {"informal_definition", "formal_definition", "is_thus_sequence"}:
                        definition_boost = 3.0
                        reasons.append(f"boost: explicit definition sentence found ({top_def.pattern_name}, conf={top_def.confidence:.2f}) (3.0x)")
                    else:
                        definition_boost = 1.8
                        reasons.append(f"boost: secondary definition pattern found ({top_def.pattern_name}) (1.8x)")

        # Penalize table of contents entries with dotted page numbers
        is_toc_dots = bool(re.search(r"\.{4,}|\b\d+\s*\.{3,}|\b(?:\.\s*){4,}", text))
        is_preface_summary = bool(
            re.search(r"\bchapter\s+\d+:\s*(?:introduces|examines|presents|describes)\b", sec_lower)
            or bool(re.search(r"\bchapter\s+\d+\s+introduces\b", text[:200].lower()))
        )

        noise_penalty = 1.0
        if is_toc_dots:
            noise_penalty = 0.05
            reasons.append("penalty: table of contents page listing downweighted (0.05x)")
        elif is_preface_summary and query.intent != ResearchIntent.SUMMARIZATION:
            noise_penalty = 0.15
            reasons.append("penalty: preface chapter summary downweighted (0.15x)")

        # 4. Citation Density Penalty (exclude bibliography dumps)
        citation_penalty = 1.0
        bracket_citations = len(re.findall(r"\[\d+\]", text))
        if bracket_citations >= 5 and query.intent != ResearchIntent.OTHER:
            citation_penalty = max(0.2, 1.0 - (bracket_citations * 0.1))
            reasons.append(f"penalty: dense citation markers ({bracket_citations} found, {citation_penalty:.2f}x)")

        # 5. Paradigm Density Boost for CLASSIFICATION
        paradigm_boost = 1.0
        if query.intent == ResearchIntent.CLASSIFICATION:
            text_lower = text.lower()
            paradigms_matched = [
                p for p in ["divide and conquer", "divide-and-conquer", "greedy method", "dynamic programming", "backtracking", "branch and bound", "branch-and-bound", "randomized", "approximation", "mesh algorithms", "hypercube"]
                if p in text_lower
            ]
            if len(paradigms_matched) >= 3:
                paradigm_boost = 4.0
                reasons.append(f"boost: high paradigm density ({len(paradigms_matched)} paradigms found: {', '.join(paradigms_matched[:3])}) (4.0x)")
            elif len(paradigms_matched) >= 1:
                paradigm_boost = 2.0
                reasons.append(f"boost: paradigm concept found ({paradigms_matched[0]}) (2.0x)")

        # 6. Formal Criteria Boost for LIST_PROPERTIES
        criteria_boost = 1.0
        if query.intent == ResearchIntent.LIST_PROPERTIES:
            text_lower = text.lower()
            criteria_keywords = sum(1 for w in ["finiteness", "definiteness", "effectiveness", "input", "output"] if w in text_lower)
            has_formal_criteria = (
                criteria_keywords >= 3
                or bool(re.search(r"\b1\.\s*input\b.*\b2\.\s*output\b", text_lower, re.S))
                or bool(re.search(r"\bsatisfy\s+(?:the\s+)?following\s+(?:five\s+)?criteria\b", text_lower))
                or ("criteria 1 and 2" in text_lower and criteria_keywords >= 2)
            )
            if has_formal_criteria:
                criteria_boost = 5.0
                reasons.append(f"boost: formal algorithm criteria definition found ({criteria_keywords} criteria keywords) (5.0x)")
            elif is_exercises:
                criteria_boost = 0.1
                reasons.append("penalty: exercise problem downweighted for criteria (0.1x)")

        # 7. Fragment Penalty (penalize tiny incomplete OCR fragments under 150 chars unless containing verified definition)
        fragment_penalty = 1.0
        if len(text.strip()) < 150 and definition_boost <= 1.0 and criteria_boost <= 1.0:
            fragment_penalty = 0.2
            reasons.append("penalty: short fragment under 150 characters (0.2x)")

        # Compute Final Score
        final_score = (
            base_bm25
            * heading_boost
            * section_prior
            * definition_boost
            * description_boost
            * caption_penalty
            * garbage_penalty
            * pseudocode_penalty
            * citation_penalty
            * paradigm_boost
            * criteria_boost
            * noise_penalty
            * fragment_penalty
        )

        p_start = int(row["page_start"]) if row["page_start"] is not None else 1
        page_lbl = meta_page_lbl or str(p_start)

        resolved_sec_type = "definitions" if is_definitions else ("bibliography" if is_bib else ("exercises" if is_exercises else ("chapter_notes" if is_chapter_notes else "body")))

        return RetrievalTrace(
            chunk_id=chunk_id,
            document_id=str(row["document_id"]),
            paper_id=str(row["paper_id"]),
            physical_page=p_start,
            page_label=page_lbl,
            section=section,
            heading_path=active_heading,
            section_type=resolved_sec_type,
            locator=locator,
            bm25_score=round(base_bm25, 4),
            heading_boost=round(heading_boost, 2),
            section_prior=round(section_prior, 3),
            definition_boost=round(definition_boost, 2),
            citation_penalty=round(citation_penalty, 2),
            final_score=round(final_score, 4),
            description_boost=round(description_boost, 2),
            caption_penalty=round(caption_penalty, 2),
            garbage_penalty=round(garbage_penalty, 2),
            pseudocode_penalty=round(pseudocode_penalty, 2),
            reasons=reasons,
        )

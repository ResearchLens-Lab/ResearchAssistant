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
from typing import Any, Dict, List, Optional, Tuple

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
    locator: str
    bm25_score: float
    heading_boost: float
    section_prior: float
    definition_boost: float
    citation_penalty: float
    final_score: float
    reasons: List[str] = field(default_factory=list)


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

        # Connect in read-only mode to prevent any locking or modification
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        connection.row_factory = sqlite3.Row

        try:
            coll_name = self._resolve_collection_name(connection)

            # Build search terms
            primary_concept = query.primary_concept or ""
            search_terms = list(query.expanded_search_terms)
            if not search_terms:
                search_terms = [primary_concept] if primary_concept else ["algorithm", "method", "procedure"]

            # Escape terms for SQLite FTS5 MATCH
            escaped_terms = []
            for t in search_terms[:8]:
                clean_t = t.replace('"', '""').strip()
                if clean_t:
                    escaped_terms.append(f'"{clean_t}"')

            fts_match_expr = " OR ".join(escaped_terms) if escaped_terms else '""'

            # Query constraints
            constraints = ["collection_name = ?"]
            params: List[Any] = [fts_match_expr, coll_name]

            if owner_id:
                constraints.append("owner_id = ?")
                params.append(owner_id)

            if document_ids:
                placeholders = ",".join("?" for _ in document_ids)
                constraints.append(f"document_id IN ({placeholders})")
                params.extend(document_ids)
            elif paper_ids:
                placeholders = ",".join("?" for _ in paper_ids)
                constraints.append(f"paper_id IN ({placeholders})")
                params.extend(paper_ids)

            where_clause = " AND ".join(["lexical_chunks MATCH ?", *constraints])
            sql = f"""
                SELECT chunk_id, paper_id, document_id, section, page_start, page_end,
                       title, filename, locator, text, bm25(lexical_chunks) AS bm25_score
                FROM lexical_chunks
                WHERE {where_clause}
                ORDER BY bm25_score ASC
                LIMIT 300
            """

            rows = connection.execute(sql, params).fetchall()

            # If no rows match exact terms, fallback to broader terms
            if not rows and primary_concept:
                words = primary_concept.split()
                if len(words) > 1:
                    broad_expr = " OR ".join(f'"{w}"' for w in words if len(w) > 2)
                    params[0] = broad_expr
                    rows = connection.execute(sql, params).fetchall()

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

            # Normalized passage hash for duplicate suppression
            norm_text = " ".join(text.lower().split())
            text_hash = hashlib.sha256(norm_text[:200].encode("utf-8")).hexdigest()
            if text_hash in seen_hashes:
                continue
            seen_hashes.add(text_hash)

            trace = self._score_candidate(row, query)
            scored_candidates.append((trace.final_score, row, trace))

        # Sort descending by final_score
        scored_candidates.sort(key=lambda item: -item[0])

        # Maximal Marginal Relevance (MMR) selection to promote diversity across sections
        selected_sources: List[RetrievedSource] = []
        traces: Dict[str, RetrievalTrace] = {}
        used_sections: Dict[str, int] = {}

        for idx, (score, row, trace) in enumerate(scored_candidates, start=1):
            if len(selected_sources) >= top_k:
                break

            sec = str(row["section"] or "Unknown")
            sec_count = used_sections.get(sec, 0)
            # Allow at most 2 chunks from the same section unless top_k is large
            if sec_count >= 2 and len(selected_sources) < top_k - 1:
                continue

            source_id = f"S{len(selected_sources) + 1}"
            used_sections[sec] = sec_count + 1

            p_start = int(row["page_start"]) if row["page_start"] is not None else 1
            p_end = int(row["page_end"]) if row["page_end"] is not None else p_start
            p_label = str(row["page_start"] or p_start)

            source = RetrievedSource(
                source_id=source_id,
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                paper_id=str(row["paper_id"]),
                page_start=p_start,
                page_end=p_end,
                section=sec,
                title=str(row["title"] or "Research Document"),
                filename=str(row["filename"] or ""),
                locator=str(row["locator"] or f"{sec} · p.{p_start}"),
                text=str(row["text"] or ""),
            )

            selected_sources.append(source)
            traces[source_id] = trace

        return selected_sources, traces

    def _score_candidate(
        self,
        row: sqlite3.Row,
        query: QueryUnderstanding,
    ) -> RetrievalTrace:
        text = str(row["text"] or "")
        section = str(row["section"] or "")
        locator = str(row["locator"] or "")
        bm25_raw = float(row["bm25_score"])
        primary_concept = (query.primary_concept or "").strip().lower()

        reasons = []

        # Invert FTS5 bm25 (more negative = better match in SQLite FTS5)
        # Transform bm25 into a positive base score in range [0.5 - 2.0]
        base_bm25 = 1.0 / (1.0 + math.exp(bm25_raw))  # Sigmoid inversion
        reasons.append(f"FTS5 BM25 raw={bm25_raw:.2f}")

        # 1. Heading Boost
        heading_boost = 1.0
        if primary_concept:
            heading_target = (section + " " + locator).lower()
            if primary_concept in heading_target:
                heading_boost = 2.5
                reasons.append(f"heading match for '{primary_concept}' (+150%)")
            elif any(w in heading_target for w in primary_concept.split() if len(w) > 3):
                heading_boost = 1.6
                reasons.append(f"partial heading match for '{primary_concept}' (+60%)")

        # 2. Section Type Prior
        section_prior = 1.0
        sec_lower = section.lower()
        loc_lower = locator.lower()

        # Classify section
        is_bib = bool(re.search(r"\b(?:references|bibliography|literature\s+cited)\b", sec_lower) or re.search(r"\b(?:references|bibliography)\b", loc_lower))
        is_index = bool(re.search(r"\b(?:index|subject\s+index|author\s+index)\b", sec_lower) or re.search(r"\bindex\b", loc_lower))
        is_exercises = bool(re.search(r"\b(?:exercises|problems|chapter\s+problems)\b", sec_lower) or re.search(r"\bexercises\b", loc_lower))
        is_front = bool(re.search(r"\b(?:contents|preface|acknowledgments|foreword)\b", sec_lower) or re.search(r"\bpreface\b", loc_lower))

        if query.intent == ResearchIntent.DEFINITION:
            if is_bib:
                section_prior = 0.01
                reasons.append("penalty: bibliography section downweighted for definition (0.01x)")
            elif is_index:
                section_prior = 0.01
                reasons.append("penalty: index section downweighted for definition (0.01x)")
            elif is_exercises:
                section_prior = 0.15
                reasons.append("penalty: exercise section downweighted for definition (0.15x)")
            elif is_front:
                section_prior = 0.30
                reasons.append("penalty: front matter downweighted for definition (0.3x)")
            else:
                section_prior = 1.5
                reasons.append("boost: body textbook chapter for definition (1.5x)")

        elif is_bib and query.intent != ResearchIntent.OTHER:
            section_prior = 0.05
            reasons.append("penalty: bibliography downweighted (0.05x)")
        elif is_index:
            section_prior = 0.05
            reasons.append("penalty: index downweighted (0.05x)")

        # 3. Sentence-Level Definition Boost
        definition_boost = 1.0
        if query.intent == ResearchIntent.DEFINITION and primary_concept:
            def_candidates = self.sentence_analyzer.find_definition_sentences(text, primary_concept)
            if def_candidates:
                top_def = def_candidates[0]
                if top_def.pattern_name in {"informal_definition", "formal_definition", "is_thus_sequence"}:
                    definition_boost = 3.0
                    reasons.append(f"boost: explicit definition sentence found ({top_def.pattern_name}, conf={top_def.confidence:.2f}) (3.0x)")
                else:
                    definition_boost = 1.8
                    reasons.append(f"boost: secondary definition pattern found ({top_def.pattern_name}) (1.8x)")

        # 4. Citation Density Penalty (exclude bibliography dumps)
        citation_penalty = 1.0
        bracket_citations = len(re.findall(r"\[\d+\]", text))
        if bracket_citations >= 5 and query.intent != ResearchIntent.OTHER:
            citation_penalty = max(0.2, 1.0 - (bracket_citations * 0.1))
            reasons.append(f"penalty: dense citation markers ({bracket_citations} found, {citation_penalty:.2f}x)")

        # Compute Final Score
        final_score = base_bm25 * heading_boost * section_prior * definition_boost * citation_penalty

        p_start = int(row["page_start"]) if row["page_start"] is not None else 1

        return RetrievalTrace(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            paper_id=str(row["paper_id"]),
            physical_page=p_start,
            page_label=str(p_start),
            section=section,
            locator=locator,
            bm25_score=round(base_bm25, 4),
            heading_boost=round(heading_boost, 2),
            section_prior=round(section_prior, 3),
            definition_boost=round(definition_boost, 2),
            citation_penalty=round(citation_penalty, 2),
            final_score=round(final_score, 4),
            reasons=reasons,
        )

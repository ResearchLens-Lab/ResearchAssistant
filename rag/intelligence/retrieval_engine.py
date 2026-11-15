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

        # For comparison queries with 2 distinct concepts, retrieve separately and combine
        if query.intent == ResearchIntent.COMPARISON and len(query.target_concepts) >= 2:
            return self._retrieve_comparison_dual(query, paper_ids, document_ids, top_k, owner_id)

        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        connection.row_factory = sqlite3.Row

        try:
            coll_name = self._resolve_collection_name(connection)

            # Check if content terms exist in library vocabulary (out-of-scope check)
            content_terms = [t for t in query.target_concepts if len(t) > 2]
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
            if not search_terms:
                search_terms = [primary_concept] if primary_concept else ["algorithm", "method", "procedure"]

            # Exact phrase query for primary concept should be prioritized
            escaped_terms = []
            for t in search_terms[:8]:
                clean_t = t.replace('"', '""').strip()
                if clean_t:
                    escaped_terms.append(f'"{clean_t}"')

            fts_match_expr = " OR ".join(escaped_terms) if escaped_terms else '""'

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

            # Check if lexical_metadata table exists
            has_meta = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='lexical_metadata'"
            ).fetchone()[0] > 0

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

        for idx, (score, row, trace) in enumerate(scored_candidates, start=1):
            if len(selected_sources) >= top_k:
                break

            sec = trace.heading_path or trace.section or "Section"
            sec_count = used_sections.get(sec, 0)
            if sec_count >= 2 and len(selected_sources) < top_k - 1 and len(scored_candidates) > top_k:
                continue

            source_id = f"S{len(selected_sources) + 1}"
            used_sections[sec] = sec_count + 1

            p_start = int(row["page_start"]) if row["page_start"] is not None else 1
            p_end = int(row["page_end"]) if row["page_end"] is not None else p_start
            p_label = trace.page_label or str(p_start)

            locator = trace.heading_path if trace.heading_path else str(row["locator"] or f"{sec} · p.{p_start}")
            if p_label and f"p.{p_label}" not in locator:
                locator = f"{locator} · p.{p_label}"

            source = RetrievedSource(
                source_id=source_id,
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                paper_id=str(row["paper_id"]),
                page_start=p_start,
                page_end=p_end,
                section=trace.section,
                title=str(row["title"] or "Research Document"),
                filename=str(row["filename"] or ""),
                locator=locator,
                text=str(row["text"] or ""),
            )

            selected_sources.append(source)
            traces[source_id] = trace

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
            intent=ResearchIntent.EXPLANATION,
            target_concepts=[c1],
            primary_concept=c1,
            expanded_search_terms=[c1] + query.expanded_search_terms,
        )
        q2 = QueryUnderstanding(
            raw_query=f"Explain {c2}",
            normalized_query=c2,
            intent=ResearchIntent.EXPLANATION,
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
        section = str(row["section"] or "")
        locator = str(row["locator"] or "")
        bm25_raw = float(row["bm25_score"])
        primary_concept = (query.primary_concept or "").strip().lower()

        # Metadata fields from lexical_metadata join
        meta_heading = str(row["meta_heading"] or "") if "meta_heading" in row.keys() and row["meta_heading"] else ""
        meta_sec_type = str(row["meta_section_type"] or "") if "meta_section_type" in row.keys() and row["meta_section_type"] else ""
        meta_page_lbl = str(row["meta_page_label"] or "") if "meta_page_label" in row.keys() and row["meta_page_label"] else ""

        reasons = []

        base_bm25 = 1.0 / (1.0 + math.exp(bm25_raw))
        reasons.append(f"FTS5 BM25 raw={bm25_raw:.2f}")

        # 1. Heading Boost
        heading_boost = 1.0
        active_heading = meta_heading or locator or section
        if primary_concept:
            heading_target = (active_heading + " " + locator).lower()
            if chunk_id in heading_matched_cids:
                heading_boost = 3.0
                reasons.append(f"headings_fts exact match for '{primary_concept}' (+200%)")
            elif primary_concept in heading_target:
                heading_boost = 2.5
                reasons.append(f"heading path match for '{primary_concept}' (+150%)")
            elif any(w in heading_target for w in primary_concept.split() if len(w) > 3):
                heading_boost = 1.6
                reasons.append(f"partial heading match for '{primary_concept}' (+60%)")

        # 2. Section Type Prior
        sec_lower = (section + " " + active_heading).lower()
        sec_type = meta_sec_type.lower() if meta_sec_type else ""

        is_bib = sec_type == "bibliography" or bool(re.search(r"\b(?:references|bibliography|literature\s+cited)\b", sec_lower))
        is_index = sec_type == "index" or bool(re.search(r"\b(?:index|subject\s+index|author\s+index)\b", sec_lower))
        is_exercises = sec_type in ("exercises", "problems") or bool(re.search(r"\b(?:exercises|problems|chapter\s+problems)\b", sec_lower))
        is_chapter_notes = sec_type == "chapter_notes" or bool(re.search(r"\b(?:chapter\s+notes|historical\s+notes|notes\s+and\s+references)\b", sec_lower))
        is_front = sec_type == "front_matter" or bool(re.search(r"\b(?:contents|preface|acknowledgments|foreword)\b", sec_lower))
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
                section_prior = 0.25
                reasons.append("penalty: front matter downweighted for definition (0.25x)")
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
            else:
                section_prior = 1.6
                reasons.append("boost: body section for complexity (1.6x)")
        elif query.intent == ResearchIntent.LOCATE:
            if is_index:
                section_prior = 2.5
                reasons.append("boost: index highly relevant for locate (2.5x)")
            else:
                section_prior = 1.2
        else:
            if is_bib and query.intent != ResearchIntent.OTHER:
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
            reasons=reasons,
        )

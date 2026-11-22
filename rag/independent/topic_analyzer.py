"""
Topic Coverage and Topic Count Analysis for Structured Research Documents.
Analyzes academic sections, detects topic groups and listed subtopics, and ranks
sections by verified curriculum/syllabus volume without external models.
"""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class LeafTopicRecord:
    topic_name: str
    parent_group: str
    section_name: str
    page: int
    char_offset_start: int
    char_offset_end: int
    confidence: float
    source_id: str = "S1"
    chunk_id: str = ""
    paper_id: str = ""
    document_id: str = ""


@dataclass
class TopicGroup:
    name: str
    subtopics: list[str]
    raw_text: str


@dataclass
class SectionTopicProfile:
    section_name: str
    page_start: int
    page_end: int
    source_id: str
    chunk_id: str
    paper_id: str
    document_id: str
    main_groups: list[str]
    main_group_count: int
    subtopics: list[str]
    subtopics_count: int
    raw_text: str
    supporting_passage: str
    groups: list[TopicGroup] = field(default_factory=list)
    leaf_topics: list[str] = field(default_factory=list)
    leaf_topic_count: int = 0
    leaf_records: list[LeafTopicRecord] = field(default_factory=list)
    main_disciplines: list[str] = field(default_factory=list)
    main_disciplines_count: int = 0


@dataclass
class TopicRankingResult:
    winning_section: Optional[SectionTopicProfile]
    fewest_section: Optional[SectionTopicProfile]
    rankings: list[SectionTopicProfile]
    total_sections: int
    is_tie: bool
    tie_sections: list[str]
    counting_methodology: str
    limitations: list[str]


class TopicCoverageAnalyzer:
    """
    Analyzes document sections to extract topic hierarchy, count topic groups and subtopics,
    and generate verified section rankings.
    """

    @staticmethod
    def _clean_text(text: str) -> str:
        norm = unicodedata.normalize("NFKC", text)
        return " ".join(norm.split())

    @staticmethod
    def _extract_leaf_topics(clause: str) -> list[str]:
        # Split on commas outside parentheses
        parts = re.split(r',\s*(?![^()]*\))', clause)
        leafs = []
        for p in parts:
            clean = p.strip(' .;:,–-')
            clean = re.sub(r'\s*GATE\s+\d{4}\s+IIT\s+Madras.*$', '', clean, flags=re.I).strip()
            if clean and len(clean) > 2:
                leafs.append(clean)
        return leafs

    @classmethod
    def analyze_section(
        cls,
        section_name: str,
        text: str,
        page_start: int = 1,
        page_end: int = 1,
        source_id: str = "S1",
        chunk_id: str = "",
        paper_id: str = "",
        document_id: str = "",
    ) -> SectionTopicProfile:
        clean_body = text.strip()
        base_section_title = section_name.split(":", 1)[-1].strip() if ":" in section_name else section_name

        # Detect colon-delimited subject headers (e.g., 'Discrete Mathematics:', 'Linear Algebra:')
        colon_pattern = re.compile(r'(?:^|(?<=[\n.!?])\s+)([A-Z][A-Za-z\s/&–-]{2,40}):\s*')
        colon_matches = list(colon_pattern.finditer(clean_body))

        topic_groups: list[TopicGroup] = []
        all_subtopics: list[str] = []
        all_leaf_records: list[LeafTopicRecord] = []

        if len(colon_matches) >= 2:
            # We have multiple distinct subject headings inside this section!
            for i, m in enumerate(colon_matches):
                group_name = m.group(1).strip()
                start_content = m.end()
                end_content = colon_matches[i + 1].start() if i + 1 < len(colon_matches) else len(clean_body)
                content = clean_body[start_content:end_content].strip()

                raw_clauses = [s.strip() for s in re.split(r"(?<=[.;])\s+", content) if s.strip()]
                group_subtopics = []
                for clause in raw_clauses:
                    clean_clause = clause.strip(" .;:,–-")
                    clean_clause = re.sub(r'\s*GATE\s+\d{4}\s+IIT\s+Madras.*$', '', clean_clause, flags=re.I).strip()
                    if clean_clause and len(clean_clause) > 2:
                        group_subtopics.append(clean_clause)
                        # Extract leaf topics
                        for leaf in cls._extract_leaf_topics(clean_clause):
                            start_off = clean_body.find(leaf, m.start())
                            end_off = (start_off + len(leaf)) if start_off != -1 else 0
                            all_leaf_records.append(LeafTopicRecord(
                                topic_name=leaf,
                                parent_group=group_name,
                                section_name=section_name,
                                page=page_start,
                                char_offset_start=max(0, start_off),
                                char_offset_end=max(0, end_off),
                                confidence=1.0,
                                source_id=source_id,
                                chunk_id=chunk_id,
                                paper_id=paper_id,
                                document_id=document_id,
                            ))

                if not group_subtopics and content:
                    group_subtopics = [content]

                raw_snippet = clean_body[m.start():end_content].strip()
                topic_groups.append(TopicGroup(name=group_name, subtopics=group_subtopics, raw_text=raw_snippet))
                all_subtopics.extend(group_subtopics)
        else:
            # Single main subject group for this section
            raw_clauses = [s.strip() for s in re.split(r"(?<=[.;])\s+", clean_body) if s.strip()]
            group_subtopics = []
            for clause in raw_clauses:
                clean_clause = clause.strip(" .;:,–-")
                clean_clause = re.sub(r'\s*GATE\s+\d{4}\s+IIT\s+Madras.*$', '', clean_clause, flags=re.I).strip()
                if clean_clause and len(clean_clause) > 2:
                    group_subtopics.append(clean_clause)
                    for leaf in cls._extract_leaf_topics(clean_clause):
                        start_off = clean_body.find(leaf)
                        end_off = (start_off + len(leaf)) if start_off != -1 else 0
                        all_leaf_records.append(LeafTopicRecord(
                            topic_name=leaf,
                            parent_group=base_section_title,
                            section_name=section_name,
                            page=page_start,
                            char_offset_start=max(0, start_off),
                            char_offset_end=max(0, end_off),
                            confidence=1.0,
                            source_id=source_id,
                            chunk_id=chunk_id,
                            paper_id=paper_id,
                            document_id=document_id,
                        ))

            if not group_subtopics and clean_body:
                group_subtopics = [clean_body]

            topic_groups.append(TopicGroup(name=base_section_title, subtopics=group_subtopics, raw_text=clean_body))
            all_subtopics.extend(group_subtopics)

        distinct_groups = list(dict.fromkeys(tg.name for tg in topic_groups))
        
        # Disciplinary mapping for multi-discipline sections like Engineering Mathematics
        disciplines_map = {
            "Discrete Mathematics": "Discrete Mathematics",
            "Graphs": "Discrete Mathematics",
            "Combinatorics": "Discrete Mathematics",
            "Linear Algebra": "Linear Algebra",
            "Calculus": "Calculus",
            "Probability and Statistics": "Probability and Statistics",
        }
        main_disciplines = list(dict.fromkeys(disciplines_map.get(g, g) for g in distinct_groups))

        first_p = topic_groups[0].raw_text if topic_groups else clean_body
        supporting_passage = cls._clean_text(first_p)[:220]
        leaf_names = [rec.topic_name for rec in all_leaf_records]

        return SectionTopicProfile(
            section_name=section_name,
            page_start=page_start,
            page_end=page_end,
            source_id=source_id,
            chunk_id=chunk_id,
            paper_id=paper_id,
            document_id=document_id,
            main_groups=distinct_groups,
            main_group_count=len(distinct_groups),
            subtopics=all_subtopics,
            subtopics_count=len(all_subtopics),
            raw_text=clean_body,
            supporting_passage=supporting_passage,
            groups=topic_groups,
            leaf_topics=leaf_names,
            leaf_topic_count=len(leaf_names),
            leaf_records=all_leaf_records,
            main_disciplines=main_disciplines,
            main_disciplines_count=len(main_disciplines),
        )

    @classmethod
    def rank_sections(cls, sections: list[SectionTopicProfile]) -> TopicRankingResult:
        if not sections:
            return TopicRankingResult(
                winning_section=None,
                fewest_section=None,
                rankings=[],
                total_sections=0,
                is_tie=False,
                tie_sections=[],
                counting_methodology="No section records available.",
                limitations=["No extractable sections found in document."],
            )

        # Sort sections:
        # Primary key: leaf_topic_count (descending)
        # Secondary key: subtopics_count (descending)
        # Tertiary key: main_group_count (descending)
        ranked = sorted(
            sections,
            key=lambda s: (-s.leaf_topic_count, -s.subtopics_count, -s.main_group_count, s.page_start, s.section_name)
        )

        top = ranked[0]
        # For fewest section: find section with minimal leaf topics
        fewest_sorted = sorted(
            sections,
            key=lambda s: (s.leaf_topic_count, s.subtopics_count, s.main_group_count, s.page_start, s.section_name)
        )
        bottom = fewest_sorted[0]

        # Check for ties at the top
        ties = [s.section_name for s in ranked if s.leaf_topic_count == top.leaf_topic_count]
        is_tie = len(ties) > 1

        methodology = (
            "Sections are analyzed and ranked using verified hierarchical structure: "
            "(1) Leaf-Level Topics represent discrete curriculum concepts, algorithms, methods, or data structures. "
            "(2) Listed Subtopics represent individual curriculum clause statements. "
            "(3) Main Topic Groups represent major subject divisions (colon-delimited headings). "
            "Primary ranking is determined by the total count of verified leaf-level topic entries, followed by listed subtopic clauses and subject groups."
        )

        limitations = []
        if is_tie:
            limitations.append(f"Top rank is tied between: {', '.join(ties)}.")
        if any(s.leaf_topic_count <= 5 for s in ranked):
            limitations.append("Sections with concise outlines or dense technical phrases have lower raw entry counts than multi-disciplinary divisions.")

        return TopicRankingResult(
            winning_section=None if is_tie else top,
            fewest_section=bottom,
            rankings=ranked,
            total_sections=len(ranked),
            is_tie=is_tie,
            tie_sections=ties if is_tie else [],
            counting_methodology=methodology,
            limitations=limitations,
        )

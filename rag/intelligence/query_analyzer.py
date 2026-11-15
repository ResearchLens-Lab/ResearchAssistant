"""
Query Understanding and Intent Analysis.
Deterministic rule-based classification across 12+ research intents,
target concept slot extraction, and section ranking priors.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class ResearchIntent(str, enum.Enum):
    DEFINITION = "DEFINITION"
    EXPLANATION = "EXPLANATION"
    COMPARISON = "COMPARISON"
    PROCEDURE = "PROCEDURE"
    COMPLEXITY = "COMPLEXITY"
    THEOREM_LOOKUP = "THEOREM_LOOKUP"
    EXAMPLE = "EXAMPLE"
    LIST_PROPERTIES = "LIST_PROPERTIES"
    LOCATE = "LOCATE"
    SUMMARIZATION = "SUMMARIZATION"
    COUNT_RANKING = "COUNT_RANKING"
    RELATIONSHIP = "RELATIONSHIP"
    OTHER = "OTHER"


@dataclass
class QueryUnderstanding:
    raw_query: str
    normalized_query: str
    intent: ResearchIntent
    target_concepts: List[str] = field(default_factory=list)
    primary_concept: Optional[str] = None
    secondary_concept: Optional[str] = None
    query_constraints: Dict[str, Any] = field(default_factory=dict)
    section_priors: Dict[str, float] = field(default_factory=dict)
    expanded_search_terms: List[str] = field(default_factory=list)
    matched_rule: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "intent": self.intent.value,
            "primary_concept": self.primary_concept,
            "target_concepts": self.target_concepts,
            "query_constraints": self.query_constraints,
            "section_priors": self.section_priors,
            "expanded_search_terms": self.expanded_search_terms,
            "matched_rule": self.matched_rule,
        }


# Default section priors per intent
DEFAULT_SECTION_PRIORS: Dict[ResearchIntent, Dict[str, float]] = {
    ResearchIntent.DEFINITION: {
        "definitions": 3.0,
        "body": 1.6,
        "front_matter": 0.2,
        "exercises": 0.1,
        "problems": 0.1,
        "chapter_notes": 0.2,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.COMPLEXITY: {
        "body": 1.8,
        "definitions": 1.5,
        "appendix": 1.3,
        "exercises": 0.4,
        "problems": 0.4,
        "chapter_notes": 0.3,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.PROCEDURE: {
        "body": 1.8,
        "examples": 1.5,
        "definitions": 1.2,
        "exercises": 0.3,
        "problems": 0.3,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.COMPARISON: {
        "body": 1.6,
        "examples": 1.3,
        "definitions": 1.2,
        "exercises": 0.3,
        "bibliography": 0.02,
        "index": 0.01,
    },
    ResearchIntent.THEOREM_LOOKUP: {
        "body": 1.8,
        "appendix": 1.5,
        "definitions": 1.2,
        "exercises": 0.3,
        "bibliography": 0.05,
        "index": 0.02,
    },
    ResearchIntent.EXAMPLE: {
        "examples": 2.5,
        "body": 1.6,
        "exercises": 0.6,
        "problems": 0.5,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.LIST_PROPERTIES: {
        "body": 1.8,
        "definitions": 1.6,
        "front_matter": 0.5,
        "exercises": 0.3,
        "bibliography": 0.02,
        "index": 0.01,
    },
    ResearchIntent.LOCATE: {
        "index": 2.5,
        "body": 1.6,
        "front_matter": 1.4,
        "bibliography": 0.5,
    },
    ResearchIntent.SUMMARIZATION: {
        "body": 1.6,
        "front_matter": 1.3,
        "chapter_notes": 1.2,
        "bibliography": 0.1,
        "index": 0.05,
    },
    ResearchIntent.COUNT_RANKING: {
        "front_matter": 1.6,
        "body": 1.5,
        "index": 1.3,
        "bibliography": 0.1,
    },
    ResearchIntent.RELATIONSHIP: {
        "body": 1.7,
        "chapter_notes": 1.3,
        "definitions": 1.2,
        "bibliography": 0.05,
        "index": 0.01,
    },
    ResearchIntent.EXPLANATION: {
        "body": 1.7,
        "examples": 1.4,
        "definitions": 1.2,
        "exercises": 0.3,
        "bibliography": 0.02,
        "index": 0.01,
    },
    ResearchIntent.OTHER: {
        "body": 1.0,
        "definitions": 1.0,
        "front_matter": 1.0,
        "bibliography": 0.2,
        "index": 0.1,
    },
}


class QueryAnalyzer:
    """Classifies user research questions into structured intents and extracts target slots."""

    STOPWORDS = frozenset({
        "a", "about", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
        "was", "what", "when", "where", "which", "who", "why", "will", "with",
        "tell", "me", "show", "give", "explain", "describe", "discuss",
    })

    def analyze(self, query: str) -> QueryUnderstanding:
        clean = unicodedata.normalize("NFKC", query).strip()
        lower = clean.casefold()

        # 1. DEFINITION
        # "What is an algorithm?", "Define merge sort", "What is meant by dynamic programming?"
        m_def = (
            re.search(r"^\s*what\s+is\s+(?:an?|the)?\s*([a-z0-9\s-]{2,60}?)(?:\s+in\s+computer\s+science|\s+in\s+algorithms)?\??$", lower)
            or re.search(r"^\s*define\s+(?:an?|the)?\s*([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bdefinition\s+of\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bwhat\s+is\s+meant\s+by\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        def_exclusions = [
            "complexity", "time complexity", "space complexity", "work", "difference", "compare",
            "procedure", "theorem", "lemma", "steps", "properties", "example", "loop invariant",
            "characteristics", "elements", "components", "operations",
        ]
        if m_def and not any(k in lower for k in def_exclusions):
            concept = m_def.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.DEFINITION, [concept], "definition_pattern",
                synonyms=self._concept_synonyms(concept)
            )

        # 2. COMPLEXITY
        # "What is the time complexity of heap sort?", "Space complexity of merge sort", "Running time of quicksort"
        m_comp = (
            re.search(r"\b(?:what\s+is\s+the\s+)?(?:worst-case\s+)?(?:time|space)?\s*complexity\s+(?:of\s+)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:worst-case\s+)?(?:running|search|lookup)\s+time\s+(?:of|in|for)\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:big\s+o|asymptotic\s+bound|theta\s+bound)\s+(?:of|for)\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_comp:
            concept = m_comp.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.COMPLEXITY, [concept], "complexity_pattern",
                constraints={"metric": "complexity"},
                synonyms=[concept, "running time", "worst-case", "big-O", "theta"]
            )

        # 3. PROCEDURE
        # "Explain how binary search works", "How does quicksort partition work?", "Steps of Dijkstra's algorithm"
        m_proc = (
            re.search(r"\bexplain\s+how\s+([a-z0-9\s-]{2,60}?)\s+(?:works?|operates?)\??$", lower)
            or re.search(r"\bhow\s+(?:does|to)\s+([a-z0-9\s-]{2,60}?)\s+(?:work|build|partition|operate)\b", lower)
            or re.search(r"\bsteps\s+(?:of|for|to)\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bprocedure\s+(?:of|for|to)\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\balgorithm\s+for\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_proc:
            concept = m_proc.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.PROCEDURE, [concept], "procedure_pattern",
                synonyms=[concept, "procedure", "steps", "algorithm", "pseudocode"]
            )

        # 4. COMPARISON
        # "Compare merge sort and quicksort", "Difference between BFS and DFS", "merge sort vs quicksort"
        m_comp = (
            re.search(r"\bcompare\s+([a-z0-9\s-]{2,40})\s+(?:and|with|versus|vs\.?)\s+([a-z0-9\s-]{2,40})\??$", lower)
            or re.search(r"\bdifferences?\s+between\s+([a-z0-9\s-]{2,40})\s+and\s+([a-z0-9\s-]{2,40})\??$", lower)
            or re.search(r"^([a-z0-9\s-]{2,40})\s+vs\.?\s+([a-z0-9\s-]{2,40})\??$", lower)
        )
        if m_comp:
            c1, c2 = m_comp.group(1).strip(), m_comp.group(2).strip()
            return self._build_result(
                clean, ResearchIntent.COMPARISON, [c1, c2], "comparison_pattern",
                synonyms=[c1, c2, "comparison", "difference", "versus"]
            )

        # 5. LIST_PROPERTIES
        # "List the properties of an algorithm", "Characteristics of a greedy choice"
        m_list = re.search(r"\b(?:list|what\s+are)\s+(?:the\s+)?(?:essential\s+)?(?:properties|characteristics|features|components|operations|elements)\s+(?:of|supported\s+by|in)\s+([a-z0-9\s-]{2,60})\??$", lower)
        if m_list:
            concept = m_list.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.LIST_PROPERTIES, [concept], "list_properties_pattern",
                synonyms=[concept, "properties", "characteristics", "criteria"]
            )

        # 6. LOCATE
        # "Where is dynamic programming discussed?", "Which chapter covers graph algorithms?"
        m_loc = (
            re.search(r"\bwhere\s+is\s+([a-z0-9\s-]{2,60})\s+(?:discussed|covered|found|introduced|located)\??$", lower)
            or re.search(r"\bwhich\s+chapter\s+(?:covers?|discusses?)\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_loc:
            concept = m_loc.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.LOCATE, [concept], "locate_pattern",
                synonyms=[concept, "chapter", "section", "overview"]
            )

        # 7. THEOREM_LOOKUP
        # "Master theorem", "Theorem 4.1", "Proof of Master theorem", "Cook's theorem", "loop invariant"
        m_thm = re.search(r"\b(master\s+theorem|theorem\s+[0-9.]+|theorem|lemma\s+[0-9.]+|corollary\s+[0-9.]+|lower\s+bound\s+theorem|cook'?s\s+theorem|max-flow\s+min-cut|loop\s+invariant)\b", lower)
        if m_thm:
            concept = m_thm.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.THEOREM_LOOKUP, [concept], "theorem_lookup_pattern",
                synonyms=[concept, "theorem", "proof", "recurrence", "cases"]
            )

        # 8. EXAMPLE
        # "Give an example of dynamic programming", "Example of NP-complete problem", "Give an application of"
        m_ex = re.search(r"\b(?:give\s+an?|show\s+an?|provide\s+an?)?\s*(?:examples?|applications?)\s+(?:of|where)\s+([a-z0-9\s-]{2,60})\??$", lower)
        if m_ex:
            concept = m_ex.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.EXAMPLE, [concept], "example_pattern",
                synonyms=[concept, "example", "instance", "illustration"]
            )

        # 9. COUNT_RANKING
        # "Which section has the most topics?", "Rank sections by syllabus coverage"
        if re.search(r"\bwhich\s+section\b.{0,30}\b(?:most|more|highest|largest|least|fewest)\b", lower) or re.search(r"\brank\s+sections?\b", lower):
            return self._build_result(
                clean, ResearchIntent.COUNT_RANKING, ["sections"], "count_ranking_pattern",
                synonyms=["section", "topics", "syllabus", "coverage"]
            )

        # 10. SUMMARIZATION
        # "Summarize chapter 2", "Overview of sorting algorithms"
        m_sum = re.search(r"\b(?:summarize|summary\s+of|overview\s+of)\s+([a-z0-9\s-]{2,60})\??$", lower)
        if m_sum:
            concept = m_sum.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.SUMMARIZATION, [concept], "summarization_pattern",
                synonyms=[concept, "summary", "overview", "main topics"]
            )

        # 11. RELATIONSHIP
        # "How is insertion sort related to bubble sort?", "Relationship between P and NP"
        m_rel = re.search(r"\b(?:relationship\s+between|how\s+is\s+([a-z0-9\s-]{2,40})\s+related\s+to)\s+([a-z0-9\s-]{2,40})", lower)
        if m_rel:
            c1 = m_rel.group(1) or ""
            c2 = m_rel.group(2) or ""
            concepts = [c for c in [c1.strip(), c2.strip()] if c]
            return self._build_result(
                clean, ResearchIntent.RELATIONSHIP, concepts, "relationship_pattern",
                synonyms=concepts + ["relationship", "connection", "similar"]
            )

        # 12. EXPLANATION (General)
        # "Explain quicksort", "Why is mergesort O(n log n)?"
        m_exp = re.search(r"\b(?:explain|describe|why\s+is|what\s+does)\s+([a-z0-9\s-]{2,60})\??$", lower)
        if m_exp:
            concept = m_exp.group(1).strip()
            return self._build_result(
                clean, ResearchIntent.EXPLANATION, [concept], "explanation_pattern",
                synonyms=[concept, "explanation", "details"]
            )

        # Fallback OTHER
        terms = [w for w in re.findall(r"\b[a-z]{3,}\b", lower) if w not in self.STOPWORDS]
        primary = terms[0] if terms else None
        return self._build_result(
            clean, ResearchIntent.OTHER, terms[:2], "fallback",
            synonyms=terms[:5]
        )

    def _build_result(
        self,
        raw_query: str,
        intent: ResearchIntent,
        concepts: List[str],
        rule_name: str,
        constraints: Optional[Dict[str, Any]] = None,
        synonyms: Optional[List[str]] = None,
    ) -> QueryUnderstanding:
        primary = concepts[0] if concepts else None
        secondary = concepts[1] if len(concepts) > 1 else None
        priors = dict(DEFAULT_SECTION_PRIORS.get(intent, DEFAULT_SECTION_PRIORS[ResearchIntent.OTHER]))

        search_terms = list(dict.fromkeys([c for c in concepts if c] + (synonyms or [])))

        return QueryUnderstanding(
            raw_query=raw_query,
            normalized_query=raw_query.strip(),
            intent=intent,
            target_concepts=concepts,
            primary_concept=primary,
            secondary_concept=secondary,
            query_constraints=constraints or {},
            section_priors=priors,
            expanded_search_terms=search_terms,
            matched_rule=rule_name,
        )

    @staticmethod
    def _concept_synonyms(concept: str) -> List[str]:
        concept_clean = concept.strip().lower()
        if concept_clean == "algorithm":
            return ["algorithm", "computational procedure", "sequence of computational steps", "procedure"]
        if "sort" in concept_clean:
            return [concept_clean, "sorting", "order", "reordering"]
        return [concept_clean]

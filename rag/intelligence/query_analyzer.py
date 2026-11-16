"""
Query Understanding and Intent Analysis.
Deterministic rule-based classification across 13 research intents,
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
    EVIDENCE_VERIFICATION = "EVIDENCE_VERIFICATION"
    CLASSIFICATION = "CLASSIFICATION"
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
        "chapter_notes": 0.15,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.COMPLEXITY: {
        "body": 1.8,
        "definitions": 1.5,
        "appendix": 1.3,
        "exercises": 0.3,
        "problems": 0.3,
        "chapter_notes": 0.15,
        "bibliography": 0.01,
        "index": 0.01,
    },
    ResearchIntent.PROCEDURE: {
        "body": 1.8,
        "examples": 1.5,
        "definitions": 1.2,
        "exercises": 0.3,
        "problems": 0.3,
        "chapter_notes": 0.15,
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
        "exercises": 0.5,
        "problems": 0.4,
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
    ResearchIntent.EVIDENCE_VERIFICATION: {
        "body": 1.8,
        "definitions": 1.5,
        "chapter_notes": 1.0,
        "exercises": 0.4,
        "bibliography": 0.05,
        "index": 0.01,
    },
    ResearchIntent.CLASSIFICATION: {
        "body": 1.8,
        "front_matter": 1.6,
        "definitions": 1.4,
        "chapter_notes": 0.5,
        "exercises": 0.2,
        "bibliography": 0.01,
        "index": 0.1,
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

    CONCEPT_ALIASES = {
        "algorithm": ["algorithm", "computational procedure", "sequence of computational steps", "procedure"],
        "heap sort": ["heap sort", "heapsort", "max-heap", "min-heap", "heapify"],
        "heapsort": ["heapsort", "heap sort", "max-heap", "min-heap", "heapify"],
        "merge sort": ["merge sort", "mergesort", "divide-and-conquer", "divide and conquer"],
        "mergesort": ["mergesort", "merge sort", "divide-and-conquer", "divide and conquer"],
        "quicksort": ["quicksort", "quick sort", "partition"],
        "quick sort": ["quick sort", "quicksort", "partition"],
        "binary search": ["binary search", "divide and conquer", "logarithmic time"],
        "dynamic programming": ["dynamic programming", "memoization", "optimal substructure", "subproblems"],
        "asymptotic notation": ["asymptotic notation", "big-O", "theta", "omega", "standard notations"],
        "loop invariant": ["loop invariant", "initialization", "maintenance", "termination", "correctness"],
    }

    def analyze(self, query: str) -> QueryUnderstanding:
        clean = unicodedata.normalize("NFKC", query).strip()
        orig_query = clean

        # Extract slash command if present at start of query (e.g. /table, /pie, /flowchart, /compare, /summary)
        slash_match = re.match(
            r"^\s*/(table|pie|chart|flowchart|mermaid|compare|summary|outline)\b\s*",
            clean,
            re.I,
        )
        output_format = None
        if slash_match:
            cmd = slash_match.group(1).lower()
            if cmd in ("table", "tabular"):
                output_format = "table"
            elif cmd in ("pie", "chart"):
                output_format = "pie"
            elif cmd in ("flowchart", "mermaid"):
                output_format = "flowchart"
            elif cmd == "compare":
                output_format = "compare"
            elif cmd in ("summary", "outline"):
                output_format = "summary"
            clean = clean[slash_match.end():].strip()
            if not clean:
                clean = "algorithms"
        elif re.search(
            r"\b(?:as\s+a\s+table|in\s+a\s+table|tabular\s+format|tabular\s+synthesis|make\s+a\s+table|give\s+(?:me\s+)?a\s+table|table\s+of)\b",
            clean.casefold(),
        ):
            output_format = "table"
        elif re.search(
            r"\b(?:pie\s+chart|distribution\s+chart|pie\s+graph)\b",
            clean.casefold(),
        ):
            output_format = "pie"
        elif re.search(
            r"\b(?:flowchart|flow\s+chart|process\s+flow)\b", clean.casefold()
        ):
            output_format = "flowchart"

        self._current_output_format = output_format
        self._current_raw_query = orig_query
        lower = clean.casefold()

        # 1. DEFINITION
        # "What is an algorithm?", "Define merge sort", "What is meant by dynamic programming?"
        # SEC-N21: Guard optional article with word boundary \b(?:an?|the)\b to prevent stripping first letter of concepts
        m_def = (
            re.search(r"^\s*what\s+is\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60}?)(?:\s+in\s+computer\s+science|\s+in\s+algorithms)?\??$", lower)
            or re.search(r"^\s*define\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bdefinition\s+of\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bwhat\s+is\s+meant\s+by\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        )
        def_exclusions = [
            "complexity", "time complexity", "space complexity", "work", "difference", "compare",
            "procedure", "theorem", "lemma", "steps", "properties", "example", "loop invariant",
            "characteristics", "elements", "components", "operations", "running time",
        ]
        if m_def and not any(k in lower for k in def_exclusions):
            concept = self._clean_concept(m_def.group(1))
            return self._build_result(
                clean, ResearchIntent.DEFINITION, [concept], "definition_pattern",
                synonyms=self._concept_synonyms(concept)
            )

        # 1.5. CLASSIFICATION / PARADIGMS / TYPES
        # "What are the different types of algorithms?", "Types of algorithms", "Categories of algorithms", "Algorithm design paradigms"
        m_cls = (
            re.search(r"\b(?:what\s+are\s+(?:the\s+)?)?(?:different\s+|major\s+|main\s+)?(?:types|classes|categories|kinds|paradigms|methods|approaches)\s+of\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"^(?:different\s+|major\s+|main\s+)?(?:types|classes|categories|kinds|paradigms)\s+of\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:algorithm|algorithmic)\s+(?:design\s+)?(?:paradigms|techniques|strategies|classes|types|categories)\b", lower)
            or re.search(r"\bclassification\s+of\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_cls:
            raw_target = m_cls.group(1) if (m_cls.lastindex and m_cls.group(1)) else "algorithm"
            concept = self._clean_concept(raw_target) or "algorithm"
            paradigms = [
                "divide and conquer",
                "greedy method",
                "dynamic programming",
                "backtracking",
                "branch and bound",
                "randomized algorithms",
                "approximation algorithms",
                "parallel algorithms",
            ]
            return self._build_result(
                clean, ResearchIntent.CLASSIFICATION, [concept], "classification_pattern",
                constraints={"taxonomy": "algorithmic_paradigms"},
                synonyms=[concept, *paradigms]
            )

        # 2. COMPLEXITY
        # "What is the worst-case time complexity of heap sort?", "Space complexity of merge sort", "Running time of quicksort"
        m_comp = (
            re.search(r"\b(?:what\s+is\s+the\s+)?(?:(worst[- ]case|average[- ]case|best[- ]case)\s+)?(?:(time|space)\s+)?complexity\s+(?:of\s+)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:(worst[- ]case|average[- ]case|best[- ]case)\s+)?(?:running|search|lookup)\s+time\s+(?:of|in|for)\s+([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:big\s+o|asymptotic\s+bound|theta\s+bound)\s+(?:of|for)\s+([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_comp:
            groups = m_comp.groups()
            concept_raw = groups[-1]
            concept = self._clean_concept(concept_raw)
            case_val = "worst-case" if "worst" in lower else ("average-case" if "average" in lower else ("best-case" if "best" in lower else "any"))
            resource_val = "space" if "space" in lower else "time"
            constraints = {"case": case_val, "resource": resource_val}
            return self._build_result(
                clean, ResearchIntent.COMPLEXITY, [concept], "complexity_pattern",
                constraints=constraints,
                synonyms=[concept, "running time", "complexity", "big-O", "theta", "worst-case", "bound"]
            )

        # 3. COMPARISON
        # "Compare merge sort and quicksort", "Difference between BFS and DFS", "merge sort vs quicksort"
        m_cmp = (
            re.search(r"\bcompare\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40})\s+(?:and|with|versus|vs\.?)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40})\??$", lower)
            or re.search(r"\bdifferences?\s+between\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40})\s+and\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40})\??$", lower)
            or re.search(r"^([a-z0-9\s-]{2,40})\s+vs\.?\s+([a-z0-9\s-]{2,40})\??$", lower)
        )
        if m_cmp:
            c1 = self._clean_concept(m_cmp.group(1))
            c2 = self._clean_concept(m_cmp.group(2))
            return self._build_result(
                clean, ResearchIntent.COMPARISON, [c1, c2], "comparison_pattern",
                synonyms=[c1, c2, "comparison", "difference", "versus"]
            )

        # 4. PROCEDURE
        # "Explain how binary search works", "How does quicksort partition work?", "Steps of Dijkstra's algorithm"
        m_proc = (
            re.search(r"\bexplain\s+how\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60}?)\s+(?:works?|operates?)\??$", lower)
            or re.search(r"\bhow\s+(?:does|to)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60}?)\s+(?:work|build|partition|operate)\b", lower)
            or re.search(r"\bsteps\s+(?:of|for|to)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bprocedure\s+(?:of|for|to)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\balgorithm\s+for\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_proc:
            concept = self._clean_concept(m_proc.group(1))
            return self._build_result(
                clean, ResearchIntent.PROCEDURE, [concept], "procedure_pattern",
                synonyms=[concept, "procedure", "steps", "algorithm", "pseudocode"]
            )

        # 5. LIST_PROPERTIES
        # "List the properties of an algorithm", "Characteristics of a greedy choice"
        m_list = re.search(r"\b(?:list|what\s+are)\s+(?:the\s+)?(?:essential\s+)?(?:properties|characteristics|features|components|operations|elements)\s+(?:of|supported\s+by|in)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        if m_list:
            concept = self._clean_concept(m_list.group(1))
            syns = [concept, "properties", "characteristics", "criteria"]
            if concept in ("algorithm", "algorithms"):
                syns.extend(["criteria", "finiteness", "definiteness", "effectiveness", "input", "output"])
            return self._build_result(
                clean, ResearchIntent.LIST_PROPERTIES, [concept], "list_properties_pattern",
                synonyms=syns
            )

        # 6. LOCATE
        # "Where is dynamic programming discussed?", "Which chapter covers graph algorithms?"
        m_loc = (
            re.search(r"\bwhere\s+is\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\s+(?:discussed|covered|found|introduced|located)\??$", lower)
            or re.search(r"\bwhich\s+chapter\s+(?:covers?|discusses?)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        )
        if m_loc:
            concept = self._clean_concept(m_loc.group(1))
            return self._build_result(
                clean, ResearchIntent.LOCATE, [concept], "locate_pattern",
                synonyms=[concept, "chapter", "section", "overview"]
            )

        # 7. THEOREM_LOOKUP
        m_thm = re.search(r"\b(master\s+theorem|theorem\s+[0-9.]+|theorem|lemma\s+[0-9.]+|corollary\s+[0-9.]+|lower\s+bound\s+theorem|cook'?s\s+theorem|max-flow\s+min-cut|loop\s+invariant)\b", lower)
        if m_thm:
            concept = self._clean_concept(m_thm.group(1))
            return self._build_result(
                clean, ResearchIntent.THEOREM_LOOKUP, [concept], "theorem_lookup_pattern",
                synonyms=[concept, "theorem", "proof", "recurrence", "cases"]
            )

        # 8. EXAMPLE
        m_ex = re.search(r"\b(?:give\s+an?|show\s+an?|provide\s+an?)?\s*(?:examples?|applications?)\s+(?:of|where)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        if m_ex:
            concept = self._clean_concept(m_ex.group(1))
            return self._build_result(
                clean, ResearchIntent.EXAMPLE, [concept], "example_pattern",
                synonyms=[concept, "example", "instance", "illustration"]
            )

        # 9. COUNT_RANKING
        if re.search(r"\bwhich\s+section\b.{0,30}\b(?:most|more|highest|largest|least|fewest)\b", lower) or re.search(r"\brank\s+sections?\b", lower):
            return self._build_result(
                clean, ResearchIntent.COUNT_RANKING, ["sections"], "count_ranking_pattern",
                synonyms=["section", "topics", "syllabus", "coverage"]
            )

        # 10. EVIDENCE_VERIFICATION
        m_ver = re.search(r"\b(?:does\s+the\s+text\s+state|is\s+it\s+true\s+that|verify\s+whether|check\s+whether)\s+(.*)\??$", lower)
        if m_ver:
            claim = m_ver.group(1).strip()
            terms = [w for w in re.findall(r"\b[a-z]{3,}\b", claim) if w not in self.STOPWORDS]
            return self._build_result(
                clean, ResearchIntent.EVIDENCE_VERIFICATION, terms[:2], "evidence_verification_pattern",
                constraints={"claim": claim},
                synonyms=terms[:5]
            )

        # 11. SUMMARIZATION
        m_sum = re.search(r"\b(?:summarize|summary\s+of|overview\s+of)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        if m_sum:
            concept = self._clean_concept(m_sum.group(1))
            return self._build_result(
                clean, ResearchIntent.SUMMARIZATION, [concept], "summarization_pattern",
                synonyms=[concept, "summary", "overview", "main topics"]
            )

        # 12. RELATIONSHIP
        m_rel = re.search(r"\b(?:relationship\s+between|how\s+is\s+([a-z0-9\s-]{2,40})\s+related\s+to)\s+([a-z0-9\s-]{2,40})", lower)
        if m_rel:
            c1 = self._clean_concept(m_rel.group(1) or "")
            c2 = self._clean_concept(m_rel.group(2) or "")
            concepts = [c for c in [c1, c2] if c]
            return self._build_result(
                clean, ResearchIntent.RELATIONSHIP, concepts, "relationship_pattern",
                synonyms=concepts + ["relationship", "connection", "similar"]
            )

        # 13. EXPLANATION (General)
        m_exp = re.search(r"\b(?:explain|describe|why\s+is|what\s+does)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
        if m_exp:
            concept = self._clean_concept(m_exp.group(1))
            return self._build_result(
                clean, ResearchIntent.EXPLANATION, [concept], "explanation_pattern",
                synonyms=self._concept_synonyms(concept) + ["explanation", "details"]
            )

        # Fallback OTHER
        terms = [w for w in re.findall(r"\b[a-z]{3,}\b", lower) if w not in self.STOPWORDS]
        return self._build_result(
            clean, ResearchIntent.OTHER, terms[:2], "fallback",
            synonyms=terms[:5]
        )

    @classmethod
    def _clean_concept(cls, raw: Optional[str]) -> str:
        if not raw:
            return ""
        s = raw.strip().lower()
        s = re.sub(r"^(?:an?|the)\s+", "", s)
        s = re.sub(r"\s+(?:in\s+computer\s+science|in\s+algorithms)$", "", s)
        return s.strip()

    @classmethod
    def _concept_synonyms(cls, concept: str) -> List[str]:
        concept_clean = concept.strip().lower()
        if concept_clean in cls.CONCEPT_ALIASES:
            return cls.CONCEPT_ALIASES[concept_clean]
        for key, aliases in cls.CONCEPT_ALIASES.items():
            if key in concept_clean:
                return [concept_clean] + [a for a in aliases if a != concept_clean]
        if "sort" in concept_clean:
            return [concept_clean, "sorting", "order", "reordering"]
        return [concept_clean]

    def _build_result(
        self,
        raw_query: str,
        intent: ResearchIntent,
        concepts: List[str],
        rule_name: str,
        constraints: Optional[Dict[str, Any]] = None,
        synonyms: Optional[List[str]] = None,
    ) -> QueryUnderstanding:
        cleaned_concepts = [self._clean_concept(c) for c in concepts if c]
        primary = cleaned_concepts[0] if cleaned_concepts else None
        secondary = cleaned_concepts[1] if len(cleaned_concepts) > 1 else None
        priors = dict(DEFAULT_SECTION_PRIORS.get(intent, DEFAULT_SECTION_PRIORS[ResearchIntent.OTHER]))

        search_terms = list(dict.fromkeys(cleaned_concepts + (synonyms or [])))

        merged_constraints = dict(constraints or {})
        current_fmt = getattr(self, "_current_output_format", None)
        if current_fmt and "output_format" not in merged_constraints:
            merged_constraints["output_format"] = current_fmt

        current_raw = getattr(self, "_current_raw_query", None) or raw_query

        # If format is compare and intent not comparison, promote to comparison
        effective_intent = intent
        if current_fmt == "compare" and intent != ResearchIntent.COMPARISON:
            effective_intent = ResearchIntent.COMPARISON
        elif current_fmt == "summary" and intent == ResearchIntent.OTHER:
            effective_intent = ResearchIntent.SUMMARIZATION

        return QueryUnderstanding(
            raw_query=current_raw,
            normalized_query=current_raw.strip(),
            intent=effective_intent,
            target_concepts=cleaned_concepts,
            primary_concept=primary,
            secondary_concept=secondary,
            query_constraints=merged_constraints,
            section_priors=priors,
            expanded_search_terms=search_terms,
            matched_rule=rule_name,
        )

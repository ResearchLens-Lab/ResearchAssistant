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
class QueryFacet:
    facet_id: str  # e.g. "definition", "criteria", "strategies", "explanation", "comparison", "complexity"
    facet_title: str
    intent: ResearchIntent
    primary_concept: str
    target_concepts: List[str] = field(default_factory=list)
    search_phrases: List[str] = field(default_factory=list)
    required: bool = True
    section_priors: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facet_id": self.facet_id,
            "facet_title": self.facet_title,
            "intent": self.intent.value,
            "primary_concept": self.primary_concept,
            "target_concepts": self.target_concepts,
            "search_phrases": self.search_phrases,
            "required": self.required,
            "section_priors": self.section_priors,
        }


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
    is_compound: bool = False
    facets: List[QueryFacet] = field(default_factory=list)

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
            "is_compound": self.is_compound,
            "facets": [f.to_dict() for f in self.facets],
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


def strip_query_prefixes(raw: str) -> str:
    r"""Strip question / prompt framing prefixes so primary concept does not become empty."""
    s = raw.strip()
    s = re.sub(
        r"^(?:what\s+is\s+(?:an?|the)?|what\s+are\s+(?:the)?|explain\s+(?:the|an?)?|define\s+(?:the|an?)?|describe\s+(?:the|an?)?|tell\s+me\s+about\s+(?:the|an?)?)\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"[\?\.\!]+$", "", s).strip()
    return s


class QueryAnalyzer:
    """Classifies user research questions into structured intents and extracts target slots."""

    STOPWORDS = frozenset({
        "a", "about", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
        "was", "what", "when", "where", "which", "who", "why", "will", "with",
        "tell", "me", "show", "give", "explain", "describe", "discuss",
        "you", "mean", "meant", "please", "us", "your",
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
        "np-completeness": ["np-completeness", "np-complete", "np complete", "polynomial-time reduction"],
        "np-complete": ["np-complete", "np-completeness", "np complete", "polynomial-time reduction"],
        "approximation algorithm": ["approximation algorithm", "approximation algorithms", "ratio bound", "approximation ratio"],
        "approximation algorithms": ["approximation algorithms", "approximation algorithm", "ratio bound", "approximation ratio"],
        "backtracking": ["backtracking", "state space tree", "bounding function"],
        "branch-and-bound": ["branch-and-bound", "branch and bound", "lc search", "fifo search"],
        "branch and bound": ["branch and bound", "branch-and-bound", "lc search", "fifo search"],
        "randomized algorithm": ["randomized algorithm", "randomized algorithms", "probability", "las vegas"],
        "randomized algorithms": ["randomized algorithms", "randomized algorithm", "probability", "las vegas"],
        "greedy algorithm": ["greedy algorithm", "greedy method", "greedy strategy"],
        "greedy algorithms": ["greedy algorithms", "greedy algorithm", "greedy method", "greedy strategy"],
    }

    def _resolve_conversational_query(self, query: str, context: Optional[str]) -> str:
        """Resolves conversational pronouns, ordinals ('the second one'), and suggestion chips using conversation history."""
        if not context or not context.strip():
            return query

        clean = query.strip()
        lower = clean.casefold()

        # Independent conceptual query guard:
        # Questions asking for fundamental definitions or concepts (e.g. "what do you mean by algorithm",
        # "what is an algorithm", "define algorithm") are standalone questions and must NEVER be
        # modified, rewritten, or contaminated by prior turns in the conversation.
        if re.search(r"^\s*(?:what\s+(?:is|do\s+you\s+mean\s+by)|define|definition\s+of|meaning\s+of|explain\s+(?:an?\s+)?algorithm)\b", lower):
            return query

        # Parse recent assistant and user turns from context
        lines = [line.strip() for line in context.splitlines() if line.strip()]
        last_user_turn = ""
        last_assistant_turn = ""
        for line in lines:
            if line.lower().startswith("user:"):
                last_user_turn = line[5:].strip()
            elif line.lower().startswith("assistant:"):
                last_assistant_turn = line[10:].strip()

        # Extract numbered items / paradigms / concepts from assistant turn
        extracted_items: List[str] = []
        for line in lines:
            m = re.match(r"^(?:assistant:\s*)?(?:###?\s*)?(?:\d+[\.\)]|\-|\*)\s+\*?\*?([A-Za-z0-9\s\-]+?)\*?\*?(?:\:\s*|\s+[-–—]\s+|\s*\(|\n|$)", line)
            if m:
                cand = m.group(1).strip()
                if len(cand) > 2 and cand.lower() not in ("note", "source", "chapter", "part"):
                    extracted_items.append(cand)

        # Fallback list of canonical algorithmic paradigms if present in context
        canonical_paradigms = [
            "Divide-and-Conquer",
            "Greedy Method",
            "Dynamic Programming",
            "Backtracking",
            "Branch-and-Bound",
            "Randomized Algorithms",
            "Approximation Algorithms",
        ]
        if not extracted_items:
            for cp in canonical_paradigms:
                if cp.lower() in context.lower():
                    extracted_items.append(cp)

        # Determine prior primary topic
        prior_topic = ""
        if last_user_turn:
            m_topic = re.search(r"\b(?:what\s+is|explain|describe|define)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40})", last_user_turn.lower())
            if m_topic:
                prior_topic = m_topic.group(1).strip()

        # 1. Resolve Ordinal Queries: "Explain the second one in detail", "what is the 2nd strategy"
        ordinals = {
            "first": 0, "1st": 0,
            "second": 1, "2nd": 1,
            "third": 2, "3rd": 2,
            "fourth": 3, "4th": 3,
            "fifth": 4, "5th": 4,
            "sixth": 5, "6th": 5,
            "seventh": 6, "7th": 6,
            "last": -1,
        }
        ord_pattern = r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|last)\s*(?:one|strategy|paradigm|method|approach|technique|algorithm|category)?\b"
        m_ord = re.search(ord_pattern, lower)
        if m_ord:
            ord_word = m_ord.group(1).lower()
            idx = ordinals.get(ord_word, 0)
            target_item = None
            if extracted_items:
                if idx == -1:
                    target_item = extracted_items[-1]
                elif 0 <= idx < len(extracted_items):
                    target_item = extracted_items[idx]
            if not target_item and 0 <= idx < len(canonical_paradigms):
                target_item = canonical_paradigms[idx]

            if target_item:
                # Rewrite conversational prompt into a clean, standalone, evidence-grounded research query
                # rather than performing naive token replacement that leaves trailing or malformed fragments.
                return f"Explain the {target_item} strategy in detail"

        # 2. Resolve Suggestion Chips
        chips_map = {
            "explain in more depth": f"Explain {prior_topic or 'the concept'} in more depth and detail",
            "give a practical example": f"Give a practical textbook example of {prior_topic or 'the concept'}",
            "explain in simple language": f"Explain {prior_topic or 'the concept'} in simple language",
            "what are the reported limitations?": f"What are the reported limitations and constraints of {prior_topic or 'the concept'}?",
            "what are the reported limitations": f"What are the reported limitations and constraints of {prior_topic or 'the concept'}?",
            "compare with related methods": f"Compare {prior_topic or 'the concept'} with related methods and design strategies",
        }
        if lower in chips_map:
            return chips_map[lower]

        # 3. Resolve Pronoun "it" / "this" with comparison or explanation
        if re.search(r"\b(?:it|this|that)\b", lower):
            target_subj = extracted_items[0] if extracted_items else prior_topic
            if target_subj:
                resolved = re.sub(r"\b(?:it|this|that)\b", target_subj, clean, flags=re.I)
                return resolved

        return clean

    def analyze(self, query: str, conversation_context: Optional[str] = None) -> QueryUnderstanding:
        clean = unicodedata.normalize("NFKC", query).strip()

        if conversation_context:
            clean = self._resolve_conversational_query(clean, conversation_context)

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

        # 0. COMPOUND MULTI-FACET QUERY RULE (e.g., "What is an algorithm and explain its different strategies")
        is_compound_def_strat = bool(
            re.search(r"\b(?:what\s+is|define|definition\s+of)\s+.*?\band\b.*?\b(?:strategies|strategy|types|kinds|categories|paradigms|methods|approaches|characteristics|criteria|properties)\b", lower)
            or re.search(r"\b(?:what\s+is|define)\s+(?:\b(?:an?|the)\b\s*)?algorithm\b.*?\b(?:strategies|strategy|paradigms|techniques|types|classes)\b", lower)
        )
        if is_compound_def_strat:
            concept = "algorithm"
            paradigms = [
                "divide and conquer",
                "greedy method",
                "dynamic programming",
                "backtracking",
                "branch and bound",
                "randomized algorithms",
                "approximation algorithms",
            ]
            inferred_compound, inferred_facets = self._infer_default_facets(
                ResearchIntent.CLASSIFICATION, concept, "strategies", [concept, "strategies"], clean
            )
            return self._build_result(
                clean,
                ResearchIntent.CLASSIFICATION,
                [concept, "strategies"],
                "compound_definition_and_strategy_pattern",
                constraints={"taxonomy": "algorithmic_paradigms", "multi_facet": True, "compound_type": "def_strat"},
                synonyms=[concept, "computational procedure", *paradigms],
                facets=inferred_facets,
                is_compound=True,
            )

        # 0.2 COMPOUND CONCEPT + EXAMPLE (e.g., "What is dynamic programming and give an example")
        m_compound_ex = re.search(r"\b(?:what\s+is|explain|describe|define)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40}?)\s+\band\b\s+(?:give\s+(?:an?\s+)?example|provide\s+(?:an?\s+)?example|examples?)\b", lower)
        if m_compound_ex:
            concept = self._clean_concept(m_compound_ex.group(1))
            f_expl = QueryFacet(
                facet_id="explanation",
                facet_title=f"Definition & Core Principle of {concept.title()}",
                intent=ResearchIntent.EXPLANATION,
                primary_concept=concept,
                target_concepts=[concept],
                search_phrases=[f'"{concept}"', f'"{concept} is"', f'"{concept} solves"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            f_exam = QueryFacet(
                facet_id="example",
                facet_title=f"Textbook Example of {concept.title()}",
                intent=ResearchIntent.EXAMPLE,
                primary_concept=concept,
                target_concepts=[concept, "example"],
                search_phrases=[f'"{concept}" AND "example"', f'"{concept}" AND "instance"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXAMPLE],
            )
            return self._build_result(
                clean,
                ResearchIntent.EXAMPLE,
                [concept, "example"],
                "compound_concept_and_example_pattern",
                constraints={"multi_facet": True, "compound_type": "concept_example"},
                synonyms=self._concept_synonyms(concept) + ["example", "instance"],
                facets=[f_expl, f_exam],
                is_compound=True,
            )

        # 0.3 COMPOUND CONCEPT + COMPLEXITY (e.g., "Explain merge sort and its time complexity")
        m_compound_comp = re.search(
            r"\b(?:what\s+is|explain|describe|define)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40}?)\s+\band\b\s+(?:its\s+)?(?:time\s+complexity|space\s+complexity|complexity|running\s+time)\b",
            lower
        )
        if m_compound_comp:
            concept = self._clean_concept(m_compound_comp.group(1))
            f_expl = QueryFacet(
                facet_id="explanation",
                facet_title=f"Core Concept of {concept.title()}",
                intent=ResearchIntent.EXPLANATION,
                primary_concept=concept,
                target_concepts=[concept],
                search_phrases=[f'"{concept}"', f'"{concept} is"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            f_comp = QueryFacet(
                facet_id="complexity",
                facet_title=f"Asymptotic Complexity of {concept.title()}",
                intent=ResearchIntent.COMPLEXITY,
                primary_concept=concept,
                target_concepts=[concept, "complexity"],
                search_phrases=[
                    f'"{concept}" AND "O("',
                    f'"{concept}" AND "running time"',
                    f'"{concept}" AND "time complexity"',
                    f'"{concept}" AND "worst-case"',
                    f'"{concept}" AND "theta("',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.COMPLEXITY],
            )
            return self._build_result(
                clean,
                ResearchIntent.COMPLEXITY,
                [concept, "complexity"],
                "compound_concept_and_complexity_pattern",
                constraints={"multi_facet": True, "compound_type": "concept_complexity"},
                synonyms=self._concept_synonyms(concept) + ["complexity", "running time"],
                facets=[f_expl, f_comp],
                is_compound=True,
            )

        # 0.4 COMPOUND CONCEPT + PROCEDURE / HOW IT WORKS / STEPS / BOUNDS
        m_compound_proc = re.search(
            r"\b(?:what\s+is|explain|describe|define)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,40}?)\s+\band\b\s+(?:how\s+(?:does\s+it\s+work|it\s+works|is\s+it\s+used|it\s+is\s+used)|explain\s+its\s+steps|its\s+steps|how\s+to\s+use\s+it|their\s+ratio\s+bounds)\b",
            lower
        )
        if m_compound_proc:
            concept = self._clean_concept(m_compound_proc.group(1))
            f_expl = QueryFacet(
                facet_id="explanation",
                facet_title=f"Foundational Definition of {concept.title()}",
                intent=ResearchIntent.EXPLANATION,
                primary_concept=concept,
                target_concepts=[concept],
                search_phrases=[f'"{concept}"', f'"{concept} is"', f'"{concept} solves"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            f_proc = QueryFacet(
                facet_id="procedure",
                facet_title=f"Operation, Methodology & Steps of {concept.title()}",
                intent=ResearchIntent.PROCEDURE,
                primary_concept=concept,
                target_concepts=[concept, "steps"],
                search_phrases=[
                    f'"{concept}" AND "step"',
                    f'"{concept}" AND "method"',
                    f'"{concept}" AND "algorithm"',
                    f'"{concept}"',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.PROCEDURE],
            )
            return self._build_result(
                clean,
                ResearchIntent.PROCEDURE,
                [concept, "steps"],
                "compound_concept_and_procedure_pattern",
                constraints={"multi_facet": True, "compound_type": "concept_procedure"},
                synonyms=self._concept_synonyms(concept) + ["steps", "methodology"],
                facets=[f_expl, f_proc],
                is_compound=True,
            )

        # 0.5 CROSS-DOCUMENT COMPARISON ("How do Cormen and Horowitz approach dynamic programming?")
        m_cross_doc = re.search(
            r"\b(?:how\s+do\s+)?(cormen|horowitz)\s+and\s+(cormen|horowitz)\s+(?:approach|treat|define|explain|present)\s+([a-z0-9\s-]{2,40})\b",
            lower
        )
        if m_cross_doc:
            concept = self._clean_concept(m_cross_doc.group(3))
            f_cormen = QueryFacet(
                facet_id="cormen_view",
                facet_title=f"Cormen formulation of {concept.title()}",
                intent=ResearchIntent.EXPLANATION,
                primary_concept=concept,
                target_concepts=[concept],
                search_phrases=[f'"{concept}"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            f_horowitz = QueryFacet(
                facet_id="horowitz_view",
                facet_title=f"Horowitz formulation of {concept.title()}",
                intent=ResearchIntent.EXPLANATION,
                primary_concept=concept,
                target_concepts=[concept],
                search_phrases=[f'"{concept}"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            return self._build_result(
                clean,
                ResearchIntent.COMPARISON,
                ["Cormen", "Horowitz", concept],
                "cross_textbook_comparison_pattern",
                constraints={"multi_facet": True, "compound_type": "cross_doc", "subject": concept},
                synonyms=[concept, "Cormen", "Horowitz"],
                facets=[f_cormen, f_horowitz],
                is_compound=True,
            )

        # 1. DEFINITION
        # "What is an algorithm?", "Define merge sort", "What is meant by dynamic programming?"
        # SEC-N21: Guard optional article with word boundary \b(?:an?|the)\b to prevent stripping first letter of concepts
        m_def = (
            re.search(r"^\s*what\s+do\s+you\s+mean\s+by\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bwhat\s+is\s+meant\s+by\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bmeaning\s+of\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"^\s*what\s+is\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60}?)(?:\s+in\s+computer\s+science|\s+in\s+algorithms)?\??$", lower)
            or re.search(r"^\s*define\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\bdefinition\s+of\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
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
        m_exp = (
            re.search(r"\b(?:explain(?:\s+to\s+me|\s+me)?|describe|tell\s+me\s+about|show\s+me|give\s+me|why\s+is|what\s+does)\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$", lower)
            or re.search(r"\b(?:tell\s+me|explain)\s+(?:the\s+)?([a-z0-9\s-]{2,60})\??$", lower)
        )
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
        # Clean leading conversational imperatives, pronouns, and politeness markers
        s = re.sub(r"^(?:(?:tell|show|explain(?:\s+to)?|give|describe|discuss|detail)\s+)?(?:me|us|please|you)\s+(?:about\s+|the\s+|an?\s+)?", "", s)
        s = re.sub(r"^(?:to\s+me|me\s+the|me\s+about|me|us|you\s+mean\s+by|mean\s+by)\s+", "", s)
        s = re.sub(r"^(?:an?|the)\s+", "", s)
        s = re.sub(r"\s+(?:in\s+computer\s+science|in\s+algorithms)$", "", s)
        s = re.sub(r"\s+(?:in\s+(?:detail|more\s+detail|depth|more\s+depth|simple\s+terms|simple\s+language|plain\s+english)|step\s+by\s+step|with\s+(?:an?\s+)?examples?)$", "", s)
        s = re.sub(r"\s+(?:algorithm(?:ic)?\s+design\s+strategy|design\s+strategy|strategy|paradigm)$", "", s)
        s = re.sub(r"\s+(?:in\s+(?:detail|more\s+detail|depth|more\s+depth|simple\s+terms|simple\s+language|plain\s+english)|step\s+by\s+step|with\s+(?:an?\s+)?examples?)$", "", s)
        s = re.sub(r"\s+and\s+(?:how\s+(?:does\s+it\s+work|it\s+works|is\s+it\s+used|it\s+is\s+used)|its\s+steps|explain\s+its\s+steps|how\s+to\s+use\s+it|their\s+ratio\s+bounds)$", "", s)
        s = re.sub(r"[\?\.\!]+$", "", s)
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

    def _infer_default_facets(
        self,
        intent: ResearchIntent,
        primary_concept: Optional[str],
        secondary_concept: Optional[str],
        target_concepts: List[str],
        raw_query: str,
    ) -> Tuple[bool, List[QueryFacet]]:
        lower = raw_query.casefold()
        pc = (primary_concept or "").strip().lower()

        # Check for compound definition + strategies / types / characteristics
        if ("what is" in lower or "define" in lower or "definition" in lower) and any(w in lower for w in ["strategies", "strategy", "types", "paradigms", "classes", "categories", "characteristics", "criteria"]):
            f_def = QueryFacet(
                facet_id="definition",
                facet_title="Definition & Meaning of Algorithm",
                intent=ResearchIntent.DEFINITION,
                primary_concept=pc or "algorithm",
                target_concepts=[pc or "algorithm", "computational procedure"],
                search_phrases=[
                    '"informally, an algorithm is"',
                    '"what is an algorithm"',
                    '"computational procedure"',
                    '"sequence of computational steps"',
                    '"algorithm is any well-defined"',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.DEFINITION],
            )
            f_crit = QueryFacet(
                facet_id="criteria",
                facet_title="Five Foundational Criteria & Characteristics (Horowitz §1.1)",
                intent=ResearchIntent.LIST_PROPERTIES,
                primary_concept=pc or "algorithm",
                target_concepts=["criteria", "finiteness", "definiteness", "input", "output", "effectiveness"],
                search_phrases=[
                    '"following criteria"',
                    '"definiteness" AND "finiteness"',
                    '"criteria 1 and 2 require"',
                    '"five criteria"',
                    '"input" AND "output" AND "finiteness"',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.LIST_PROPERTIES],
            )
            f_strat = QueryFacet(
                facet_id="strategies",
                facet_title="Algorithmic Design Strategies & Taxonomy",
                intent=ResearchIntent.CLASSIFICATION,
                primary_concept="algorithmic strategies",
                target_concepts=["divide and conquer", "greedy method", "dynamic programming", "backtracking", "branch and bound", "randomized algorithms", "approximation algorithms"],
                search_phrases=[
                    '"divide and conquer"',
                    '"greedy method" OR "greedy strategy" OR "greedy algorithm"',
                    '"dynamic programming"',
                    '"backtracking"',
                    '"branch and bound"',
                    '"randomized algorithm" OR "randomized algorithms"',
                    '"approximation algorithm" OR "approximation algorithms"',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.CLASSIFICATION],
            )
            f_exp = QueryFacet(
                facet_id="explanation",
                facet_title="Strategy Principles & Core Methods",
                intent=ResearchIntent.EXPLANATION,
                primary_concept="strategy principles",
                target_concepts=["divide and conquer", "greedy", "dynamic programming", "backtracking", "branch and bound"],
                search_phrases=[
                    '"divide-and-conquer strategy suggests"',
                    '"greedy method is perhaps the most"',
                    '"sequence of decisions" AND "dynamic programming"',
                    '"dynamic programming" AND "subproblems"',
                    '"state space" AND "backtracking"',
                    '"branch-and-bound refers to"',
                    '"techniques used in designing and analyzing"',
                ],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.EXPLANATION],
            )
            return True, [f_def, f_crit, f_strat, f_exp]

        # Single Definition
        if intent == ResearchIntent.DEFINITION and pc in ("algorithm", "algorithms"):
            f_def = QueryFacet(
                facet_id="definition",
                facet_title="Definition & Core Meaning",
                intent=ResearchIntent.DEFINITION,
                primary_concept=pc,
                target_concepts=[pc, "computational procedure"],
                search_phrases=['"algorithm is"', '"what is an algorithm"', '"computational procedure"', '"sequence of computational steps"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.DEFINITION],
            )
            f_crit = QueryFacet(
                facet_id="criteria",
                facet_title="Five Foundational Criteria (Horowitz §1.1)",
                intent=ResearchIntent.LIST_PROPERTIES,
                primary_concept=pc,
                target_concepts=["criteria", "finiteness", "definiteness", "input", "output", "effectiveness"],
                search_phrases=['"following criteria"', '"definiteness" AND "finiteness"', '"criteria 1 and 2"', '"input" AND "output" AND "finiteness"'],
                section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.LIST_PROPERTIES],
            )
            return False, [f_def, f_crit]

        # Taxonomy / Classification / Paradigms
        if intent == ResearchIntent.CLASSIFICATION or (pc in ("algorithm", "algorithms") and any(w in lower for w in ["types", "strategies", "paradigms", "classes", "categories"])):
            paradigms = [
                ("divide_and_conquer", "Divide-and-Conquer", ['"divide and conquer"']),
                ("greedy_method", "The Greedy Method", ['"greedy method" OR "greedy strategy" OR "greedy algorithm"']),
                ("dynamic_programming", "Dynamic Programming", ['"dynamic programming"']),
                ("backtracking", "Backtracking", ['"backtracking"']),
                ("branch_and_bound", "Branch-and-Bound", ['"branch and bound"']),
                ("randomized", "Randomized Algorithms", ['"randomized algorithm" OR "randomized algorithms"']),
                ("approximation", "Approximation Algorithms", ['"approximation algorithm" OR "approximation algorithms"']),
            ]
            facets = []
            for fid, ftitle, phrases in paradigms:
                facets.append(QueryFacet(
                    facet_id=fid,
                    facet_title=ftitle,
                    intent=ResearchIntent.CLASSIFICATION,
                    primary_concept=ftitle.lower(),
                    target_concepts=[ftitle.lower()],
                    search_phrases=phrases,
                    section_priors=DEFAULT_SECTION_PRIORS[ResearchIntent.CLASSIFICATION],
                ))
            return False, facets

        # Comparison
        if intent == ResearchIntent.COMPARISON and primary_concept and secondary_concept:
            f1 = QueryFacet(
                facet_id="concept_1",
                facet_title=primary_concept.title(),
                intent=ResearchIntent.EXPLANATION,
                primary_concept=primary_concept,
                target_concepts=[primary_concept],
                search_phrases=[f'"{primary_concept}"'],
            )
            f2 = QueryFacet(
                facet_id="concept_2",
                facet_title=secondary_concept.title(),
                intent=ResearchIntent.EXPLANATION,
                primary_concept=secondary_concept,
                target_concepts=[secondary_concept],
                search_phrases=[f'"{secondary_concept}"'],
            )
            f3 = QueryFacet(
                facet_id="comparison",
                facet_title=f"Comparison: {primary_concept} vs {secondary_concept}",
                intent=ResearchIntent.COMPARISON,
                primary_concept=f"{primary_concept} vs {secondary_concept}",
                target_concepts=[primary_concept, secondary_concept],
                search_phrases=[f'"{primary_concept}" AND "{secondary_concept}"'],
            )
            return True, [f1, f2, f3]

        # Default Single Facet
        default_facet = QueryFacet(
            facet_id="main",
            facet_title=primary_concept.title() if primary_concept else "Core Topic",
            intent=intent,
            primary_concept=primary_concept or "",
            target_concepts=target_concepts,
            search_phrases=[f'"{c}"' for c in target_concepts if len(c) > 2],
            section_priors=DEFAULT_SECTION_PRIORS.get(intent, DEFAULT_SECTION_PRIORS[ResearchIntent.OTHER]),
        )
        return False, [default_facet]

    def _build_result(
        self,
        raw_query: str,
        intent: ResearchIntent,
        concepts: List[str],
        rule_name: str,
        constraints: Optional[Dict[str, Any]] = None,
        synonyms: Optional[List[str]] = None,
        facets: Optional[List[QueryFacet]] = None,
        is_compound: Optional[bool] = None,
    ) -> QueryUnderstanding:
        cleaned_concepts = [self._clean_concept(c) for c in concepts if c]
        primary = cleaned_concepts[0] if cleaned_concepts else None
        current_raw = getattr(self, "_current_raw_query", None) or raw_query

        # Fallback if primary concept is missing or empty
        if not primary or not primary.strip():
            fallback_c = strip_query_prefixes(current_raw)
            if fallback_c:
                primary = fallback_c
                if not cleaned_concepts:
                    cleaned_concepts = [fallback_c]

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

        if facets is None:
            inferred_compound, inferred_facets = self._infer_default_facets(
                effective_intent, primary, secondary, cleaned_concepts, current_raw
            )
            final_compound = is_compound if is_compound is not None else inferred_compound
            final_facets = inferred_facets
        else:
            final_compound = is_compound if is_compound is not None else (len(facets) > 1)
            final_facets = facets

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
            is_compound=final_compound,
            facets=final_facets,
        )

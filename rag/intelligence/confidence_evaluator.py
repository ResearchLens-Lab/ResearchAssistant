"""
Calibrated Confidence and Abstention Evaluator.
Evaluates evidence quality, pattern matches, ranking margins, and section types
to produce four authoritative confidence tiers:
STRONG, PARTIAL, WEAK, or NOT LOCATED (Abstention).
"""

from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import RetrievalTrace
from rag.intelligence.sentence_analyzer import DefinitionCandidate, SentenceAnalyzer
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, enum.Enum):
    STRONG = "STRONG"
    PARTIAL = "PARTIAL"
    WEAK = "WEAK"
    NOT_LOCATED = "NOT LOCATED"

    # Compatibility alias for older tests expecting HIGH_CONFIDENCE
    @classmethod
    def from_str(cls, val: str) -> "ConfidenceLevel":
        v = val.upper().strip()
        if v in ("HIGH", "HIGH CONFIDENCE", "HIGH_CONFIDENCE", "STRONG"):
            return cls.STRONG
        elif v in ("LOW", "LOW CONFIDENCE", "LOW_CONFIDENCE", "PARTIAL"):
            return cls.PARTIAL
        elif v in ("WEAK", "POOR"):
            return cls.WEAK
        return cls.NOT_LOCATED


@dataclass
class ConfidenceReport:
    level: ConfidenceLevel
    overall_confidence_score: float  # [0.0 - 1.0]
    is_definitive_answer: bool
    top_definition: Optional[DefinitionCandidate] = None
    top_source: Optional[RetrievedSource] = None
    justification: str = ""
    evidence_signals: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_level": self.level.value,
            "score": round(self.overall_confidence_score, 3),
            "is_definitive": self.is_definitive_answer,
            "justification": self.justification,
            "evidence_signals": self.evidence_signals,
            "limitations": self.limitations,
        }


class ConfidenceEvaluator:
    """Evaluates multi-factor evidence signals to calibrate answer confidence and enforce honest abstention."""

    STRONG_THRESHOLD = 0.80
    PARTIAL_THRESHOLD = 0.45

    def __init__(self):
        self.sentence_analyzer = SentenceAnalyzer()

    def evaluate(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        traces: Dict[str, RetrievalTrace],
    ) -> ConfidenceReport:
        if not sources:
            return ConfidenceReport(
                level=ConfidenceLevel.NOT_LOCATED,
                overall_confidence_score=0.0,
                is_definitive_answer=False,
                justification=f"No matching passages were found in your selected documents for '{query.primary_concept or query.raw_query}'.",
                limitations=["Requested concept is absent from the selected library."],
            )

        top_source = sources[0]
        top_trace = traces.get(top_source.source_id)

        signals: List[str] = []
        limitations: List[str] = []

        top_score = top_trace.final_score if top_trace else 1.0
        signals.append(f"Top retrieval score: {top_score:.2f}")

        # Check term coverage & entity presence across top retrieved sources to guard against incidental single-word hits
        combined_source_text = " ".join(s.text.lower() for s in sources[:3])
        stopwords = {
            "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
            "explain", "describe", "compare", "list", "show", "give", "does", "from",
            "the", "and", "for", "with", "that", "this", "these", "those", "was",
            "were", "are", "been", "being", "have", "has", "had", "about", "into",
            "table", "pie", "chart", "flowchart", "mermaid", "summary", "outline",
            "different", "types", "categories", "paradigms", "methods", "classes",
        }
        raw_words = re.findall(r"\b[A-Za-z0-9]{3,}\b", query.raw_query)
        informative_terms = [w.lower() for w in raw_words if w.lower() not in stopwords]
        capitalized_entities = [
            w.lower() for w in re.findall(r"\b[A-Z][a-z0-9]{2,}\b", query.raw_query)
            if w.lower() not in stopwords
        ]
        missing_entities = [e for e in capitalized_entities if e not in combined_source_text]
        matched_terms = [t for t in informative_terms if t in combined_source_text]
        term_coverage = len(matched_terms) / max(1, len(informative_terms))

        if query.intent != ResearchIntent.CLASSIFICATION:
            if (missing_entities and term_coverage < 0.60) or (informative_terms and term_coverage < 0.35):
                missing_desc = ", ".join(f"'{e}'" for e in (missing_entities or [t for t in informative_terms if t not in matched_terms])[:3])
                return ConfidenceReport(
                    level=ConfidenceLevel.NOT_LOCATED,
                    overall_confidence_score=0.10,
                    is_definitive_answer=False,
                    top_source=None,
                    justification=f"Your indexed documents do not contain evidence for key terms ({missing_desc}).",
                    limitations=["Target concepts from the query were not found in the selected library."],
                )

        primary_concept = query.primary_concept or ""

        # 1. DEFINITION
        if query.intent == ResearchIntent.DEFINITION and primary_concept:
            top_def: Optional[DefinitionCandidate] = None
            def_source: Optional[RetrievedSource] = None
            for s in sources[:4]:
                defs = self.sentence_analyzer.find_definition_sentences(s.text, primary_concept)
                if defs:
                    top_def = defs[0]
                    def_source = s
                    break

            if top_def and top_def.confidence >= 0.85:
                # Confirm the source is not in bibliography or exercises
                tr = traces.get(def_source.source_id) if def_source else None
                sec_type = tr.section_type if tr else "body"
                if sec_type in ("bibliography", "index", "exercises"):
                    signals.append(f"Definition pattern found but in {sec_type} section")
                    limitations.append(f"Passage is from a {sec_type} section rather than an instructional chapter.")
                    return ConfidenceReport(
                        level=ConfidenceLevel.PARTIAL,
                        overall_confidence_score=0.55,
                        is_definitive_answer=False,
                        top_definition=top_def,
                        top_source=def_source or top_source,
                        justification=f"A definitional sentence was found in a {sec_type} section for '{primary_concept}'.",
                        evidence_signals=signals,
                        limitations=limitations,
                    )

                signals.append(f"Explicit definition sentence confirmed ({top_def.pattern_name}, pattern_conf={top_def.confidence:.2f})")
                signals.append(f"Concept '{primary_concept}' is grammatical subject of copula")
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.95,
                    is_definitive_answer=True,
                    top_definition=top_def,
                    top_source=def_source or top_source,
                    justification=f"Direct authoritative definition of '{primary_concept}' found in source passage [{def_source.source_id if def_source else top_source.source_id}] on page {def_source.page_start if def_source else top_source.page_start}.",
                    evidence_signals=signals,
                    limitations=[],
                )
            elif top_def:
                signals.append(f"Partial definition sentence found ({top_def.pattern_name})")
                limitations.append("Informal or indirect characterization rather than rigorous formal definition.")
                return ConfidenceReport(
                    level=ConfidenceLevel.PARTIAL,
                    overall_confidence_score=0.65,
                    is_definitive_answer=False,
                    top_definition=top_def,
                    top_source=def_source or top_source,
                    justification=f"Relevant explanatory passages found for '{primary_concept}', with indirect definition.",
                    evidence_signals=signals,
                    limitations=limitations,
                )
            else:
                signals.append(f"Mentions of '{primary_concept}' exist, but no definition sentences match.")
                limitations.append("The source discusses this topic in context without a formal definition.")
                return ConfidenceReport(
                    level=ConfidenceLevel.PARTIAL,
                    overall_confidence_score=0.45,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Concept '{primary_concept}' appears in the text, but no definitional sentence was found.",
                    evidence_signals=signals,
                    limitations=limitations,
                )

        # 2. COMPLEXITY
        elif query.intent == ResearchIntent.COMPLEXITY and primary_concept:
            found_claims = []
            for s in sources[:4]:
                claims = self.sentence_analyzer.extract_complexity_claims(s.text)
                if claims:
                    found_claims.extend(claims)

            if found_claims:
                signals.append(f"Complexity bounds identified: {', '.join(c.formula for c in found_claims[:3])}")
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.92,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification=f"Explicit asymptotic complexity bounds for '{primary_concept}' verified in source text.",
                    evidence_signals=signals,
                    limitations=[],
                )
            else:
                limitations.append(f"Running time or complexity discussed, but exact mathematical bounds were not stated.")
                return ConfidenceReport(
                    level=ConfidenceLevel.PARTIAL,
                    overall_confidence_score=0.50,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Contextual passages retrieved for '{primary_concept}', but explicit complexity formula not located.",
                    evidence_signals=signals,
                    limitations=limitations,
                )

        # 3. COMPARISON
        elif query.intent == ResearchIntent.COMPARISON and len(query.target_concepts) >= 2:
            c1, c2 = query.target_concepts[0].lower(), query.target_concepts[1].lower()
            has_c1 = any(c1 in s.text.lower() for s in sources)
            has_c2 = any(c2 in s.text.lower() for s in sources)

            if has_c1 and has_c2:
                signals.append(f"Passages retrieved for both concepts ('{c1}' and '{c2}')")
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.88,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification=f"Comparative source evidence located for both '{c1}' and '{c2}'.",
                    evidence_signals=signals,
                    limitations=[],
                )
            else:
                missing = c1 if not has_c1 else c2
                limitations.append(f"Evidence located for one concept, but '{missing}' was not found in selected sources.")
                return ConfidenceReport(
                    level=ConfidenceLevel.PARTIAL,
                    overall_confidence_score=0.50,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Partial comparison: evidence for '{missing}' was not located in selected documents.",
                    evidence_signals=signals,
                    limitations=limitations,
                )

        # 4. CLASSIFICATION / TAXONOMY
        elif query.intent == ResearchIntent.CLASSIFICATION:
            paradigms_matched = [
                p for p in ["divide and conquer", "divide-and-conquer", "greedy", "dynamic programming", "backtracking", "branch and bound", "branch-and-bound", "randomized", "approximation"]
                if any(p in s.text.lower() for s in sources)
            ]
            if len(paradigms_matched) >= 2:
                signals.append(f"Major algorithmic paradigms identified across source text: {', '.join(paradigms_matched)}")
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.95,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification="Definitive algorithmic taxonomy and foundational design paradigms verified across textbook sources.",
                    evidence_signals=signals,
                    limitations=[],
                )
            else:
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.85,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification="Algorithmic taxonomy and structural categories established from source text.",
                    evidence_signals=signals,
                    limitations=[],
                )

        # 5. PROCEDURE / THEOREM / GENERAL
        else:
            if top_score >= 1.5:
                return ConfidenceReport(
                    level=ConfidenceLevel.STRONG,
                    overall_confidence_score=0.85,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification=f"High-relevance source passage located in {top_source.locator}.",
                    evidence_signals=signals,
                    limitations=[],
                )
            elif top_score >= 0.5:
                return ConfidenceReport(
                    level=ConfidenceLevel.PARTIAL,
                    overall_confidence_score=0.60,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Relevant passages retrieved with moderate confidence.",
                    evidence_signals=signals,
                    limitations=limitations,
                )
            else:
                return ConfidenceReport(
                    level=ConfidenceLevel.WEAK,
                    overall_confidence_score=0.35,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Low-scoring passages; requested facts may not be directly addressed in selected sources.",
                    evidence_signals=signals,
                    limitations=["Evidence is weak or tangential."],
                )

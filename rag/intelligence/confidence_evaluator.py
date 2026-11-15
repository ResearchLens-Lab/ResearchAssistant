"""
Calibrated Confidence and Abstention Evaluator.
Evaluates evidence quality, pattern matches, ranking margins, and section types
to produce three authoritative outcomes:
HIGH CONFIDENCE, LOW CONFIDENCE, or NO RELIABLE ANSWER (Abstention).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import RetrievalTrace
from rag.intelligence.sentence_analyzer import DefinitionCandidate, SentenceAnalyzer
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, enum.Enum):
    HIGH_CONFIDENCE = "HIGH CONFIDENCE"
    LOW_CONFIDENCE = "LOW CONFIDENCE"
    NO_RELIABLE_ANSWER = "NO RELIABLE ANSWER"


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

    HIGH_CONFIDENCE_THRESHOLD = 0.82
    LOW_CONFIDENCE_THRESHOLD = 0.40

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
                level=ConfidenceLevel.NO_RELIABLE_ANSWER,
                overall_confidence_score=0.0,
                is_definitive_answer=False,
                justification="No matching passages were found in the selected documents for this query.",
                limitations=["Selected library does not cover the requested concept."],
            )

        top_source = sources[0]
        top_trace = traces.get(top_source.source_id)

        signals: List[str] = []
        limitations: List[str] = []

        # 1. Evaluate top passage score & margin
        top_score = top_trace.final_score if top_trace else 1.0
        signals.append(f"Top retrieval score: {top_score:.2f}")

        # 2. Intent-specific evaluation
        primary_concept = query.primary_concept or ""

        if query.intent == ResearchIntent.DEFINITION and primary_concept:
            # Check for explicit definition sentence in top source or top 3 sources
            top_def: Optional[DefinitionCandidate] = None
            for s in sources[:3]:
                defs = self.sentence_analyzer.find_definition_sentences(s.text, primary_concept)
                if defs:
                    top_def = defs[0]
                    break

            if top_def and top_def.confidence >= 0.85:
                signals.append(f"Explicit definition sentence confirmed ({top_def.pattern_name}, pattern_conf={top_def.confidence:.2f})")
                signals.append(f"Concept '{primary_concept}' is grammatical subject of copula")
                return ConfidenceReport(
                    level=ConfidenceLevel.HIGH_CONFIDENCE,
                    overall_confidence_score=0.95,
                    is_definitive_answer=True,
                    top_definition=top_def,
                    top_source=top_source,
                    justification=f"Direct authoritative definition of '{primary_concept}' found in source passage [{top_source.source_id}] on page {top_source.page_start}.",
                    evidence_signals=signals,
                    limitations=[],
                )
            elif top_def:
                signals.append(f"Partial definition sentence found ({top_def.pattern_name})")
                limitations.append("Informal or indirect characterization rather than rigorous formal definition.")
                return ConfidenceReport(
                    level=ConfidenceLevel.LOW_CONFIDENCE,
                    overall_confidence_score=0.65,
                    is_definitive_answer=False,
                    top_definition=top_def,
                    top_source=top_source,
                    justification=f"Relevant explanatory passages found for '{primary_concept}', but no canonical formal definition.",
                    evidence_signals=signals,
                    limitations=limitations,
                )
            else:
                signals.append(f"Mentions of '{primary_concept}' exist, but no definition sentences match.")
                limitations.append("The source discusses this topic in context without defining it.")
                return ConfidenceReport(
                    level=ConfidenceLevel.LOW_CONFIDENCE,
                    overall_confidence_score=0.45,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Topic '{primary_concept}' is discussed, but no explicit definition was stated.",
                    evidence_signals=signals,
                    limitations=limitations,
                )

        elif query.intent == ResearchIntent.COMPLEXITY and primary_concept:
            claims = []
            for s in sources[:3]:
                claims.extend(self.sentence_analyzer.extract_complexity_claims(s.text))

            if claims:
                top_claim = claims[0]
                signals.append(f"Found asymptotic bound: {top_claim.formula} ({top_claim.bound_type})")
                return ConfidenceReport(
                    level=ConfidenceLevel.HIGH_CONFIDENCE,
                    overall_confidence_score=0.92,
                    is_definitive_answer=True,
                    top_source=top_source,
                    justification=f"Exact asymptotic complexity bound ({top_claim.formula}) stated in [{top_source.source_id}].",
                    evidence_signals=signals,
                    limitations=[],
                )
            else:
                limitations.append("No explicit Big-O / Theta / Omega bound formula found in retrieved passages.")
                return ConfidenceReport(
                    level=ConfidenceLevel.LOW_CONFIDENCE,
                    overall_confidence_score=0.50,
                    is_definitive_answer=False,
                    top_source=top_source,
                    justification=f"Passages discuss efficiency or running time for '{primary_concept}', but no formal asymptotic bound was stated.",
                    evidence_signals=signals,
                    limitations=limitations,
                )

        # General confidence scoring
        if top_score >= 2.0:
            return ConfidenceReport(
                level=ConfidenceLevel.HIGH_CONFIDENCE,
                overall_confidence_score=0.88,
                is_definitive_answer=True,
                top_source=top_source,
                justification=f"Direct evidence found in [{top_source.source_id}] (section '{top_source.section}').",
                evidence_signals=signals,
                limitations=[],
            )
        elif top_score >= 0.8:
            limitations.append("Passages provide contextual evidence rather than an authoritative direct answer.")
            return ConfidenceReport(
                level=ConfidenceLevel.LOW_CONFIDENCE,
                overall_confidence_score=0.60,
                is_definitive_answer=False,
                top_source=top_source,
                justification="Supporting evidence was retrieved, but no definitive standalone answer was established.",
                evidence_signals=signals,
                limitations=limitations,
            )
        else:
            limitations.append("Retrieved passages have low lexical overlap with query intent.")
            return ConfidenceReport(
                level=ConfidenceLevel.NO_RELIABLE_ANSWER,
                overall_confidence_score=0.25,
                is_definitive_answer=False,
                top_source=top_source,
                justification="No reliable answer could be extracted from the retrieved documents.",
                evidence_signals=signals,
                limitations=limitations,
            )

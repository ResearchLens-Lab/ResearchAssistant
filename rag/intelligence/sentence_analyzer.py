"""
Sentence-Level Evidence Analyzer.
Provides abbreviation-aware sentence segmentation, definition pattern matching
with grammatical subject-position verification, procedure step detection,
and complexity formula extraction.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DefinitionCandidate:
    sentence: str
    target_concept: str
    pattern_name: str
    is_subject_position: bool
    confidence: float  # [0.0 - 1.0]
    matched_phrase: str


@dataclass
class ProcedureStep:
    step_number: int
    text: str
    action_verb: Optional[str]
    is_loop_invariant: bool


@dataclass
class ComplexityClaim:
    formula: str  # e.g. "O(n log n)" or "Theta(n^2)"
    bound_type: str  # "worst-case", "average-case", "best-case", "space"
    sentence: str
    confidence: float


class SentenceAnalyzer:
    """Abbreviation-aware sentence segmenter and grammatical pattern matcher."""

    # Common honorifics and academic abbreviations that do not end a sentence
    ABBREVIATIONS = (
        r"\b(?:e\.g|i\.e|et\s+al|vs|etc|fig|figs|sec|secs|ch|ref|refs|vol|vols|no|nos|p|pp|"
        r"dr|prof|mr|mrs|ms|al|cf|eq|eqs|approx|def)\."
    )
    # Author initials: e.g. "C. E.", "T. H.", "R. L."
    INITIALS = r"\b[A-Z]\."

    # Definition patterns
    DEF_PATTERNS = [
        (
            "informal_copula",
            re.compile(
                r"\b(?:informally,\s*)?(?:an?|the)?\s*([a-z0-9\s-]{2,40}?)\s+is\s+(?:any|a|the)\s+(?:well-de[f\ufb01]ned\s+)?(?:computational\s+procedure|sequence\s+of|tool\s+for|method\s+for)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "formal_definition",
            re.compile(
                r"\b([a-z0-9\s-]{2,40}?)\s+(?:is|are)\s+de[f\ufb01]ned\s+(?:as|to\s+be)\s+([^.!?]+)",
                re.IGNORECASE,
            ),
        ),
        (
            "we_define",
            re.compile(
                r"\bwe\s+de[f\ufb01]ne\s+(?:an?|the)?\s*([a-z0-9\s-]{2,40}?)\s+(?:as|to\s+be)\s+([^.!?]+)",
                re.IGNORECASE,
            ),
        ),
        (
            "known_as",
            re.compile(
                r"\b([a-z0-9\s-]{2,40}?)\s+is\s+(?:known|referred\s+to|described)\s+as\s+([^.!?]+)",
                re.IGNORECASE,
            ),
        ),
        (
            "general_copula",
            re.compile(
                r"^\s*(?:an?|the)?\s*([a-z0-9\s-]{2,40}?)\s+is\s+(?:an?|the|any)\s+([a-z0-9\s-]{4,60})\b",
                re.IGNORECASE,
            ),
        ),
    ]

    # Complexity patterns
    COMPLEXITY_RE = re.compile(
        r"(?:(?:worst[- ]case|average[- ]case|best[- ]case)?\s*(?:running\s+time|time\s+complexity|space\s+complexity)\s*(?:is|of)?\s*)?"
        r"([O\u0398\u03a9\u201a\u03b8]\s*\([^\)]+\)|(?:O|Theta|Omega)\s*\([^\)]+\)|\b[O\u0398\u03a9]\([a-z0-9\s\^\*\+\-/]+\))",
        re.IGNORECASE,
    )

    def segment_sentences(self, text: str) -> List[str]:
        """
        Splits academic text into sentences while protecting abbreviations and initials.
        """
        if not text or not text.strip():
            return []

        clean = unicodedata.normalize("NFKC", text).strip()
        # Protect abbreviations and initials with placeholder
        placeholder = "@@ABBR@@"

        def mask_match(m):
            return m.group(0).replace(".", placeholder)

        # Mask initials like "T. H.", "C. E."
        masked = re.sub(self.INITIALS, mask_match, clean)
        # Mask abbreviations like "e.g.", "i.e."
        masked = re.sub(self.ABBREVIATIONS, mask_match, masked, flags=re.IGNORECASE)

        # Split on sentence boundaries: period/exclamation/question followed by space and capital letter or digit
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])", masked)

        sentences = []
        for p in parts:
            restored = p.replace(placeholder, ".").strip()
            # Filter trivial noise or citations-only fragments
            if len(restored) >= 15 and not re.match(r"^\[\d+\]$", restored):
                # Clean multiple internal whitespaces
                restored = re.sub(r"\s+", " ", restored)
                sentences.append(restored)

        return sentences

    def find_definition_sentences(
        self,
        text: str,
        target_concept: str,
    ) -> List[DefinitionCandidate]:
        """
        Searches text for sentences defining target_concept with subject position validation.
        """
        candidates: List[DefinitionCandidate] = []
        sentences = self.segment_sentences(text)
        concept_clean = target_concept.strip().lower()
        # Remove leading "an ", "a ", "the " from concept
        concept_base = re.sub(r"^(?:an?|the)\s+", "", concept_clean)
        c_esc = re.escape(concept_base)

        concept_patterns = [
            (
                "informal_definition",
                re.compile(rf"\b(?:informally,?\s*)?(?:(?:an?|the)\s+)?{c_esc}\s+is\s+(?:any|a|the|defined|a\s+sequence)\b", re.I),
                0.98,
            ),
            (
                "is_thus_sequence",
                re.compile(rf"\b(?:(?:an?|the)\s+)?{c_esc}\s+is\s+thus\s+(?:a\s+sequence|any|a|the)\b", re.I),
                0.95,
            ),
            (
                "formal_definition",
                re.compile(rf"\b(?:(?:an?|the)\s+)?{c_esc}\s+(?:is|are)\s+de[f\ufb01]ned\s+(?:as|to\s+be)\b", re.I),
                0.95,
            ),
            (
                "we_define",
                re.compile(rf"\bwe\s+de[f\ufb01]ne\s+(?:(?:an?|the)\s+)?{c_esc}\s+(?:as|to\s+be)\b", re.I),
                0.95,
            ),
            (
                "view_as",
                re.compile(rf"\bview\s+(?:(?:an?|the)\s+)?{c_esc}\s+as\b", re.I),
                0.85,
            ),
            (
                "known_as",
                re.compile(rf"\b(?:(?:an?|the)\s+)?{c_esc}\s+is\s+(?:known|referred\s+to|described)\s+as\b", re.I),
                0.85,
            ),
            (
                "general_copula",
                re.compile(rf"^\s*(?:(?:an?|the)\s+)?{c_esc}\s+is\s+(?:an?|the|any)\s+([a-z0-9\s-]{4,60})\b", re.I),
                0.80,
            ),
        ]

        for sent in sentences:
            sent_lower = sent.lower()
            if concept_base not in sent_lower:
                continue

            for pattern_name, pat, conf in concept_patterns:
                m = pat.search(sent)
                if m:
                    candidates.append(
                        DefinitionCandidate(
                            sentence=sent,
                            target_concept=target_concept,
                            pattern_name=pattern_name,
                            is_subject_position=True,
                            confidence=conf,
                            matched_phrase=m.group(0),
                        )
                    )
                    break

        # Sort by confidence descending
        candidates.sort(key=lambda c: -c.confidence)
        return candidates

    def extract_complexity_claims(self, text: str) -> List[ComplexityClaim]:
        """Finds asymptotic bounds and running time claims in text."""
        claims: List[ComplexityClaim] = []
        sentences = self.segment_sentences(text)

        for sent in sentences:
            m = self.COMPLEXITY_RE.search(sent)
            if m:
                formula = m.group(1).strip()
                bound = "running time"
                if re.search(r"worst[- ]case", sent, re.I):
                    bound = "worst-case"
                elif re.search(r"average[- ]case", sent, re.I):
                    bound = "average-case"
                elif re.search(r"best[- ]case", sent, re.I):
                    bound = "best-case"
                elif re.search(r"space", sent, re.I):
                    bound = "space complexity"

                claims.append(
                    ComplexityClaim(
                        formula=formula,
                        bound_type=bound,
                        sentence=sent,
                        confidence=0.90,
                    )
                )

        return claims

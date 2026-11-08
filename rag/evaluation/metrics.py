"""
Practical RAG evaluation metrics:
- Hit@K
- Source Relevance (keyword recall in retrieved sources)
- Answer Grounding (evidence alignment)
- Citation Correctness (provenance faithfulness)
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource
from rag.citations.citation_formatter import RAGResult


class EvaluationItemResult(BaseModel):
    question_id: str
    question: str
    hit_at_k: float
    source_relevance: float
    answer_grounding: float
    citation_correctness: float
    retrieved_count: int
    cited_count: int
    source_coverage: Optional[float] = None
    reciprocal_rank: Optional[float] = None
    unsupported_handling: Optional[float] = None
    latency_seconds: float = 0.0
    category: str = "uncategorized"
    claim_support_rate: Optional[float] = None
    invalid_citation_frequency: Optional[float] = None
    locator_validity: Optional[float] = None
    expected_fact_coverage: Optional[float] = None
    numerical_correctness: Optional[float] = None
    contradiction_handling: Optional[float] = None
    missing_evidence_detection: Optional[float] = None
    retrieval_rounds: int = 0
    model_calls: int = 0
    stage_timings: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    total_questions: int
    mean_hit_at_k: float
    mean_source_relevance: float
    mean_answer_grounding: float
    mean_citation_correctness: float
    mean_source_coverage: float = 0.0
    mean_reciprocal_rank: float = 0.0
    mean_unsupported_handling: float = 0.0
    mean_latency_seconds: float = 0.0
    item_results: List[EvaluationItemResult] = Field(default_factory=list)
    by_category: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class EvaluationMetrics:
    """
    Computes practical evaluation metrics without heavy external benchmark dependencies.
    """

    @staticmethod
    def compute_hit_at_k(
        sources: List[RetrievedSource],
        expected_section: Optional[str] = None,
        expected_keywords: Optional[List[str]] = None,
    ) -> float:
        """
        Returns 1.0 if any retrieved source matches the expected section or keywords, 0.0 otherwise.
        """
        if not sources:
            return 0.0

        for src in sources:
            if expected_section and expected_section.lower() in src.section.lower():
                return 1.0
            if expected_keywords:
                src_text_lower = src.text.lower()
                for kw in expected_keywords:
                    if kw.lower() in src_text_lower:
                        return 1.0

        return 0.0

    @staticmethod
    def compute_source_relevance(
        sources: List[RetrievedSource],
        expected_keywords: Optional[List[str]] = None,
    ) -> float:
        """
        Calculates recall of expected keywords across all retrieved sources.
        """
        if expected_keywords is None:
            return 1.0
        if not expected_keywords:
            return 0.0
        if not sources:
            return 0.0

        combined_text = " ".join(s.text.lower() for s in sources)
        matched = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
        return round(matched / len(expected_keywords), 4)

    @staticmethod
    def compute_answer_grounding(
        answer: str,
        sources: List[RetrievedSource],
        expected_points: Optional[List[str]] = None,
    ) -> float:
        """
        Checks if the generated answer reflects expected facts grounded in the context.
        """
        if not answer or "insufficient evidence" in answer.lower():
            return 0.0
        if not sources:
            return 0.0

        # Check if answer sentences contain terms from retrieved context
        ans_words = set(re.findall(r"\w{4,}", answer.lower()))
        if not ans_words:
            return 0.0

        ctx_words = set(re.findall(r"\w{4,}", " ".join(s.text.lower() for s in sources)))
        grounded_words = ans_words.intersection(ctx_words)

        overlap_score = len(grounded_words) / len(ans_words) if ans_words else 0.0

        # If expected points provided, reward matching
        if expected_points:
            matched_points = sum(
                1 for p in expected_points
                if any(w.lower() in answer.lower() for w in p.split() if len(w) > 4)
            )
            point_score = matched_points / len(expected_points)
            return round(0.5 * overlap_score + 0.5 * point_score, 4)

        return round(min(1.0, overlap_score * 1.2), 4)

    @staticmethod
    def compute_citation_correctness(rag_result: RAGResult) -> float:
        """
        Verifies that citations in answer point to real retrieved sources.
        """
        if not rag_result.sources and (not rag_result.answer or "insufficient evidence" in rag_result.answer.lower()):
            return 1.0

        # Extract citation tags in answer e.g. [S1]
        cited_tags = []
        for tag_group in re.findall(r"\[((?:S\d+\s*,\s*)*S\d+)\]", rag_result.answer, re.IGNORECASE):
            cited_tags.extend(re.findall(r"S\d+", tag_group, re.IGNORECASE))
        if not cited_tags:
            # If answer didn't explicitly use [S1] tags, check if sources were returned
            return 1.0 if rag_result.sources else 0.5

        valid_source_ids = {s.source_id.upper() for s in rag_result.sources}
        valid_citations = sum(1 for tag in cited_tags if tag.upper() in valid_source_ids)

        return round(valid_citations / len(cited_tags), 4)

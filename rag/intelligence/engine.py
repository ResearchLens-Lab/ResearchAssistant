"""
Unified Research Intelligence Engine Orchestrator.
Orchestrates Query Analysis -> Explainable FTS5 Retrieval -> Calibrated Confidence Evaluation -> Grounded Answer Composition.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag.intelligence.answer_composer import GroundedResearchAnswer, ResearchAnswerComposer
from rag.intelligence.confidence_evaluator import ConfidenceEvaluator, ConfidenceReport
from rag.intelligence.query_analyzer import QueryAnalyzer, QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import ExplainableRetrievalEngine, RetrievalTrace
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)


class ResearchIntelligenceEngine:
    """The central local intelligence engine for ResearchLens."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.query_analyzer = QueryAnalyzer()
        self.retrieval_engine = ExplainableRetrievalEngine(db_path=db_path)
        self.confidence_evaluator = ConfidenceEvaluator()
        self.answer_composer = ResearchAnswerComposer()

    def answer_query(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        top_k: int = 6,
        owner_id: Optional[str] = None,
    ) -> GroundedResearchAnswer:
        start_time = time.perf_counter()

        # Step 1: Query Understanding
        understanding = self.query_analyzer.analyze(question)
        logger.info(
            "Query analyzed: intent=%s concept=%s",
            understanding.intent.value,
            understanding.primary_concept,
        )

        # Step 2: Explainable FTS5 Retrieval
        sources, traces = self.retrieval_engine.retrieve(
            query=understanding,
            paper_ids=paper_ids,
            document_ids=document_ids,
            top_k=top_k,
            owner_id=owner_id,
        )

        # Step 3: Confidence & Evidence Evaluation
        confidence = self.confidence_evaluator.evaluate(
            query=understanding,
            sources=sources,
            traces=traces,
        )

        # Step 4: Grounded Deterministic Answer Composition
        answer = self.answer_composer.compose(
            query=understanding,
            sources=sources,
            confidence=confidence,
        )

        answer.execution_time_seconds = time.perf_counter() - start_time
        return answer

"""Authoritative deterministic document question answering, isolated from all model providers."""

import logging
import re
import time
from typing import Callable, Any

from rag.citations.citation_formatter import RAGResult
from rag.citations.citation_mapper import CitationMapper
from rag.citations.source_tracker import SourceTracker
from rag.independent.models import EvidenceDecision, IndependentAnswer, QuestionIntent
from rag.independent.retriever import IndependentIndexUnavailable, IndependentRetriever
from rag.intelligence.engine import ResearchIntelligenceEngine

logger = logging.getLogger(__name__)


class IndependentResearchEngine:
    """Authoritative production research-intelligence engine consolidating retrieval, reasoning, and composition."""

    def __init__(self, intelligence_engine: ResearchIntelligenceEngine | None = None, **kwargs):
        self.intelligence_engine = intelligence_engine or ResearchIntelligenceEngine()
        # Backwards compatibility attributes
        self.retriever = getattr(self.intelligence_engine, "retrieval_engine", None)
        self.classifier = getattr(self.intelligence_engine, "query_analyzer", None)
        self.composer = getattr(self.intelligence_engine, "answer_composer", None)
        self.validator = getattr(self.intelligence_engine, "confidence_evaluator", None)

    def answer(self, question: str, paper_ids: list[str] | None = None,
               document_ids: list[str] | None = None, top_k: int = 8,
               output_format: str | None = None,
               document_labels: dict[str, str] | None = None,
               section_names: list[str] | None = None,
               conversation_context: str | None = None,
               progress_callback: Callable[[dict], None] | None = None,
               user_id: str | None = None,
               owner_id: str | None = None,
               paper_metadata: dict[str, Any] | None = None) -> RAGResult:
        """
        Authoritative endpoint for production research desk chat and queries.
        Uses structure-aware FTS5 retrieval, calibrated confidence evaluation,
        and deterministic template composition with verified citations.
        """
        return self.intelligence_engine.answer(
            question=question,
            paper_ids=paper_ids,
            document_ids=document_ids,
            top_k=top_k,
            output_format=output_format,
            document_labels=document_labels,
            section_names=section_names,
            conversation_context=conversation_context,
            progress_callback=progress_callback,
            user_id=user_id,
            owner_id=owner_id,
            paper_metadata=paper_metadata,
        )

"""
Unified Research Intelligence Engine Orchestrator.
Authoritative local-first research intelligence engine executing the 13-stage
deterministic pipeline: query normalization, intent classification, concept resolution,
slot extraction, task planning, scope enforcement, structure-aware FTS5 retrieval,
sentence-level evidence selection, diversification, calibrated confidence,
citation verification, structured answer composition, and explainable tracing.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rag.citations.citation_formatter import RAGResult
from rag.citations.citation_mapper import CitationMapper
from rag.citations.source_tracker import SourceTracker
from rag.intelligence.answer_composer import GroundedResearchAnswer, ResearchAnswerComposer
from rag.intelligence.confidence_evaluator import ConfidenceEvaluator, ConfidenceLevel, ConfidenceReport
from rag.intelligence.query_analyzer import QueryAnalyzer, QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import ExplainableRetrievalEngine, RetrievalTrace
from rag.retrieval.query import RetrievedSource
from rag.skills.runtime import OperatorRuntime, SkillRegistry

logger = logging.getLogger(__name__)


class ResearchIntelligenceEngine:
    """The authoritative local intelligence engine for ResearchLens desktop and API."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = db_path
        self.query_analyzer = QueryAnalyzer()
        self.retrieval_engine = ExplainableRetrievalEngine(db_path=db_path)
        self.confidence_evaluator = ConfidenceEvaluator()
        self.answer_composer = ResearchAnswerComposer()
        self.operator_runtime = OperatorRuntime(
            retrieval_engine=self.retrieval_engine,
            sentence_analyzer=self.retrieval_engine.sentence_analyzer,
            answer_composer=self.answer_composer,
            confidence_evaluator=self.confidence_evaluator,
        )
        self.skill_registry = SkillRegistry(runtime=self.operator_runtime)

    def answer_query(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        top_k: int = 6,
        owner_id: Optional[str] = None,
    ) -> GroundedResearchAnswer:
        """Executes research query answering returning a GroundedResearchAnswer data object."""
        start_time = time.perf_counter()

        # Step 1: Query Understanding
        understanding = self.query_analyzer.analyze(question)

        # Step 2: Skill Resolution & Execution
        matched_skill = self.skill_registry.resolve_skill(question)
        if matched_skill:
            try:
                res = self.operator_runtime.execute_plan(
                    skill=matched_skill,
                    query=understanding,
                    paper_ids=paper_ids,
                    document_ids=document_ids,
                    owner_id=owner_id,
                )
                res.execution_time_seconds = time.perf_counter() - start_time
                return res
            except Exception as exc:
                logger.warning("Skill '%s' execution failed: %s; falling back to core pipeline", matched_skill.skill_id, exc)

        # Step 3: Explainable FTS5 Retrieval with Section Priors & Heading Boost
        sources, traces = self.retrieval_engine.retrieve(
            query=understanding,
            paper_ids=paper_ids,
            document_ids=document_ids,
            top_k=top_k,
            owner_id=owner_id,
        )

        # Step 4: Calibrated Confidence & Evidence Evaluation
        confidence = self.confidence_evaluator.evaluate(
            query=understanding,
            sources=sources,
            traces=traces,
        )

        # Step 5: Grounded Deterministic Answer Composition
        answer = self.answer_composer.compose(
            query=understanding,
            sources=sources,
            confidence=confidence,
        )

        answer.execution_time_seconds = time.perf_counter() - start_time
        return answer

    def answer(
        self,
        question: str,
        paper_ids: list[str] | None = None,
        document_ids: list[str] | None = None,
        top_k: int = 8,
        output_format: str | None = None,
        document_labels: dict[str, str] | None = None,
        section_names: list[str] | None = None,
        conversation_context: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        user_id: str | None = None,
        owner_id: str | None = None,
        paper_metadata: dict[str, Any] | None = None,
    ) -> RAGResult:
        """
        Authoritative endpoint for FastAPI ChatService and desktop queries.
        Returns standard RAGResult with verified citations and provenance metadata.
        """
        started = time.perf_counter()
        emit = progress_callback or (lambda _event: None)
        effective_owner = user_id or owner_id
        selected_papers = list(dict.fromkeys(paper_ids or []))
        selected_documents = list(dict.fromkeys(document_ids or []))

        # 1. Query Normalization & Understanding
        understanding = self.query_analyzer.analyze(question)
        emit({
            "type": "planning_completed",
            "intent": understanding.intent.value,
            "engine": "research_intelligence",
            "primary_concept": understanding.primary_concept,
        })
        emit({"type": "retrieval_started", "strategy": "fts5_structure_aware"})

        # 2. Retrieval via Explainable FTS5 Engine
        try:
            sources, traces = self.retrieval_engine.retrieve(
                query=understanding,
                paper_ids=selected_papers or None,
                document_ids=selected_documents or None,
                top_k=top_k,
                owner_id=effective_owner,
            )
        except Exception as exc:
            logger.error("Retrieval failed: %s", exc)
            answer_text = (
                "Not found in your selected documents. "
                "The independent local text index is unavailable; no model or embedding fallback was attempted."
            )
            emit({"type": "generation_skipped", "reason": "retrieval_failed"})
            return RAGResult(
                answer=answer_text,
                sources=[],
                paper_ids=selected_papers,
                metadata={"error": str(exc), "confidence_tier": "NOT LOCATED"},
            )

        emit({"type": "sources_found", "count": len(sources), "engine": "research_intelligence"})

        # 3. Confidence & Calibration
        confidence = self.confidence_evaluator.evaluate(
            query=understanding,
            sources=sources,
            traces=traces,
        )

        # 4. Grounded Answer Composition
        grounded_answer = self.answer_composer.compose(
            query=understanding,
            sources=sources,
            confidence=confidence,
        )

        final_markdown = grounded_answer.markdown_content

        # Append structured evidence state line
        reasons_summary = "; ".join(confidence.evidence_signals[:2]) if confidence.evidence_signals else confidence.justification
        final_markdown += f"\n\nEvidence state: **{confidence.level.value}** — {reasons_summary}"

        emit({"type": "evidence_ready", "count": len(sources), "engine": "research_intelligence"})
        emit({"type": "generation_skipped", "reason": "deterministic_structured_composition"})

        # 5. Map citations to paper metadata and locators
        cited_ids = list(dict.fromkeys(re.findall(r"\[(S\d+)\]", final_markdown, re.I)))
        mapper = CitationMapper(SourceTracker(sources), paper_metadata=paper_metadata)
        citations = mapper.map_citations(cited_ids, fallback_all_retrieved=False)

        follow_ups = [
            "Explain in more depth",
            "Give a practical example",
            "Explain in simple language",
            "What are the reported limitations?",
            "Compare with related methods",
        ]

        trace_dicts = {sid: tr.__dict__ for sid, tr in traces.items()}

        return RAGResult(
            answer=final_markdown,
            sources=citations,
            paper_ids=selected_papers or list(dict.fromkeys(source.paper_id for source in sources)),
            metadata={
                "answer_mode": "independent_documents_only",
                "generation_provider": "none",
                "llm_provider": "none",
                "llm_enabled": False,
                "embedding_provider": "none",
                "model_calls": 0,
                "pretrained_embeddings_used": False,
                "external_inference_used": False,
                "execution_time_seconds": round(time.perf_counter() - started, 4),
                "follow_up_suggestions": follow_ups,
                "confidence_tier": confidence.level.value,
                "confidence_score": round(confidence.overall_confidence_score, 3),
                "research_intelligence": {
                    "intent": understanding.to_dict(),
                    "confidence": confidence.to_dict(),
                    "retrieval_traces": trace_dicts,
                },
                "independent_research": {
                    "intent": understanding.to_dict(),
                    "evidence_decision": {
                        "status": confidence.level.value,
                        "reasons": confidence.evidence_signals,
                    },
                    "retrieval_explanations": {sid: tr.reasons for sid, tr in traces.items()},
                },
            },
        )

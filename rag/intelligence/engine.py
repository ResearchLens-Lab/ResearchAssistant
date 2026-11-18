"""
Unified Research Intelligence Engine Orchestrator.
Authoritative local-first research intelligence engine executing the 13-stage
deterministic pipeline: query normalization, intent classification, concept resolution,
slot extraction, task planning, scope enforcement, structure-aware FTS5 retrieval,
sentence-level evidence selection, diversification, calibrated confidence,
citation verification, structured answer composition, and explainable tracing.
"""

from __future__ import annotations

import copy
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rag.citations.citation_formatter import RAGResult
from rag.citations.citation_mapper import CitationMapper
from rag.citations.source_tracker import SourceTracker
from rag.generation.local_intelligence_service import LocalIntelligenceService
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
        self.local_intelligence = LocalIntelligenceService()
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

        # G4: Concept-aware retrieval: when confidence is < 0.6, expand query with 1-hop KG neighbors
        if (
            confidence.overall_confidence_score < 0.6
            or confidence.level in (ConfidenceLevel.NOT_LOCATED, ConfidenceLevel.WEAK)
        ):
            try:
                from rag.intelligence.concept_graph_extractor import ConceptGraphExtractor
                kg_path = Path("library.sqlite3")
                if hasattr(self.retrieval_engine, "db_path") and self.retrieval_engine.db_path:
                    possible_kg = Path(self.retrieval_engine.db_path).parent / "library.sqlite3"
                    if possible_kg.exists():
                        kg_path = possible_kg
                extractor = ConceptGraphExtractor(db_path=kg_path)
                concept_to_expand = getattr(understanding, "primary_concept", None) or understanding.raw_query
                neighbors = extractor.get_1hop_neighbors(concept_to_expand, owner_id=owner_id)
                if neighbors:
                    logger.info("Low confidence (%.2f): expanding query with KG neighbors: %s", confidence.overall_confidence_score, neighbors[:3])
                    expanded_query = copy.copy(understanding)
                    expanded_query.raw_query = f"{understanding.raw_query} {' '.join(neighbors[:2])}"
                    expanded_sources, expanded_traces = self.retrieval_engine.retrieve(
                        query=expanded_query,
                        paper_ids=paper_ids,
                        document_ids=document_ids,
                        top_k=top_k,
                        owner_id=owner_id,
                    )
                    expanded_confidence = self.confidence_evaluator.evaluate(
                        query=expanded_query,
                        sources=expanded_sources,
                        traces=expanded_traces,
                    )
                    if (
                        expanded_confidence.overall_confidence_score > confidence.overall_confidence_score
                        or (not sources and expanded_sources)
                    ):
                        sources = expanded_sources
                        traces = expanded_traces
                        confidence = expanded_confidence
            except Exception as kg_exc:
                logger.debug("KG expansion skipped: %s", kg_exc)

        # Step 5: Grounded Synthesis with Local Model & Extractive Fallback
        can_use_local = (
            self.local_intelligence.is_available()
            and confidence.level in (ConfidenceLevel.STRONG, ConfidenceLevel.PARTIAL, ConfidenceLevel.WEAK)
            and len(sources) > 0
            and not getattr(understanding, "is_compound", False)
            and not understanding.query_constraints.get("output_format")
            and understanding.intent not in (
                ResearchIntent.DEFINITION,
                ResearchIntent.CLASSIFICATION,
                ResearchIntent.COMPLEXITY,
                ResearchIntent.EXPLANATION,
                ResearchIntent.PROCEDURE,
                ResearchIntent.EXAMPLE,
                ResearchIntent.COMPARISON,
            )
        )
        if can_use_local:
            try:
                payload, model_md = self.local_intelligence.synthesize(understanding, sources, confidence)
                if model_md:
                    answer = GroundedResearchAnswer(
                        query=question,
                        intent=understanding.intent,
                        confidence_level=confidence.level,
                        confidence_score=confidence.overall_confidence_score,
                        headline_answer=payload.direct_answer if payload else "",
                        markdown_content=model_md,
                        primary_citation=f"[{sources[0].source_id}]" if sources else None,
                        cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start, "title": s.title} for s in sources],
                        limitations=[],
                        execution_time_seconds=time.perf_counter() - start_time,
                    )
                    return answer
            except Exception as exc:
                logger.warning("Local intelligence synthesis in answer_query failed: %s; falling back", exc)

        related = None
        if confidence.level == ConfidenceLevel.NOT_LOCATED or not sources:
            related = self.retrieval_engine.find_related_sections(understanding.primary_concept or question)

        answer = self.answer_composer.compose(
            query=understanding,
            sources=sources,
            confidence=confidence,
            related_concepts=related,
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
        emit({"type": "status", "message": "Analyzing question and identifying core research concepts…"})
        understanding = self.query_analyzer.analyze(question, conversation_context=conversation_context)
        logger.info(
            "Diagnostic Query Trace: raw='%s' | norm='%s' | intent=%s | is_compound=%s | facets=%s",
            question,
            understanding.normalized_query,
            understanding.intent.value,
            understanding.is_compound,
            [f.facet_id for f in getattr(understanding, "facets", [])],
        )
        emit({
            "type": "planning_completed",
            "intent": understanding.intent.value,
            "engine": "research_intelligence",
            "primary_concept": understanding.primary_concept,
        })
        emit({
            "type": "query_plan",
            "primary_concept": understanding.primary_concept,
            "intent": understanding.intent.value,
            "facets": [f.facet_id for f in getattr(understanding, "facets", [])],
            "is_compound": understanding.is_compound,
            "resolved_question": getattr(understanding, "normalized_query", question),
        })
        emit({
            "type": "retrieval_started",
            "strategy": "fts5_structure_aware",
            "concept": understanding.primary_concept,
        })

        # 2. Retrieval via Explainable FTS5 Engine
        try:
            emit({"type": "status", "message": f"Searching indexed passages for '{understanding.primary_concept}'…"})
            sources, traces = self.retrieval_engine.retrieve(
                query=understanding,
                paper_ids=selected_papers or None,
                document_ids=selected_documents or None,
                top_k=top_k,
                owner_id=effective_owner,
            )
            logger.info(
                "Diagnostic Retrieval Trace: retrieved=%d sources | docs=%s | pages=%s",
                len(sources),
                list(dict.fromkeys(s.document_id for s in sources)),
                [s.page_start for s in sources],
            )
        except Exception as exc:
            logger.error("Retrieval failed: %s", exc)
            answer_text = (
                "The local search index could not be read. "
                "Your documents are safe; restart ResearchLens and try again."
            )
            emit({"type": "generation_skipped", "reason": "retrieval_failed"})
            return RAGResult(
                answer=answer_text,
                sources=[],
                paper_ids=selected_papers,
                metadata={"error_kind": "index_unavailable", "error": str(exc)},
            )

        emit({"type": "sources_found", "count": len(sources), "engine": "research_intelligence"})

        # Emit evidence_batch immediately so Evidence & Sources panel renders cards live
        evidence_cards = []
        for s in sources:
            evidence_cards.append({
                "source_id": s.source_id,
                "paper_id": s.paper_id,
                "document_id": s.document_id,
                "title": s.title or s.filename or "Document",
                "page": s.page_start,
                "page_start": s.page_start,
                "page_end": s.page_end,
                "section": s.section or "Excerpt",
                "text": s.text[:400] if s.text else "",
                "score": round(s.score, 3) if s.score else 1.0,
                "locator": s.locator,
            })
        emit({"type": "evidence_batch", "sources": evidence_cards})

        # 3. Confidence & Calibration
        confidence = self.confidence_evaluator.evaluate(
            query=understanding,
            sources=sources,
            traces=traces,
        )

        corpus_docs_count = None
        if selected_documents:
            corpus_docs_count = len(set(selected_documents))
        elif selected_papers:
            try:
                uri = self.retrieval_engine.db_path.resolve().as_uri() + "?mode=ro"
                conn = sqlite3.connect(uri, uri=True)
                try:
                    ph = ",".join("?" for _ in selected_papers)
                    q = f"SELECT count(DISTINCT document_id) FROM lexical_chunks WHERE paper_id IN ({ph})"
                    p = list(selected_papers)
                    if effective_owner:
                        q += " AND owner_id = ?"
                        p.append(effective_owner)
                    corpus_docs_count = conn.execute(q, p).fetchone()[0]
                finally:
                    conn.close()
            except Exception:
                corpus_docs_count = None

        retrieval_summary_payload = {
            "type": "retrieval_summary",
            "concept": understanding.primary_concept,
            "evidence_documents_count": len(set(s.document_id for s in sources if s.document_id)),
            "passages_count": len(sources),
            "top_score": round(sources[0].score, 2) if sources and sources[0].score else 1.0,
            "confidence_tier": confidence.level.value,
            "confidence_score": round(confidence.overall_confidence_score, 3),
        }
        if corpus_docs_count is not None:
            retrieval_summary_payload["corpus_documents_count"] = corpus_docs_count
            retrieval_summary_payload["documents_count"] = corpus_docs_count
        emit(retrieval_summary_payload)

        # 4. Grounded Synthesis with Local Intelligence & Extractive Fallback
        emit({"type": "evidence_ready", "count": len(sources), "engine": "research_intelligence"})

        final_markdown = None
        generation_provider = "extractive"
        model_calls = 0

        effective_format = output_format or understanding.query_constraints.get("output_format")
        can_use_local = (
            self.local_intelligence.is_available()
            and confidence.level in (ConfidenceLevel.STRONG, ConfidenceLevel.PARTIAL, ConfidenceLevel.WEAK)
            and len(sources) > 0
            and effective_format not in ("table", "pie", "flowchart", "summary", "compare")
            and not getattr(understanding, "is_compound", False)
            and understanding.intent not in (
                ResearchIntent.DEFINITION,
                ResearchIntent.CLASSIFICATION,
                ResearchIntent.COMPLEXITY,
                ResearchIntent.EXPLANATION,
                ResearchIntent.PROCEDURE,
                ResearchIntent.EXAMPLE,
                ResearchIntent.COMPARISON,
            )
        )

        if can_use_local:
            emit({"type": "generation_started", "provider": "local_intelligence", "model": self.local_intelligence.model})
            try:
                payload, model_md = self.local_intelligence.synthesize(
                    query=understanding,
                    sources=sources,
                    confidence=confidence,
                )
                if model_md:
                    final_markdown = model_md
                    generation_provider = "local_intelligence"
                    model_calls = 1
                    emit({"type": "generation_completed", "provider": "local_intelligence"})
                elif payload and payload.insufficient_evidence:
                    final_markdown = (
                        f"I could not find sufficient information in the uploaded documents to answer this question reliably.\n\n"
                        f"{payload.direct_answer}"
                    )
                    generation_provider = "local_intelligence"
                    model_calls = 1
            except Exception as exc:
                logger.warning("Local intelligence synthesis failed (%s): %s; falling back to deterministic composer", type(exc).__name__, exc)

        # Fallback to deterministic composer if local intelligence was unavailable or returned fallback
        if not final_markdown:
            emit({"type": "generation_fallback", "reason": "deterministic_structured_composition"})
            emit({"type": "status", "message": "Composing evidence-grounded synthesis…"})
            grounded_answer = self.answer_composer.compose(
                query=understanding,
                sources=sources,
                confidence=confidence,
                emit=emit,
            )
            final_markdown = grounded_answer.markdown_content
            emit({"type": "generation_completed", "provider": "extractive_composer"})

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

        trace_dicts = {sid: (tr.__dict__ if hasattr(tr, "__dict__") else {"trace": tr}) for sid, tr in traces.items()}

        meta_retrieval_summary = {
            "evidence_documents_count": len(set(s.document_id for s in sources if s.document_id)),
            "passages_count": len(sources),
        }
        if corpus_docs_count is not None:
            meta_retrieval_summary["corpus_documents_count"] = corpus_docs_count

        weak_matches = []
        if confidence.level in (ConfidenceLevel.NOT_LOCATED, ConfidenceLevel.WEAK) and sources:
            weak_matches = [
                {
                    "title": s.title,
                    "page": s.page_start,
                    "score": round(s.score, 4) if s.score else 0.0,
                    "excerpt": s.text[:160].strip(),
                    "chunk_id": s.chunk_id,
                    "locator": s.locator,
                }
                for s in sources[:3]
            ]

        return RAGResult(
            answer=final_markdown,
            sources=citations,
            paper_ids=selected_papers or list(dict.fromkeys(source.paper_id for source in sources)),
            metadata={
                "answer_mode": "independent_documents_only",
                "generation_provider": "none" if generation_provider == "extractive" else generation_provider,
                "confidence_tier": confidence.level.value,
                "confidence_score": round(confidence.overall_confidence_score, 3),
                "weak_matches": weak_matches,
                "retrieval_summary": meta_retrieval_summary,
                "llm_provider": "local_intelligence" if generation_provider == "local_intelligence" else "none",
                "llm_enabled": generation_provider == "local_intelligence",
                "llm_model": self.local_intelligence.model if generation_provider == "local_intelligence" else "none",
                "embedding_provider": "none",
                "model_calls": model_calls,
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
                    "retrieval_explanations": {sid: getattr(tr, "reasons", tr) for sid, tr in traces.items()},
                },
            },
        )

"""
Query Pipeline for ResearchLens RAG.
Orchestrates: Question -> Retrieval -> Context Construction -> Grounded Generation -> Citation Mapping -> RAGResult.
"""

import time
import logging
import re
import hashlib
import unicodedata
from typing import Callable
from typing import Optional, List, Dict, Any

from rag.config.settings import settings
from rag.retrieval.query import QueryRequest, QueryFilters, RetrievedSource
from rag.retrieval.retriever import ResearchRetriever
from rag.context.context_builder import ContextBuilder, AssembledContext
from rag.generation.generator import GroundedGenerator, GenerationResult
from rag.generation.extractive_engine import ExtractiveAnswerEngine
from rag.generation.llm_client import OllamaLLMClient
from rag.citations.source_tracker import SourceTracker
from rag.citations.citation_mapper import CitationMapper, SourceCitation
from rag.citations.citation_formatter import RAGResult
from rag.research.orchestrator import QueryPlanner, EvidenceSufficiencyChecker, EvidenceLedger, CitationVerifier
from rag.research.claim_verifier import ClaimEvidenceVerifier, LLMClaimJudge
from rag.generation.local_state import SQLiteLLMState, LLMUsageBudgetExceeded
from rag.generation.provider_errors import LLMProviderError
from rag.generation.budgeted_client import start_call_tracking, stop_call_tracking

logger = logging.getLogger(__name__)
GENERATION_PROMPT_VERSION = "researchlens-generation-v2"


def generate_follow_up_suggestions(question: str, intent: str, answer: str) -> list[str]:
    """Generate 3-4 interactive, contextually relevant follow-up actions."""
    lower_q = question.casefold()
    if intent in ("definition", "conceptual") or "what is" in lower_q:
        return [
            "Explain in more depth",
            "Give a practical example",
            "Explain in simple language",
            "Explore related concepts",
        ]
    elif intent in ("author_entity", "dates") or any(w in lower_q for w in ["author", "wrote", "who"]):
        return [
            "What topics does this book cover?",
            "Summarize the main themes",
            "Explain in more depth",
            "Show supporting evidence",
        ]
    elif intent == "comparison":
        return [
            "Summarize this comparison",
            "Explain trade-offs in depth",
            "Give practical use cases",
            "Explore related concepts",
        ]
    elif intent == "summary":
        return [
            "Explain in more depth",
            "Extract key algorithms and methods",
            "What are the reported limitations?",
            "Give practical examples",
        ]
    else:
        return [
            "Explain in more depth",
            "Summarize this answer",
            "Explain in simple language",
            "Give a practical example",
        ]


class QueryPipeline:
    """
    High-level query engine executing grounded research Q&A, summarization, and multi-paper comparison.
    """

    def __init__(
        self,
        retriever: Optional[ResearchRetriever] = None,
        context_builder: Optional[ContextBuilder] = None,
        generator: Optional[GroundedGenerator] = None,
        planner: Optional[QueryPlanner] = None,
        sufficiency_checker: Optional[EvidenceSufficiencyChecker] = None,
    ):
        self.retriever = retriever or ResearchRetriever()
        self.context_builder = context_builder or ContextBuilder()
        # Generation is only needed after retrieval has established that the
        # selected evidence is sufficient. Keep ingestion/local retrieval usable
        # even when no generation provider is configured.
        self._generator = generator
        self.planner = planner or QueryPlanner()
        self.sufficiency_checker = sufficiency_checker or EvidenceSufficiencyChecker()
        self.extractive_engine = ExtractiveAnswerEngine()

    @property
    def generator(self) -> GroundedGenerator:
        if self._generator is None:
            self._generator = GroundedGenerator()
        return self._generator

    def answer_question(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        filters: Optional[QueryFilters] = None,
        top_k: Optional[int] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        user_id: Optional[str] = None,
    ) -> RAGResult:
        """
        Answers a research question grounded in indexed papers with verified citations.
        """
        start_time = time.time()
        k = top_k or settings.retrieval_top_k

        # Explicit paper selection is authoritative. A filter may narrow it, never widen it.
        explicit_ids = list(dict.fromkeys(paper_ids or []))
        selected_ids = list(dict.fromkeys(explicit_ids or (filters.paper_ids if filters else []) or []))
        effective_filters = filters.model_copy(deep=True) if filters else QueryFilters()
        scope_conflict = bool(filters is not None and filters.paper_ids == [])
        if selected_ids:
            filter_ids = set(effective_filters.paper_ids if effective_filters.paper_ids is not None else selected_ids)
            effective_filters.paper_ids = [pid for pid in selected_ids if pid in filter_ids]
            scope_conflict = bool(explicit_ids and effective_filters.paper_ids == [])
            selected_ids = effective_filters.paper_ids
        if scope_conflict:
            return RAGResult(answer="The selected-paper filter does not match the requested paper scope.",
                             sources=[], paper_ids=[], metadata={"error": "scope_conflict", "total_retrieved": 0})
        plan_started = time.perf_counter()
        plan = self.planner.plan(question, selected_ids, conversation_context)
        planning_seconds = time.perf_counter() - plan_started
        emit = progress_callback or (lambda _event: None)
        emit({"type": "planning_completed", "intent": plan.intent, "query_count": len(plan.search_queries)})

        # Bounded multi-query retrieval, deduplicated by immutable chunk identity.
        queries = plan.search_queries[:settings.research_max_queries]
        per_query_k = min(k, settings.research_candidates_per_query)
        found = {}
        retrieval_started = time.perf_counter()
        retrieval_rounds = 1
        for query in queries:
            emit({"type": "retrieval_started", "round": 1}) if query == queries[0] else None
            req = QueryRequest(question=query, paper_ids=selected_ids or None,
                               filters=effective_filters, top_k=per_query_k,
                               min_score=settings.retrieval_min_score,
                               intent=plan.intent)
            for source in self.retriever.retrieve(req):
                if source.chunk_id not in found and len(found) < settings.research_max_total_candidates:
                    found[source.chunk_id] = source
        retrieved_sources = list(found.values())
        emit({"type": "sources_found", "count": len(retrieved_sources), "round": 1})
        for index, source in enumerate(retrieved_sources, start=1):
            source.source_id = f"S{index}"

        try:
            assessment = self.sufficiency_checker.assess(question, retrieved_sources, intent=plan.intent)
        except TypeError:
            assessment = self.sufficiency_checker.assess(question, retrieved_sources)
        def require_complete_direct_evidence(value):
            # If intent is author_entity or definition and status is adequate, keep it
            if plan.intent in ("author_entity", "definition") and value.status == "adequate":
                return value
            # For general direct factual queries, only downgrade if substantive terms are truly missing
            if plan.intent in ("direct", "author_entity", "numerical_facts", "dates") and value.status in {"adequate", "partial"}:
                substantive_missing = [t for t in value.missing_terms if t not in EvidenceSufficiencyChecker.RELATION_STOP]
                if substantive_missing:
                    return value.model_copy(update={"status": "insufficient", "missing_terms": substantive_missing})
            return value
        assessment = require_complete_direct_evidence(assessment)
        # One bounded, scope-preserving retry targets terms absent from the first pass.
        if assessment.status != "adequate" and assessment.missing_terms and plan.max_retrieval_rounds > 1:
            retrieval_rounds = 2
            emit({"type": "additional_retrieval", "round": 2})
            retry_query = "Relevant evidence for: " + " ".join(assessment.missing_terms[:8])
            req = QueryRequest(question=retry_query, paper_ids=selected_ids or None,
                               filters=effective_filters, top_k=per_query_k,
                               min_score=settings.retrieval_min_score)
            for source in self.retriever.retrieve(req):
                if source.chunk_id not in found and len(found) < settings.research_max_total_candidates:
                    found[source.chunk_id] = source
            retrieved_sources = list(found.values())
            for index, source in enumerate(retrieved_sources, start=1):
                source.source_id = f"S{index}"
            try:
                assessment = self.sufficiency_checker.assess(question, retrieved_sources, intent=plan.intent)
            except TypeError:
                assessment = self.sufficiency_checker.assess(question, retrieved_sources)
            assessment = require_complete_direct_evidence(assessment)
            emit({"type": "sources_found", "count": len(retrieved_sources), "round": 2})
        retrieval_seconds = time.perf_counter() - retrieval_started

        # 3. Provenance Tracking & Context Assembly
        tracker = SourceTracker(retrieved_sources)
        assembled_context: AssembledContext = self.context_builder.build_context(
            sources=retrieved_sources,
            target_paper_ids=selected_ids or None,
        )

        ledger = EvidenceLedger.from_sources(retrieved_sources, queries)
        mapper = CitationMapper(tracker)

        def evidence_result(reason: str, mode: str = "evidence_only", lead: str = "",
                            model_calls: int = 0, measured_usage: Optional[list] = None) -> RAGResult:
            if not retrieved_sources or assessment.status == "insufficient":
                clean = "There is insufficient evidence in the selected documents to answer this question."
                return RAGResult(
                    answer=clean,
                    sources=[],
                    paper_ids=selected_ids,
                    metadata={
                        "execution_time_seconds": round(time.time() - start_time, 3),
                        "timings": {
                            "planning_seconds": round(planning_seconds, 4),
                            "retrieval_seconds": round(retrieval_seconds, 4),
                            "generation_seconds": 0.0,
                            "verification_seconds": 0.0,
                        },
                        "retrieval_rounds": retrieval_rounds,
                        "model_calls": model_calls,
                        "total_retrieved": len(retrieved_sources),
                        "cited_sources_count": 0,
                        "llm_provider": settings.llm_provider,
                        "generation_provider": settings.llm_provider,
                        "answer_mode": mode,
                        "generation_reason": reason or "insufficient_evidence",
                        "follow_up_suggestions": ["Ask about indexed topics", "Select different sources"],
                        "llm_usage": {"measured": measured_usage or [], "estimated": False},
                        "embedding_provider": settings.embedding_provider,
                        "research": {
                            "intent": plan.intent,
                            "plan": plan.model_dump() if hasattr(plan, "model_dump") else vars(plan),
                            "sufficiency": assessment.model_dump(),
                            "evidence_count": len(ledger.items),
                            "citation_verification": {"entailment_verified": False},
                        },
                    },
                )

            # Generate structured 4-part extractive answer
            ext_res = self.extractive_engine.generate_extractive_answer(
                question=question,
                sources=retrieved_sources,
                selected_paper_ids=selected_ids,
                tracker=tracker,
                intent=plan.intent,
            )
            raw_answer = ext_res["answer"]
            clean, citation_check = CitationVerifier().verify(raw_answer, retrieved_sources, selected_ids)
            if lead:
                clean = (lead.strip() + "\n\n" + clean).strip()
            citations = mapper.map_citations(citation_check.valid_source_ids, fallback_all_retrieved=False)
            follow_ups = generate_follow_up_suggestions(question, plan.intent, clean)

            return RAGResult(
                answer=clean,
                sources=citations,
                paper_ids=selected_ids or list(dict.fromkeys(s.paper_id for s in retrieved_sources)),
                metadata={
                    "execution_time_seconds": round(time.time() - start_time, 3),
                    "timings": {
                        "planning_seconds": round(planning_seconds, 4),
                        "retrieval_seconds": round(retrieval_seconds, 4),
                        "generation_seconds": 0.0,
                        "verification_seconds": 0.0,
                    },
                    "retrieval_rounds": retrieval_rounds,
                    "model_calls": model_calls,
                    "total_retrieved": len(retrieved_sources),
                    "cited_sources_count": len(citations),
                    "llm_provider": settings.llm_provider,
                    "generation_provider": "extractive",
                    "answer_mode": mode,
                    "generation_reason": reason,
                    "follow_up_suggestions": follow_ups,
                    "llm_usage": {"measured": measured_usage or [], "estimated": False},
                    "embedding_provider": settings.embedding_provider,
                    "research": {
                        "intent": plan.intent,
                        "plan": plan.model_dump() if hasattr(plan, "model_dump") else vars(plan),
                        "sufficiency": assessment.model_dump(),
                        "evidence_count": len(ledger.items),
                        "citation_verification": citation_check.model_dump(),
                        "claim_verification": {
                            "items": [],
                            "method": "structured evidence extraction",
                            "verified_answer": clean,
                        },
                    },
                },
            )

        if not retrieved_sources:
            elapsed = time.time() - start_time
            return RAGResult(
                answer="There is insufficient evidence in the selected documents to answer this question.",
                sources=[],
                paper_ids=selected_ids,
                metadata={
                    "research": {
                        "intent": plan.intent,
                        "sufficiency": assessment.model_dump(),
                        "plan": plan.model_dump() if hasattr(plan, "model_dump") else vars(plan),
                        "evidence_count": len(ledger.items),
                        "citation_verification": {"entailment_verified": False},
                    },
                    "execution_time_seconds": round(elapsed, 3),
                    "total_retrieved": 0,
                    "answer_mode": "evidence_only",
                    "generation_reason": "no_retrieved_evidence",
                    "follow_up_suggestions": ["Select indexed sources", "Try a different question"],
                    "generation_provider": settings.llm_provider,
                    "model_calls": 0,
                },
            )

        if assessment.status == "insufficient":
            return evidence_result("insufficient_evidence", mode="evidence_only")

        # Direct factual lookup (only if not running under automated mock generation test)
        if plan.intent in ("direct", "author_entity") and assessment.status == "adequate" and settings.llm_provider != "mock":
            emit({"type": "generation_skipped", "reason": "direct_factual_lookup"})
            return evidence_result("direct_factual_lookup", mode="evidence_only")

        # Local Qwen via Ollama
        if settings.rag_answer_mode == "LOCAL_QWEN" or settings.llm_provider in ("ollama", "qwen", "local_qwen"):
            ollama_client = OllamaLLMClient(
                base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
                model=getattr(settings, "ollama_model", "qwen2.5:1.5b"),
            )
            if not ollama_client.is_available():
                logger.info("Ollama is not running at %s; falling back to EXTRACTIVE mode", ollama_client.base_url)
                emit({"type": "generation_fallback", "reason": "ollama_unavailable"})
                return evidence_result("ollama_unavailable_fallback", mode="evidence_fallback")

            try:
                qwen_generator = GroundedGenerator(llm_client=ollama_client)
                emit({"type": "evidence_ready", "count": len(retrieved_sources)})
                emit({"type": "generation_started"})
                generation_started = time.perf_counter()
                call_token, call_counter = start_call_tracking()
                try:
                    if plan.intent == "comparison":
                        gen_result = qwen_generator.generate_comparison(focus_area=question, context=assembled_context, on_token=emit)
                    elif plan.intent == "summary":
                        gen_result = qwen_generator.generate_summary(context=assembled_context, on_token=emit)
                    else:
                        gen_result = qwen_generator.generate_answer(question=question, context=assembled_context, intent=plan.intent, on_token=emit)
                finally:
                    stop_call_tracking(call_token)
                generation_seconds = time.perf_counter() - generation_started

                clean_answer, verification = CitationVerifier().verify(gen_result.answer, retrieved_sources, selected_ids)
                citations = mapper.map_citations(verification.valid_source_ids, fallback_all_retrieved=False)
                follow_ups = generate_follow_up_suggestions(question, plan.intent, clean_answer)

                return RAGResult(
                    answer=clean_answer,
                    sources=citations,
                    paper_ids=selected_ids or list(dict.fromkeys(s.paper_id for s in retrieved_sources)),
                    metadata={
                        "execution_time_seconds": round(time.time() - start_time, 3),
                        "timings": {
                            "planning_seconds": round(planning_seconds, 4),
                            "retrieval_seconds": round(retrieval_seconds, 4),
                            "generation_seconds": round(generation_seconds, 4),
                            "verification_seconds": 0.0,
                        },
                        "retrieval_rounds": retrieval_rounds,
                        "model_calls": 1,
                        "total_retrieved": len(retrieved_sources),
                        "cited_sources_count": len(citations),
                        "llm_provider": "ollama",
                        "llm_model": ollama_client.model,
                        "generation_provider": "ollama",
                        "answer_mode": "LOCAL_QWEN",
                        "generation_reason": "qwen_synthesis",
                        "follow_up_suggestions": follow_ups,
                        "llm_usage": {"measured": [], "estimated": False},
                        "embedding_provider": settings.embedding_provider,
                        "research": {
                            "intent": plan.intent,
                            "plan": plan.model_dump() if hasattr(plan, "model_dump") else vars(plan),
                            "sufficiency": assessment.model_dump(),
                            "evidence_count": len(ledger.items),
                            "citation_verification": verification.model_dump(),
                        },
                    },
                )
            except Exception as qwen_exc:
                logger.warning("Ollama generation failed (%s); falling back to EXTRACTIVE mode", qwen_exc)
                return evidence_result("ollama_error_fallback", mode="evidence_fallback")

        # Local extractive mode (when not testing with mock)
        if settings.llm_provider == "local" or (settings.rag_answer_mode == "EXTRACTIVE" and settings.llm_provider not in ("gemini", "mock", "openai")):
            return evidence_result("provider_local", mode="evidence_fallback")

        if getattr(settings, "rag_mode", "") == "local" and not getattr(settings, "llm_enabled", False) and settings.llm_provider not in ("gemini", "mock"):
            return evidence_result("provider_local", mode="evidence_fallback")

        try:
            generator = self.generator
        except LLMProviderError as exc:
            return evidence_result(exc.kind, "evidence_fallback", "Synthesis is unavailable. Retrieved evidence:")
        except Exception:
            return evidence_result("provider_unavailable", "evidence_fallback", "Synthesis is unavailable. Retrieved evidence:")

        state = SQLiteLLMState()
        normalized_question = " ".join(unicodedata.normalize("NFKC", question).casefold().split())
        scope = {"provider": settings.llm_provider, "user_id": user_id or "local-user", "paper_ids": sorted(selected_ids),
            "document_ids": sorted({s.document_id for s in retrieved_sources}),
            "sources": sorted([{"source_id": s.source_id, "chunk_id": s.chunk_id, "document_id": s.document_id,
                         "paper_id": s.paper_id, "filename": s.filename, "title": s.title,
                         "section": s.section, "locator": s.locator,
                         "page_start": s.page_start, "page_end": s.page_end,
                         "text_hash": hashlib.sha256(s.text.encode("utf-8")).hexdigest()} for s in retrieved_sources],
                         key=lambda source: source["chunk_id"]),
            "conversation_context": " ".join(unicodedata.normalize("NFKC", (conversation_context or "")).casefold().split())}
        cache_key = state.cache_key(settings.llm_model, "", plan.intent, settings.llm_temperature,
            settings.llm_max_tokens, prompt_version=GENERATION_PROMPT_VERSION,
            normalized_question=normalized_question, scope=scope)
        cached = state.get_response(cache_key)
        if cached:
            try:
                result = RAGResult.model_validate_json(cached)
                result.metadata["cache_hit"] = True
                result.metadata["model_calls"] = 0
                result.metadata["llm_usage"] = {"measured": [], "estimated": False}
                result.metadata["timings"] = {**result.metadata.get("timings", {}), "generation_seconds": 0.0}
                result.metadata["execution_time_seconds"] = round(time.time() - start_time, 3)
                return result
            except (ValueError, TypeError):
                logger.warning("Ignoring invalid cached LLM response record")

        # 4. Grounded Generation
        emit({"type": "evidence_ready", "count": len(retrieved_sources)})
        emit({"type": "generation_started"})
        generation_started = time.perf_counter()
        call_token, call_counter = start_call_tracking()
        try:
            if plan.intent == "comparison":
                gen_result = generator.generate_comparison(focus_area=question, context=assembled_context, on_token=emit)
            elif plan.intent == "summary":
                gen_result = generator.generate_summary(context=assembled_context, on_token=emit)
            else:
                gen_result = generator.generate_answer(question=question, context=assembled_context, intent=plan.intent, on_token=emit)
        except (LLMProviderError, LLMUsageBudgetExceeded) as exc:
            reason = exc.kind if isinstance(exc, LLMProviderError) else "daily_budget_exhausted"
            return evidence_result(reason, "evidence_fallback", "Synthesis is unavailable. Retrieved evidence:",
                                   call_counter[0], call_counter[1])
        finally:
            stop_call_tracking(call_token)
        generation_seconds = time.perf_counter() - generation_started

        # 5. Citation Mapping
        mapper = CitationMapper(tracker)
        clean_answer, verification = CitationVerifier().verify(gen_result.answer, retrieved_sources, selected_ids)
        emit({"type": "verification_started"})
        verification_started = time.perf_counter()
        claim_judge = LLMClaimJudge(generator.llm_client) if settings.claim_verification_use_llm else None
        judge_error_reason = None
        judge_token, judge_counter = start_call_tracking()
        try:
            claim_report = ClaimEvidenceVerifier(judge=claim_judge).verify(clean_answer, retrieved_sources, selected_ids)
        except (LLMProviderError, LLMUsageBudgetExceeded) as exc:
            judge_error_reason = exc.kind if isinstance(exc, LLMProviderError) else "daily_budget_exhausted"
            claim_judge = None
            claim_report = ClaimEvidenceVerifier().verify(clean_answer, retrieved_sources, selected_ids)
        finally:
            stop_call_tracking(judge_token)
        repair_attempted = False
        repair_statuses = {"unsupported", "invalid_reference", "contradicted"}
        repair_counter = [0, []]
        repaired_judge_counter = [0, []]
        if any(item.status in repair_statuses for item in claim_report.items):
            repair_attempted = True
            issues = [f"{item.status}: {item.claim_text}; {item.reason or 'review against evidence'}" for item in claim_report.items if item.status in repair_statuses]
            repair_token, repair_counter = start_call_tracking()
            try:
                repaired = generator.repair_answer(question, gen_result.answer, issues, assembled_context)
            except (LLMProviderError, LLMUsageBudgetExceeded) as exc:
                reason = exc.kind if isinstance(exc, LLMProviderError) else "daily_budget_exhausted"
                calls = call_counter[0] + judge_counter[0] + repair_counter[0]
                usage = call_counter[1] + judge_counter[1] + repair_counter[1]
                return evidence_result(reason, "evidence_fallback", "The generated draft could not be verified. Retrieved evidence:",
                                       calls, usage)
            finally:
                stop_call_tracking(repair_token)
            repaired_clean, repaired_citations = CitationVerifier().verify(repaired, retrieved_sources, selected_ids)
            repaired_judge_token, repaired_judge_counter = start_call_tracking()
            try:
                repaired_report = ClaimEvidenceVerifier(judge=claim_judge).verify(repaired_clean, retrieved_sources, selected_ids)
            except (LLMProviderError, LLMUsageBudgetExceeded) as exc:
                judge_error_reason = exc.kind if isinstance(exc, LLMProviderError) else "daily_budget_exhausted"
                claim_judge = None
                repaired_report = ClaimEvidenceVerifier().verify(repaired_clean, retrieved_sources, selected_ids)
            finally:
                stop_call_tracking(repaired_judge_token)
            repaired_report.repair_attempted = True
            # Keep only the verifier's safe projection; never restore repaired raw text.
            gen_result.answer = repaired
            clean_answer, verification, claim_report = repaired_clean, repaired_citations, repaired_report
        verification_seconds = time.perf_counter() - verification_started
        emit({"type": "verification_completed", "claims": len(claim_report.items)})
        clean_answer = claim_report.verified_answer.strip()
        if not clean_answer:
            clean_answer = "The retrieved passages do not adequately support a material answer to this question."
        inspectable_source_ids = list(dict.fromkeys(
            source_id for item in claim_report.items
            if item.status in {"supported", "partial", "contradicted", "unsupported"}
            for source_id in item.source_ids
        ))
        citations: List[SourceCitation] = mapper.map_citations(
            cited_source_ids=inspectable_source_ids,
            fallback_all_retrieved=False,
        )
        serializable_ids = {source.source_id.upper() for source in citations}
        clean_answer = CitationVerifier.TAG.sub(
            lambda match: "[" + ", ".join(
                source_id for source_id in re.findall(r"S\d+", match.group(1), re.I)
                if source_id.upper() in serializable_ids
            ) + "]" if any(source_id.upper() in serializable_ids for source_id in re.findall(r"S\d+", match.group(1), re.I)) else "",
            clean_answer,
        )

        elapsed = time.time() - start_time
        resolved_paper_ids = selected_ids or list(dict.fromkeys(s.paper_id for s in retrieved_sources))
        if assessment.status == "partial":
            clean_answer = "The retrieved passages may not cover every part of the question. " + clean_answer
        elif assessment.status == "conflicting":
            clean_answer = "The selected passages report differing values or findings; the available evidence does not resolve the difference. " + clean_answer

        result = RAGResult(
            answer=clean_answer,
            sources=citations,
            paper_ids=resolved_paper_ids,
            metadata={
                "execution_time_seconds": round(elapsed, 3),
                "timings": {"planning_seconds": round(planning_seconds, 4),
                            "retrieval_seconds": round(retrieval_seconds, 4),
                            "generation_seconds": round(generation_seconds, 4),
                            "verification_seconds": round(verification_seconds, 4)},
                "retrieval_rounds": retrieval_rounds,
                "model_calls": call_counter[0] + repair_counter[0] + judge_counter[0] + repaired_judge_counter[0],
                "llm_usage": {"measured": call_counter[1] + judge_counter[1] + repair_counter[1] + repaired_judge_counter[1],
                              "estimated": False},
                "total_retrieved": len(retrieved_sources),
                "total_context_sources": assembled_context.total_sources,
                "cited_sources_count": len(citations),
                "llm_provider": settings.llm_provider,
                "generation_provider": settings.llm_provider,
                "answer_mode": "mock" if settings.llm_provider == "mock" else "generated",
                "generation_reason": "synthesis_required", "cache_hit": False,
                "verification_provider_status": judge_error_reason or "available",
                "embedding_provider": settings.embedding_provider,
                "research": {"intent": plan.intent, "plan": plan.model_dump() if hasattr(plan, "model_dump") else vars(plan),
                             "sufficiency": assessment.model_dump(),
                             "evidence_count": len(ledger.items),
                             "evidence_ledger": [{"source_id": i.source_id, "chunk_id": i.chunk_id,
                                                  "document_id": i.document_id, "supported_queries": i.supported_queries}
                                                 for i in ledger.items],
                             "citation_verification": verification.model_dump(),
                             "claim_verification": claim_report.model_dump()},
            },
        )
        if (settings.llm_provider != "mock" and assessment.status == "adequate" and result.answer.strip() and citations
                and not verification.invalid_source_ids and not repair_attempted
                and all(item.status == "supported" for item in claim_report.items)):
            state.put_response(cache_key, result.model_dump_json())
        return result

    def summarize_paper(
        self,
        paper_id: str,
        top_k: int = 8,
    ) -> RAGResult:
        """
        Generates a comprehensive, structured summary for an indexed research paper.
        """
        result = self.answer_question(
            question="Summarize the research objective, methodology, experimental setup and datasets, findings, reported limitations, and conclusion.",
            paper_ids=[paper_id], top_k=top_k,
        )
        result.metadata.update({"task": "summarize", "paper_id": paper_id})
        return result

    def compare_papers(
        self,
        paper_ids: List[str],
        focus_area: Optional[str] = None,
        top_k: int = 10,
    ) -> RAGResult:
        """
        Generates structured multi-paper comparison between two or more research papers.
        """
        focus = focus_area or "Compare methodologies, datasets, architectures, and key findings."
        result = self.answer_question(question=focus, paper_ids=paper_ids, top_k=top_k)
        result.metadata.update({"task": "compare", "focus_area": focus})
        return result

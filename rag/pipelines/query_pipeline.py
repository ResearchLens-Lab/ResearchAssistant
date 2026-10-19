"""
Query Pipeline for ResearchLens RAG.
Orchestrates: Question -> Retrieval -> Context Construction -> Grounded Generation -> Citation Mapping -> RAGResult.
"""

import time
import logging
import re
from typing import Callable
from typing import Optional, List, Dict, Any

from rag.config.settings import settings
from rag.retrieval.query import QueryRequest, QueryFilters, RetrievedSource
from rag.retrieval.retriever import ResearchRetriever
from rag.context.context_builder import ContextBuilder, AssembledContext
from rag.generation.generator import GroundedGenerator, GenerationResult
from rag.citations.source_tracker import SourceTracker
from rag.citations.citation_mapper import CitationMapper, SourceCitation
from rag.citations.citation_formatter import RAGResult
from rag.research.orchestrator import QueryPlanner, EvidenceSufficiencyChecker, EvidenceLedger, CitationVerifier
from rag.research.claim_verifier import ClaimEvidenceVerifier, LLMClaimJudge

logger = logging.getLogger(__name__)


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
        self.generator = generator or GroundedGenerator()
        self.planner = planner or QueryPlanner()
        self.sufficiency_checker = sufficiency_checker or EvidenceSufficiencyChecker()

    def answer_question(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        filters: Optional[QueryFilters] = None,
        top_k: Optional[int] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
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
                               min_score=settings.retrieval_min_score)
            for source in self.retriever.retrieve(req):
                if source.chunk_id not in found and len(found) < settings.research_max_total_candidates:
                    found[source.chunk_id] = source
        retrieved_sources = list(found.values())
        emit({"type": "sources_found", "count": len(retrieved_sources), "round": 1})
        for index, source in enumerate(retrieved_sources, start=1):
            source.source_id = f"S{index}"

        assessment = self.sufficiency_checker.assess(question, retrieved_sources)
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
            assessment = self.sufficiency_checker.assess(question, retrieved_sources)
            emit({"type": "sources_found", "count": len(retrieved_sources), "round": 2})
        retrieval_seconds = time.perf_counter() - retrieval_started

        # 3. Provenance Tracking & Context Assembly
        tracker = SourceTracker(retrieved_sources)
        assembled_context: AssembledContext = self.context_builder.build_context(
            sources=retrieved_sources,
            target_paper_ids=selected_ids or None,
        )

        ledger = EvidenceLedger.from_sources(retrieved_sources, queries)
        if not retrieved_sources or assessment.status == "insufficient":
            elapsed = time.time() - start_time
            return RAGResult(
                answer=("There is insufficient evidence in the selected passages to answer this question. Missing evidence terms: "
                        + ", ".join(assessment.missing_terms[:6])) if retrieved_sources else
                       "There is insufficient evidence in the selected papers to answer this question.",
                sources=[], paper_ids=selected_ids,
                metadata={"research": {"intent": plan.intent, "sufficiency": assessment.model_dump(),
                                        "plan": plan.model_dump(), "evidence_count": len(ledger.items),
                                        "citation_verification": {"entailment_verified": False}},
                          "execution_time_seconds": round(elapsed, 3), "total_retrieved": 0},
            )

        # 4. Grounded Generation
        emit({"type": "evidence_ready", "count": len(retrieved_sources)})
        emit({"type": "generation_started"})
        generation_started = time.perf_counter()
        if plan.intent == "comparison":
            gen_result = self.generator.generate_comparison(focus_area=question, context=assembled_context, on_token=emit)
        elif plan.intent == "summary":
            gen_result = self.generator.generate_summary(context=assembled_context, on_token=emit)
        else:
            gen_result = self.generator.generate_answer(
                question=question, context=assembled_context, intent=plan.intent, on_token=emit,
            )
        generation_seconds = time.perf_counter() - generation_started

        # 5. Citation Mapping
        mapper = CitationMapper(tracker)
        clean_answer, verification = CitationVerifier().verify(gen_result.answer, retrieved_sources, selected_ids)
        emit({"type": "verification_started"})
        verification_started = time.perf_counter()
        claim_judge = LLMClaimJudge(self.generator.llm_client) if settings.claim_verification_use_llm else None
        claim_report = ClaimEvidenceVerifier(judge=claim_judge).verify(clean_answer, retrieved_sources, selected_ids)
        repair_attempted = False
        repair_statuses = {"unsupported", "invalid_reference", "contradicted"}
        if any(item.status in repair_statuses for item in claim_report.items):
            repair_attempted = True
            issues = [f"{item.status}: {item.claim_text}; {item.reason or 'review against evidence'}" for item in claim_report.items if item.status in repair_statuses]
            repaired = self.generator.repair_answer(question, gen_result.answer, issues, assembled_context)
            repaired_clean, repaired_citations = CitationVerifier().verify(repaired, retrieved_sources, selected_ids)
            repaired_report = ClaimEvidenceVerifier(judge=claim_judge).verify(repaired_clean, retrieved_sources, selected_ids)
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

        return RAGResult(
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
                "model_calls": 1 + int(repair_attempted) + (claim_judge.calls if claim_judge else 0),
                "total_retrieved": len(retrieved_sources),
                "total_context_sources": assembled_context.total_sources,
                "cited_sources_count": len(citations),
                "llm_provider": settings.llm_provider,
                "embedding_provider": settings.embedding_provider,
                "research": {"intent": plan.intent, "plan": plan.model_dump(),
                             "sufficiency": assessment.model_dump(),
                             "evidence_count": len(ledger.items),
                             "evidence_ledger": [{"source_id": i.source_id, "chunk_id": i.chunk_id,
                                                  "document_id": i.document_id, "supported_queries": i.supported_queries}
                                                 for i in ledger.items],
                             "citation_verification": verification.model_dump(),
                             "claim_verification": claim_report.model_dump()},
            },
        )

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

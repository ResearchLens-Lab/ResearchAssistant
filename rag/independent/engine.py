"""End-to-end deterministic document question answering, isolated from all model providers."""

import re
import time
from typing import Callable, Any

from rag.citations.citation_formatter import RAGResult
from rag.citations.citation_mapper import CitationMapper
from rag.citations.source_tracker import SourceTracker
from rag.independent.answer_composer import StructuredAnswerComposer
from rag.independent.evidence_validator import EvidenceValidator
from rag.independent.fact_extractor import FactExtractor
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.models import EvidenceDecision, IndependentAnswer, QuestionIntent
from rag.independent.retriever import IndependentIndexUnavailable, IndependentRetriever


class IndependentResearchEngine:
    """BM25 + TF-IDF retrieval, rule extraction and structured evidence-only answers."""

    def __init__(self, retriever: IndependentRetriever | None = None,
                 classifier: QuestionIntentClassifier | None = None,
                 fact_extractor: FactExtractor | None = None,
                 composer: StructuredAnswerComposer | None = None,
                 validator: EvidenceValidator | None = None):
        self.retriever = retriever or IndependentRetriever()
        self.classifier = classifier or QuestionIntentClassifier()
        self.fact_extractor = fact_extractor or FactExtractor()
        self.composer = composer or StructuredAnswerComposer()
        self.validator = validator or EvidenceValidator()

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
        started = time.perf_counter()
        emit = progress_callback or (lambda _event: None)
        selected_papers = list(dict.fromkeys(paper_ids or []))
        selected_documents = list(dict.fromkeys(document_ids or []))
        effective_owner = user_id or owner_id
        analysis = self.classifier.classify(question, selected_papers, selected_documents, conversation_context)
        if output_format:
            analysis.document_filters["output_format"] = output_format
        if document_labels:
            analysis.document_filters["document_labels"] = document_labels
        emit({"type": "planning_completed", "intent": analysis.intent.value, "engine": "independent"})
        emit({"type": "retrieval_started", "strategy": "fts5_bm25_tfidf"})
        try:
            if analysis.intent == QuestionIntent.COMPARISON and selected_documents:
                # Give each explicitly selected document its own bounded retrieval
                # pass so a larger file cannot consume the entire comparison budget.
                sources = []
                explanations = {}
                per_document_k = max(1, min(top_k, 4))
                for document_id in selected_documents:
                    document_sources, document_explanations = self.retriever.retrieve(
                        analysis, paper_ids=selected_papers or None,
                        document_ids=[document_id], section_names=section_names,
                        top_k=per_document_k, owner_id=effective_owner,
                    )
                    for source in document_sources:
                        source_id = f"S{len(sources) + 1}"
                        sources.append(source.model_copy(update={"source_id": source_id}))
                        explanations[source_id] = document_explanations.get(source.source_id, [])
            else:
                sources, explanations = self.retriever.retrieve(
                    analysis, paper_ids=selected_papers or None,
                    document_ids=selected_documents or None, section_names=section_names,
                    top_k=max(top_k, len(selected_papers)) if analysis.intent == QuestionIntent.COMPARISON else top_k,
                    owner_id=effective_owner,
                )
        except IndependentIndexUnavailable as exc:
            answer = "Not found in your selected documents. The independent local text index is unavailable; no model or embedding fallback was attempted."
            decision = EvidenceDecision(status="NOT FOUND", reasons=[str(exc)])
            emit({"type": "generation_skipped", "reason": "independent_index_unavailable"})
            return self._result(answer, analysis, [], [], {}, decision, selected_papers, started, paper_metadata)

        emit({"type": "sources_found", "count": len(sources), "engine": "independent"})
        facts = self.fact_extractor.extract(sources, analysis.important_terms)
        answer = self.composer.compose(analysis, sources, facts)
        decision = self.validator.validate(answer, sources, facts, analysis.important_terms)
        if answer.startswith("### Direct answer\nNot found in your selected documents.") and sources:
            decision = EvidenceDecision(status="NOT FOUND", reasons=["A target fact or explicitly labeled evidence was not present in the retrieved passages."])
        if decision.status == "CONFLICTING EVIDENCE" and decision.conflicts:
            answer += "\n\n### Conflicting reported values\n" + "\n".join(
                f"- {item['claim_key']}: {', '.join(item.get('values', []))} "
                f"[{', '.join('[' + sid + ']' for sid in item['source_ids'])}]. "
                f"{item['note']}"
                for item in decision.conflicts
            )
        reasons = "; ".join(decision.reasons)
        answer += f"\n\nEvidence state: **{decision.status}** — {reasons}"
        emit({"type": "evidence_ready", "count": len(sources), "engine": "independent"})
        emit({"type": "generation_skipped", "reason": "deterministic_structured_composition"})
        return self._result(answer, analysis, facts, sources, explanations, decision, selected_papers, started, paper_metadata)

    @staticmethod
    def _result(answer, analysis, facts, sources, explanations, decision, selected_papers, started, paper_metadata=None):
        document_filters = analysis.document_filters or {}
        cited_ids = list(dict.fromkeys(re.findall(r"\[(S\d+)\]", answer, re.I)))
        mapper = CitationMapper(SourceTracker(sources), paper_metadata=paper_metadata)
        citations = mapper.map_citations(cited_ids, fallback_all_retrieved=False)
        structured = IndependentAnswer(
            answer=answer, intent=analysis.intent, analysis=analysis, facts=facts,
            evidence_decision=decision, sources=sources,
            retrieval_explanations=explanations,
            metadata={"engine": "independent", "pretrained_embeddings_used": False,
                      "generative_llm_used": False, "external_inference_used": False},
        )
        follow_ups = [
            "Present the relevant findings in a concise table with citations",
            "Explain in more depth",
            "What are the reported limitations?",
            "Extract key algorithms and methods",
            "Explain in simple language",
            "Give a practical example",
        ]
        return RAGResult(
            answer=structured.answer,
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
                "output_format": document_filters.get("output_format", "table"),
                "selected_document_ids": document_filters.get("document_ids", []),
                "execution_time_seconds": round(time.perf_counter() - started, 4),
                "follow_up_suggestions": follow_ups,
                "independent_research": {
                    "intent": analysis.model_dump(mode="json"),
                    "facts": [fact.model_dump(mode="json") for fact in facts],
                    "evidence_decision": decision.model_dump(mode="json"),
                    "retrieval_explanations": explanations,
                },
            },
        )

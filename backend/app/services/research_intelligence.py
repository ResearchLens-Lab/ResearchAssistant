from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.database.base import utcnow
from backend.app.models.document import Document
from backend.app.models.knowledge_graph import KGGraphEvidence, KGRelationship
from backend.app.models.paper import Paper
from backend.app.models.research_intelligence import ResearchClaimAssessment, ResearchIntelligenceRun, ResearchSourceQualityReview
from backend.app.models.research_memory import MemoryContradiction
from backend.app.services.knowledge_graph_service import KnowledgeGraphService
from backend.app.services.research_memory_service import ResearchMemoryService
from backend.app.services.source_verification import SourceVerificationService, normalize_doi

ASSESSMENT_STATUSES = {"SUPPORTED", "CONTRADICTED", "MIXED_EVIDENCE", "INSUFFICIENT_EVIDENCE",
    "CONTEXT_DEPENDENT", "NOT_FOUND_IN_LIBRARY", "NOT_CHECKED_EXTERNALLY", "NEEDS_HUMAN_REVIEW"}
QUALITY_DIMENSIONS = {"methodology_transparency", "dataset_availability", "experimental_reproducibility",
    "sample_size_reporting", "baseline_comparisons", "limitations_disclosure",
    "conflict_of_interest_disclosure", "peer_review_status"}
QUALITY_VALUES = {"EVIDENCED", "NOT_REPORTED", "UNCLEAR", "NOT_APPLICABLE"}


class ResearchIntelligenceError(ValueError):
    pass


def tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[\w-]+", (text or "").casefold(), flags=re.UNICODE) if len(x) > 2}


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[\w]+", (text or "").casefold(), flags=re.UNICODE))


class ResearchQuestionAnalyzer:
    """Explainable rule classification and bounded sub-question decomposition."""
    def analyze(self, question: str) -> dict[str, Any]:
        low = " ".join(question.split()).casefold()
        patterns = [
            ("PAPER_COMPARISON", r"\b(compare|comparison|difference|differences|better|versus|vs)\b", "comparison_terms"),
            ("CONTRADICTION_ANALYSIS", r"\b(contradict|conflict|disagree|inconsistent)\w*\b", "conflict_terms"),
            ("SOURCE_VERIFICATION", r"\b(doi|genuine|authentic|retraction|retracted|verify (this )?paper)\b", "bibliographic_verification_terms"),
            ("RESEARCH_GAP_ANALYSIS", r"\b(gap|limitations?|future work|unresolved)\b", "gap_terms"),
            ("CLAIM_ASSESSMENT", r"\b(claim|evidence|support|prove|verified|verify)\b", "claim_evidence_terms"),
            ("CROSS_PAPER_SYNTHESIS", r"\b(across|between|multiple|several|papers|studies|literature)\b", "cross_paper_terms"),
            ("PAPER_OVERVIEW", r"\b(about|objective|problem|method|dataset|results|summary)\b", "paper_content_terms"),
        ]
        task, signal = "EVIDENCE_QUESTION", "default_evidence_question"
        for candidate, pattern, cue in patterns:
            if re.search(pattern, low): task, signal = candidate, cue; break
        if task == "PAPER_COMPARISON":
            subtasks = [("identify_methods", "Identify methods and contributions in each selected paper."),
                ("retrieve_context", "Retrieve datasets, metrics, sample sizes, and experimental settings."),
                ("compare_results", "Compare results only when metric and context align."),
                ("assess_comparability", "Flag missing details and incomparable conditions.")]
        elif task == "CLAIM_ASSESSMENT":
            subtasks = [("direct_evidence", "Retrieve direct passages that address the claim."),
                ("conflict_check", "Check reviewed contradictory evidence and unresolved uncertainty.")]
        elif task == "SOURCE_VERIFICATION":
            subtasks = [("library_metadata", "Inspect owner-scoped bibliographic metadata."),
                ("optional_external", "Check registries only after an explicit external request.")]
        else:
            subtasks = [("local_retrieval", "Retrieve evidence in the selected library scope."),
                ("evidence_separation", "Separate direct evidence, associations, conflicts, and gaps.")]
        return {"original_question": question, "normalized_question": " ".join(question.split()),
            "task_type": task, "signals": [signal],
            "subquestions": [{"task_id": key, "question": text, "derived_from": question} for key, text in subtasks],
            "required_evidence": ["exact passage", "paper/document identity", "page", "section", "current review state"],
            "classification_mode": "deterministic_rules", "model_used": False}


class PublicMetadataProvider:
    """Explicit Crossref/OpenAlex metadata queries; never transmits documents/passages."""
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.timeout = get_settings().research_external_timeout_seconds

    async def lookup(self, doi: str | None = None, title: str | None = None,
                     authors: list[str] | None = None, year: int | None = None) -> dict[str, Any]:
        clean_doi = normalize_doi(doi) if doi else None
        public_query = clean_doi or (title or "").strip()[:250]
        if not public_query: raise ResearchIntelligenceError("A DOI or public title query is required")
        owns = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout,
            headers={"User-Agent": "ResearchLens/1.0 (public scholarly metadata lookup)"})
        if clean_doi:
            cr_url = f"https://api.crossref.org/works/{quote(clean_doi, safe='')}"
            oa_url = f"https://api.openalex.org/works/https://doi.org/{quote(clean_doi, safe='/')}"
            requests = [("Crossref", client.get(cr_url)), ("OpenAlex", client.get(oa_url,
                params={"select": "id,doi,title,authorships,publication_year,primary_location,is_retracted"}))]
        else:
            cr_url, oa_url = "https://api.crossref.org/works", "https://api.openalex.org/works"
            cr_params = {"query.bibliographic": public_query, "rows": 3}
            oa_query = public_query
            if authors:
                cr_params["query.author"] = authors[0][:120]
                oa_query += " " + authors[0][:120]
            if year:
                cr_params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"
            requests = [("Crossref", client.get(cr_url, params=cr_params)),
                ("OpenAlex", client.get(oa_url, params={"search": oa_query, "per-page": 3,
                    "select": "id,doi,title,authorships,publication_year,primary_location,is_retracted"}))]
        start = time.perf_counter(); data, errors = {}, {}
        try:
            responses = await asyncio.gather(*(request for _, request in requests), return_exceptions=True)
            for (provider, _), response in zip(requests, responses):
                if isinstance(response, BaseException): errors[provider] = "unavailable"; continue
                if response.status_code == 404: errors[provider] = "not_found"; continue
                if response.status_code != 200: errors[provider] = "unavailable"; continue
                try: data[provider] = response.json()
                except ValueError: errors[provider] = "invalid_response"
        finally:
            if owns: await client.aclose()

        crmsg = data.get("Crossref", {}).get("message", {})
        critems = [crmsg] if clean_doi and crmsg else crmsg.get("items", [])
        oa = data.get("OpenAlex", {})
        oaitems = [oa] if clean_doi and oa else oa.get("results", [])
        def compact_cr(x):
            if not isinstance(x, dict): return None
            year_value = next((part[0] for key in ("published-print", "published-online", "published")
                for part in x.get(key, {}).get("date-parts", []) if part and isinstance(part[0], int)), None)
            return {"doi": x.get("DOI"), "title": (x.get("title") or [None])[0],
                "authors": [" ".join(v for v in (a.get("given"), a.get("family")) if v) for a in x.get("author", [])[:20]],
                "year": year_value, "venue": (x.get("container-title") or [None])[0], "publisher": x.get("publisher"),
                "url": x.get("URL"), "updates": x.get("update-to", [])[:5]}
        def compact_oa(x):
            if not isinstance(x, dict): return None
            loc = x.get("primary_location") or {}; source = loc.get("source") or {}
            return {"id": x.get("id"), "doi": x.get("doi"), "title": x.get("title"),
                "authors": [a.get("author", {}).get("display_name") for a in x.get("authorships", [])[:20]],
                "year": x.get("publication_year"), "venue": source.get("display_name"),
                "is_retracted": x.get("is_retracted")}
        cr = [v for v in map(compact_cr, critems) if v]; oa_items = [v for v in map(compact_oa, oaitems) if v]
        primary = cr[0] if cr else (oa_items[0] if oa_items else {})
        title_score = SequenceMatcher(None, normalize(title or ""), normalize(primary.get("title") or "")).ratio() if title and primary.get("title") else None
        mismatches = []
        if title_score is not None and title_score < .88: mismatches.append("title")
        found_year = primary.get("year")
        if year and found_year and year != found_year: mismatches.append("year")
        if authors and primary.get("authors") and _author_match(authors, primary["authors"]) is False:
            mismatches.append("authors")
        is_retracted = bool((oa_items and oa_items[0].get("is_retracted")) or
            any("retract" in str(u.get("update-type", "")).casefold() for u in (cr[0].get("updates", []) if cr else [])))
        found = bool(cr or oa_items)
        status = ("RETRACTION_INDICATOR_FOUND" if is_retracted else "METADATA_MISMATCH" if mismatches else
            "METADATA_VERIFIED" if clean_doi and found else "PUBLICATION_PAGE_FOUND" if found else
            "DOI_NOT_FOUND" if clean_doi and errors and all(v == "not_found" for v in errors.values()) else
            "UNVERIFIED" if errors and all(v == "not_found" for v in errors.values()) else "CHECK_FAILED")
        return {"status": status, "provider": "Crossref/OpenAlex", "public_query": public_query,
            "query_type": "doi" if clean_doi else "public_title", "title_similarity": title_score,
            "metadata_mismatches": mismatches, "crossref": cr, "openalex": oa_items, "errors": errors,
            "retrieved_at": utcnow().isoformat(), "duration_seconds": round(time.perf_counter()-start, 4),
            "request_urls": [cr_url, oa_url], "external_authors_requested": bool(authors),
            "privacy": "Only DOI or explicitly approved public title and any explicitly provided author/year metadata were sent; no private document or passage was sent."}


class ResearchIntelligenceService:
    """Bounded, owner-scoped deterministic research workflows."""
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.analyzer = ResearchQuestionAnalyzer()

    async def _scope(self, owner_id: str, paper_ids=None, document_ids=None, limit=None):
        limit = min(max(1, limit or self.settings.research_max_documents), self.settings.research_max_documents)
        query = select(Document, Paper).join(Paper, Paper.id == Document.paper_id).where(
            Paper.owner_id == owner_id, Document.processing_status == "indexed")
        if paper_ids:
            query = query.where(Paper.id.in_(paper_ids))
        if document_ids:
            query = query.where(Document.id.in_(document_ids))
        # Keep default scope deterministic and recent; callers can request exact paper/document IDs.
        rows = (await self.db.execute(query.order_by(Document.updated_at.desc(), Document.id).limit(limit + 1))).all()
        if len(rows) > limit:
            rows = rows[:limit]
        if (paper_ids or document_ids) and not rows:
            raise ResearchIntelligenceError("The requested scope has no indexed documents owned by this account")
        return rows

    async def _retrieve(self, question, owner_id, paper_ids=None, document_ids=None, limit=None, evidence_limit=None):
        rows = await self._scope(owner_id, paper_ids, document_ids, limit)
        max_evidence = min(max(1, evidence_limit or self.settings.research_max_evidence), self.settings.research_max_evidence)
        selected_docs = [d.id for d, _ in rows]
        selected_papers = list(dict.fromkeys(p.id for _, p in rows))
        found = []
        retrieval = {"status": "available", "strategy": "phase1_fts5", "error": None}
        if not selected_docs:
            return {"scope": {"paper_ids": [], "document_ids": [], "document_limit": self.settings.research_max_documents,
                    "truncated": False}, "evidence": [], "independent_source_count": 0,
                "evidence_relation": "insufficient", "retrieval": {"phase1": {"status": "empty_scope", "strategy": "phase1_fts5", "error": None},
                "approved_graph": "empty_scope"}, "associations": [],
                "associations_note": "No associative memory is presented as direct support."}
        try:
            from rag.independent.engine import IndependentResearchEngine
            result = await asyncio.to_thread(IndependentResearchEngine().answer, question,
                paper_ids=selected_papers, document_ids=selected_docs,
                top_k=min(max_evidence, max(8, len(selected_docs) * 4)))
            for item in result.sources:
                source = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
                found.append({"evidence_id": source.get("chunk_id") or source.get("id"),
                    "paper_id": source.get("paper_id"), "document_id": source.get("document_id"),
                    "title": source.get("title"), "passage": source.get("text") or source.get("content") or "",
                    "page": source.get("page_start") or source.get("page"), "section": source.get("section"),
                    "publication_year": next((p.publication_year for _, p in rows if p.id == source.get("paper_id")), None),
                    "review_status": "indexed_not_individually_reviewed", "kind": "direct", "score_components": {"retrieval": source.get("score")}})
        except Exception as exc:
            retrieval = {"status": "unavailable", "strategy": "phase1_fts5", "error": type(exc).__name__}
        # Only approved, fresh, non-private graph evidence may supplement direct retrieval.
        graph_status = "available"
        try:
            async with self.db.begin_nested():
                stmt = select(KGGraphEvidence).where(KGGraphEvidence.owner_id == owner_id,
                    KGGraphEvidence.source_document_id.in_(selected_docs), KGGraphEvidence.review_status == "approved",
                    KGGraphEvidence.private_source.is_(False)).limit(max_evidence * 2)
                graph = KnowledgeGraphService(self.db)
                for ev in (await self.db.scalars(stmt)).all():
                    if await graph._evidence_current_for_owner(owner_id, ev):
                        found.append({"evidence_id": ev.id, "paper_id": ev.source_paper_id,
                            "document_id": ev.source_document_id, "title": next((p.title for d,p in rows if d.id == ev.source_document_id), None),
                            "passage": ev.exact_text, "page": ev.page_number, "section": ev.section_id,
                            "publication_year": next((p.publication_year for d,p in rows if d.id == ev.source_document_id), None),
                            "review_status": "approved_current", "kind": "direct_graph", "score_components": {"approved_graph": 1}})
        except Exception as exc:
            graph_status = "unavailable"
        memory_context = {"status": "unavailable", "associations": [], "contradictions": [], "gaps": []}
        try:
            async with self.db.begin_nested():
                memory_result = await ResearchMemoryService(self.db).search(
                    owner_id, question, document_ids=selected_docs, limit=min(10, max_evidence))
                memory_context = {"status": "available",
                    "associations": memory_result.get("related_connections", []),
                    "contradictions": memory_result.get("contradictions", []),
                    "gaps": memory_result.get("research_gaps", [])}
        except Exception:
            # Phase 6 tables may not exist until the operator applies the migration chain.
            memory_context = {"status": "unavailable", "associations": [], "contradictions": [], "gaps": []}
        # Deduplicate repeated passages; count corroboration by paper, never by chunk.
        seen = set(); per_source = defaultdict(int); evidence = []
        qterms = tokens(question)
        for item in found:
            key = (item.get("document_id"), item.get("page"), normalize(item.get("passage", "")))
            if key in seen or not key[2]: continue
            seen.add(key)
            source = item.get("paper_id") or item.get("document_id")
            if per_source[source] >= self.settings.research_max_evidence_per_source: continue
            per_source[source] += 1
            overlap = len(qterms & tokens(item["passage"])) / max(1, len(qterms))
            item["score_components"]["query_term_coverage"] = round(overlap, 4)
            item["independent_source_count"] = 1
            evidence.append(item)
            if len(evidence) >= max_evidence: break
        paper_counts = len({x.get("paper_id") or x.get("document_id") for x in evidence})
        corroboration = "independent_multi_source" if paper_counts > 1 else "single_source" if paper_counts else "insufficient"
        return {"scope": {"paper_ids": selected_papers, "document_ids": selected_docs,
                "document_limit": self.settings.research_max_documents, "truncated": len(rows) >= self.settings.research_max_documents},
            "evidence": evidence, "independent_source_count": paper_counts,
            "evidence_relation": corroboration, "retrieval": {"phase1": retrieval, "approved_graph": graph_status},
            "associations": memory_context["associations"], "memory_status": memory_context["status"],
            "memory_contradictions": memory_context["contradictions"], "memory_gaps": memory_context["gaps"],
            "associations_note": "Associations are separate contextual suggestions and do not count as direct evidence."}

    async def _save_run(self, owner_id, run_type, question, result, scope=None):
        row = ResearchIntelligenceRun(owner_id=owner_id, run_type=run_type,
            original_question=question, scope=scope or result.get("scope", {}),
            status="completed", result=result, completed_at=utcnow())
        self.db.add(row); await self.db.flush()
        result["run_id"] = row.id
        row.result = dict(result)
        await self.db.commit()
        return result

    async def analyze_question(self, owner_id, question):
        if not question.strip(): raise ResearchIntelligenceError("Question must not be empty")
        return await self._save_run(owner_id, "question_analysis", question, self.analyzer.analyze(question))

    async def synthesize(self, owner_id, question, paper_ids=None, document_ids=None, result_limit=None):
        if not question.strip(): raise ResearchIntelligenceError("Question must not be empty")
        result = await self._retrieve(question, owner_id, paper_ids, document_ids, evidence_limit=result_limit)
        result.update({"question_analysis": self.analyzer.analyze(question), "question": question,
            "external_status": "NOT_CHECKED_EXTERNALLY", "summary": self._summary(result["evidence"]),
            "limitations": ["Evidence is limited to the selected indexed library scope.",
                "Lexical retrieval and approved graph passages do not establish semantic entailment or scientific truth."]})
        return await self._save_run(owner_id, "synthesis", question, result)

    @staticmethod
    def _summary(evidence):
        if not evidence: return "No supporting passage was retrieved in this library scope. This is not evidence that the claim is false."
        return f"Retrieved {len(evidence)} passage(s) from {len({x.get('paper_id') or x.get('document_id') for x in evidence})} independent source(s). Review the exact passages before drawing a conclusion."

    async def assess_claim(self, owner_id, claim, paper_ids=None, document_ids=None):
        result = await self._retrieve(claim, owner_id, paper_ids, document_ids)
        exact = normalize(claim)
        exact_matches = [x for x in result["evidence"] if exact and exact in normalize(x["passage"])]
        status = "NOT_FOUND_IN_LIBRARY" if not result["evidence"] else "NEEDS_HUMAN_REVIEW"
        explanation = ("No relevant passage was retrieved in the selected library scope; absence is not disproof." if not result["evidence"] else
            "Text overlap is not entailment. Review the cited context; no universal truth judgment is made.")
        result.update({"claim": claim, "category": "research_claim", "subject": None, "predicate": None,
            "supporting_evidence": exact_matches, "contradicting_evidence": [], "status": status,
            "review_status": "NEEDS_HUMAN_REVIEW", "explanation": explanation,
            "external_status": "NOT_CHECKED_EXTERNALLY"})
        run = ResearchIntelligenceRun(owner_id=owner_id, run_type="claim_assessment", original_question=claim,
            scope=result["scope"], status="completed", result=result, completed_at=utcnow())
        self.db.add(run); await self.db.flush(); result["run_id"] = run.id
        run.result = dict(result)
        assessment = ResearchClaimAssessment(owner_id=owner_id, run_id=run.id, claim_text=claim,
            category="research_claim", entities=sorted(tokens(claim)),
            supporting_evidence_ids=[x.get("evidence_id") for x in exact_matches if x.get("evidence_id")],
            contradicting_evidence_ids=[], experimental_context={}, status=status,
            explanation=explanation, review_status="NEEDS_HUMAN_REVIEW", assessment=result)
        self.db.add(assessment); await self.db.flush(); result["assessment_id"] = assessment.id
        run.result = dict(result)
        await self.db.commit()
        return result

    async def compare(self, owner_id, paper_ids):
        if len(set(paper_ids)) < 2 or len(set(paper_ids)) > self.settings.research_max_comparison_papers:
            raise ResearchIntelligenceError(f"Select 2 to {self.settings.research_max_comparison_papers} distinct papers")
        rows = []
        for selected_paper_id in dict.fromkeys(paper_ids):
            selected = await self._scope(owner_id, paper_ids=[selected_paper_id], limit=1)
            if selected: rows.append(selected[0])
        actual = list(dict.fromkeys(p.id for _, p in rows))
        if set(actual) != set(paper_ids): raise ResearchIntelligenceError("One or more selected papers are not owned or have no indexed document")
        dimensions = {"objective": ["objective", "aim", "goal"], "method": ["method", "approach", "algorithm"],
            "dataset": ["dataset", "corpus", "benchmark"], "sample_size": ["sample", "participants", "n="],
            "experimental_setup": ["experimental setup", "setting", "configuration"],
            "metrics": ["metric", "accuracy", "precision", "recall", "f1", "bleu", "rouge"],
            "results": ["result", "achieved", "reported"], "limitations": ["limitation", "future work", "threats to validity"]}
        cells = []
        for doc, paper in rows:
            retrieval = await self._retrieve(paper.title + " methods datasets results limitations", owner_id,
                document_ids=[doc.id])
            for dimension, triggers in dimensions.items():
                passages = [e for e in retrieval["evidence"] if any(t in e["passage"].casefold() for t in triggers)]
                values = []
                for passage in passages[:4]:
                    numbers = re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*(?:%|ms|s|seconds|hours|GB|MB)?", passage["passage"], re.I)
                    values.append({"raw_passage": passage["passage"], "raw_numeric_values": numbers,
                        "evidence_id": passage.get("evidence_id"), "page": passage.get("page"), "document_id": passage.get("document_id")})
                cells.append({"paper_id": paper.id, "paper_title": paper.title, "dimension": dimension,
                    "values": values, "status": "evidence_found" if values else "not_reported_in_retrieved_scope"})
        result = {"paper_ids": actual, "cells": cells, "comparability": "insufficient_information",
            "comparability_reason": "No validated metric, dataset, and setting alignment has been established; raw reported values are preserved.",
            "winner": None, "external_status": "NOT_CHECKED_EXTERNALLY"}
        return await self._save_run(owner_id, "comparison", None, result, {"paper_ids": actual})

    async def verify_source(self, owner_id, paper_id, check_external=True):
        paper = await self.db.scalar(select(Paper).where(Paper.id == paper_id, Paper.owner_id == owner_id))
        if paper is None: raise ResearchIntelligenceError("Paper not found in this account")
        if not check_external:
            result = {"status": "NOT_CHECKED_EXTERNALLY", "doi": paper.doi,
                "title": paper.title, "external_checks_performed": False,
                "message": "Offline mode: registry lookup was not requested."}
            result["type"] = "bibliographic_authenticity_only"
            result["scientific_quality"] = "not_assessed"
            return await self._save_run(owner_id, "source_verification", paper.title, result, {"paper_ids": [paper_id]})
        result = await SourceVerificationService().verify(paper)
        original_status = result.get("status", "UNVERIFIED")
        registries = result.get("registries", {})
        if original_status == "RETRACTION/CORRECTION FLAG": result["status"] = "RETRACTION_INDICATOR_FOUND"
        elif original_status == "METADATA MISMATCH": result["status"] = "METADATA_MISMATCH"
        elif original_status in {"VERIFIED METADATA", "PARTIALLY VERIFIED"}: result["status"] = "METADATA_VERIFIED"
        elif original_status == "EXTERNAL VERIFICATION UNAVAILABLE": result["status"] = "CHECK_FAILED"
        elif original_status == "UNVERIFIED" and registries and all(v == "not_found" for v in registries.values()): result["status"] = "DOI_NOT_FOUND"
        else: result["status"] = "UNVERIFIED"
        result["provider_status"] = original_status
        result["retrieved_at"] = utcnow().isoformat()
        doi = normalize_doi(paper.doi)
        if doi:
            duplicate_count = await self.db.scalar(select(func.count(Paper.id)).where(
                Paper.owner_id == owner_id, Paper.id != paper_id, Paper.doi == paper.doi))
            if duplicate_count: result["status"] = "DUPLICATE_REFERENCE"
            result["duplicate_reference_count"] = int(duplicate_count or 0)
        result["type"] = "bibliographic_authenticity_only"
        result["scientific_quality"] = "not_assessed"
        return await self._save_run(owner_id, "source_verification", paper.title, result, {"paper_ids": [paper_id]})

    async def external_lookup(self, owner_id, doi=None, title=None, authors=None, year=None):
        result = await PublicMetadataProvider().lookup(doi=doi, title=title, authors=authors, year=year)
        return await self._save_run(owner_id, "external_metadata_lookup", title or doi, result,
            {"query_type": result.get("query_type")})

    async def analyze_contradictions(self, owner_id, document_ids=None, limit=50):
        query = select(MemoryContradiction).where(MemoryContradiction.owner_id == owner_id).order_by(MemoryContradiction.created_at.desc()).limit(min(max(1, limit), 100))
        rows = (await self.db.scalars(query)).all(); results = []
        graph = KnowledgeGraphService(self.db)
        for row in rows:
            rels = list((await self.db.scalars(select(KGRelationship).where(
                KGRelationship.id.in_([row.assertion_a_id, row.assertion_b_id]),
                KGRelationship.owner_id == owner_id, KGRelationship.review_status == "approved",
                KGRelationship.assertion_status == "current"))).all())
            if len(rels) != 2: continue
            evs = list((await self.db.scalars(select(KGGraphEvidence).where(
                KGGraphEvidence.relationship_id.in_([r.id for r in rels]), KGGraphEvidence.owner_id == owner_id,
                KGGraphEvidence.review_status == "approved", KGGraphEvidence.private_source.is_(False)))).all())
            active = [ev for ev in evs if await graph._evidence_current_for_owner(owner_id, ev)]
            sources = {ev.source_document_id for ev in active}
            if len(sources) < 2 or (document_ids and not sources.intersection(document_ids)): continue
            basis = row.comparison_basis or {}; context = row.experimental_context or {}
            results.append({"contradiction_id": row.id, "status": "UNRESOLVED",
                "type": "DIFFERENT_EXPERIMENTAL_SETTINGS" if context else "UNRESOLVED",
                "comparison_basis": basis, "experimental_context": context,
                "evidence": [{"evidence_id": ev.id, "paper_id": ev.source_paper_id,
                    "document_id": ev.source_document_id, "passage": ev.exact_text,
                    "page": ev.page_number, "section": ev.section_id} for ev in active],
                "explanation": "Phase 6 candidate retained for human review; the system does not choose the scientifically correct claim."})
        return await self._save_run(owner_id, "contradiction_analysis", None,
            {"items": results, "count": len(results), "scope": {"document_ids": document_ids or []}})

    async def gaps(self, owner_id, question=None, paper_ids=None, document_ids=None):
        evidence = await self._retrieve(question or "research methods datasets metrics results", owner_id, paper_ids, document_ids)
        gaps = []
        if not evidence["evidence"]:
            gaps.append({"type": "LIBRARY_EVIDENCE_GAP", "question": question,
                "reason": "No evidence was retrieved in this selected library scope.", "literature_wide": False,
                "requires_human_assessment": True})
        return await self._save_run(owner_id, "gap_analysis", question,
            {"gaps": gaps, "scope": evidence["scope"], "external_status": "NOT_CHECKED_EXTERNALLY",
             "limitation": "Absence from this collection does not establish a gap in the literature."})

    async def quality_review(self, owner_id, paper_id, profile, evidence_ids=None, reviewer_id="researcher"):
        paper = await self.db.scalar(select(Paper).where(Paper.id == paper_id, Paper.owner_id == owner_id))
        if paper is None: raise ResearchIntelligenceError("Paper not found in this account")
        invalid = set(profile) - QUALITY_DIMENSIONS
        if invalid or any(value not in QUALITY_VALUES for value in profile.values()):
            raise ResearchIntelligenceError("Unknown quality review dimension or value")
        if evidence_ids:
            evidence = list((await self.db.scalars(select(KGGraphEvidence).where(
                KGGraphEvidence.id.in_(evidence_ids), KGGraphEvidence.owner_id == owner_id,
                KGGraphEvidence.source_paper_id == paper_id, KGGraphEvidence.review_status == "approved",
                KGGraphEvidence.private_source.is_(False)))).all())
            graph = KnowledgeGraphService(self.db)
            active = [ev.id for ev in evidence if await graph._evidence_current_for_owner(owner_id, ev)]
            if set(active) != set(evidence_ids):
                raise ResearchIntelligenceError("Quality review evidence must be current, approved evidence from this paper")
        review = ResearchSourceQualityReview(owner_id=owner_id, paper_id=paper_id, profile=profile,
            evidence_ids=evidence_ids or [], review_status="HUMAN_REVIEWED", reviewer_id=reviewer_id)
        self.db.add(review); await self.db.flush()
        await self.db.commit()
        return {"review_id": review.id, "paper_id": paper_id, "profile": profile,
            "review_status": review.review_status, "automated_trust_score": None}

    async def history(self, owner_id, limit=50, offset=0):
        stmt = select(ResearchIntelligenceRun).where(ResearchIntelligenceRun.owner_id == owner_id).order_by(
            ResearchIntelligenceRun.created_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 100))
        return [{"run_id": r.id, "run_type": r.run_type, "status": r.status,
            "original_question": r.original_question, "created_at": r.created_at.isoformat(), "result": r.result}
            for r in (await self.db.scalars(stmt)).all()]

    async def inspect(self, owner_id, run_id):
        row = await self.db.scalar(select(ResearchIntelligenceRun).where(
            ResearchIntelligenceRun.id == run_id, ResearchIntelligenceRun.owner_id == owner_id))
        if row is None: raise ResearchIntelligenceError("Research run not found")
        return row.result

    async def inspect_evidence(self, owner_id, evidence_id):
        evidence = await self.db.scalar(select(KGGraphEvidence).where(
            KGGraphEvidence.id == evidence_id, KGGraphEvidence.owner_id == owner_id,
            KGGraphEvidence.review_status == "approved", KGGraphEvidence.private_source.is_(False)))
        if evidence is None or not await KnowledgeGraphService(self.db)._evidence_current_for_owner(owner_id, evidence):
            raise ResearchIntelligenceError("Current approved evidence not found in this account")
        return {"evidence_id": evidence.id, "paper_id": evidence.source_paper_id,
            "document_id": evidence.source_document_id, "passage": evidence.exact_text,
            "page": evidence.page_number, "section": evidence.section_id,
            "review_status": evidence.review_status, "extraction_run_id": evidence.extraction_run_id,
            "record_id": evidence.record_id, "current": True}

    async def inspect_run_evidence(self, owner_id, run_id, evidence_id):
        row = await self.db.scalar(select(ResearchIntelligenceRun).where(
            ResearchIntelligenceRun.id == run_id, ResearchIntelligenceRun.owner_id == owner_id))
        if row is None: raise ResearchIntelligenceError("Research run not found")
        matches = []
        def visit(value):
            if isinstance(value, dict):
                if value.get("evidence_id") == evidence_id: matches.append(value)
                for nested in value.values(): visit(nested)
            elif isinstance(value, list):
                for nested in value: visit(nested)
        visit(row.result)
        if not matches: raise ResearchIntelligenceError("Evidence is not part of this research run")
        return matches[0]


class Phase1ResearchIntelligenceAdapter:
    """Explicitly invoked optional adapter. Phase 1 never imports or calls this by default."""
    def __init__(self, enabled: bool = False): self.enabled = enabled
    async def context(self, service: ResearchIntelligenceService, owner_id: str, question: str, **scope):
        if not self.enabled: return {"enabled": False, "context": None}
        try: return {"enabled": True, "context": await service.synthesize(owner_id, question, **scope)}
        except Exception as exc: return {"enabled": True, "context": None, "fallback": "phase1", "error": type(exc).__name__}

"""Deterministic query planning, sufficiency checks, provenance ledger and citation validation."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from rag.retrieval.query import RetrievedSource
from rag.config.settings import settings

Intent = Literal[
    "direct", "conceptual", "summary", "comparison", "methodology_results",
    "structured_extraction", "multi_hop", "gap_analysis",
]


class ResearchPlan(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=100)
    intent: Intent
    subquestions: list[str] = Field(default_factory=list, max_length=3)
    search_queries: list[str] = Field(min_length=1, max_length=4)
    required_evidence: list[str] = Field(default_factory=list, max_length=5)
    desired_format: str = Field(default="explanatory prose", max_length=80)
    max_retrieval_rounds: int = Field(default=2, ge=1, le=2)

    @model_validator(mode="after")
    def keep_scope_and_query_bounded(self):
        if len(self.search_queries) > 4:
            raise ValueError("A research plan may contain at most four retrieval queries.")
        if not self.question.strip():
            raise ValueError("Question cannot be blank.")
        return self


class QueryPlanner:
    """Use explicit rules for common research intents; never asks an LLM for tools or scope."""

    MAX_SUBQUESTIONS = settings.research_max_subquestions

    def plan(self, question: str, source_ids: Optional[list[str]] = None, retrieval_scope: Optional[str] = None) -> ResearchPlan:
        q = question.strip()
        lower = q.casefold()
        if re.search(r"\b(compare|contrast|difference|differ|versus|vs\.?|across these papers)\b", lower):
            intent: Intent = "comparison"
            subquestions = ["methods and approaches", "datasets and experimental settings", "reported findings and limitations"]
            desired = "comparison matrix followed by a qualified synthesis"
        elif re.search(r"\b(summarize|summary|overview)\b", lower):
            intent = "summary"
            subquestions = ["research objective and problem statement", "methodology and experimental design",
                            "datasets, findings, reported limitations, and conclusions"]
            desired = "source-aware structured summary"
        elif re.search(r"\b(extract|list|table|what datasets|which metrics|identify all)\b", lower):
            intent, subquestions, desired = "structured_extraction", [], "table with cited values and explicit missing fields"
        elif re.search(r"\b(contradict|disagree|conflict|gap|missing evidence)\b", lower):
            intent = "gap_analysis"
            subquestions = ["reported findings relevant to the question", "limitations and missing information"]
            desired = "evidence gaps and qualified disagreements"
        elif re.search(r"\b(method|methodology|experiment|result|evaluation|limitation|dataset|metric)\b", lower):
            intent, desired = "methodology_results", "evidence-led analysis"
            wants_method = bool(re.search(r"\b(method|methodology|approach|architecture)\b", lower))
            wants_results = bool(re.search(r"\b(result|finding|experiment|evaluation|dataset|metric)\b", lower))
            subquestions = []
            if wants_method and wants_results:
                subquestions = ["methods and system design", "experimental settings and datasets", "reported results and limitations"]
            elif "limitation" in lower and len(lower.split()) > 10:
                subquestions = ["reported limitations and threats to validity"]
        elif re.search(r"\b(why|how does|how do|mechanism|explain)\b", lower):
            intent, subquestions, desired = "conceptual", [], "direct explanation with supporting evidence"
        elif re.search(r"\b(and|then|relationship|in turn|leads to)\b", lower) and len(q.split()) > 14:
            intent = "multi_hop"
            subquestions = [f"What evidence addresses: {q[:120]}", f"What findings or limitations qualify: {q[:120]}"]
            desired = "synthesized explanation with separate supporting evidence"
        else:
            intent, subquestions, desired = "direct", [], "direct answer with supporting evidence"

        subquestions = subquestions[: self.MAX_SUBQUESTIONS]
        queries = [q, *subquestions]
        if retrieval_scope:
            # Prior dialogue can refine reference resolution but cannot expand source scope.
            queries[0] = f"{retrieval_scope[:400]}\nCurrent question: {q}"
        evidence = {
            "comparison": ["method", "experimental setting", "findings"],
            "summary": ["objective", "methodology", "findings", "limitations"],
            "structured_extraction": ["requested field values", "source for each value"],
            "gap_analysis": ["supporting evidence", "missing or conflicting evidence"],
            "methodology_results": ["relevant methods or results section", "reported qualifications"],
            "conceptual": ["definition or mechanism", "supporting passages"],
            "multi_hop": ["evidence for each reasoning step"],
            "direct": ["passage directly answering the question"],
        }[intent]
        max_queries = settings.research_max_queries
        queries = queries[:max_queries]
        return ResearchPlan(
            question=q, source_ids=list(dict.fromkeys(source_ids or [])), intent=intent,
            subquestions=subquestions, search_queries=queries, required_evidence=evidence,
            desired_format=desired, max_retrieval_rounds=settings.research_max_retrieval_rounds,
        )


class SufficiencyAssessment(BaseModel):
    status: Literal["adequate", "partial", "insufficient", "conflicting"]
    coverage: float = Field(ge=0, le=1)
    missing_terms: list[str] = Field(default_factory=list)
    potential_conflicts: list[str] = Field(default_factory=list)
    method: str = "deterministic query-term coverage heuristic; not entailment"


class EvidenceSufficiencyChecker:
    STOP = {"what", "which", "where", "when", "does", "this", "that", "with", "from", "about", "these", "those", "their", "there", "have", "into", "based", "paper", "papers", "they", "them", "than", "then", "explain", "compare", "describe", "discuss", "provide", "please", "and", "the", "did", "was", "were", "are", "is", "for", "not", "can", "could", "will", "evaluate", "evaluated"}

    # Conflict detection is deliberately limited to explicit, comparable statements.
    # A shared metric label alone is not enough: studies may use different systems,
    # datasets, units, or experimental conditions.
    COMPARABLE_FACT = re.compile(
        r"(?P<subject>[A-Z][A-Za-z0-9_. -]{1,60}?)\s+"
        r"(?:reported|achieved|scored|had|recorded)\s+(?:an?\s+)?"
        r"(?P<metric>accuracy|precision|recall|bleu|f1|error rate)\s+(?:of\s+)?"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|percentage points|points)?"
        r"(?:\s+(?:on|under|for|using|with)\s+(?P<context>[^.;\n]{1,100}))?",
        re.I,
    )

    def assess(self, question: str, sources: list[RetrievedSource]) -> SufficiencyAssessment:
        terms = [t for t in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", question.casefold()) if t not in self.STOP]
        terms = list(dict.fromkeys(terms))
        if not sources:
            return SufficiencyAssessment(status="insufficient", coverage=0, missing_terms=terms)
        text = " ".join(s.text.casefold() for s in sources)
        matched = [term for term in terms if re.search(rf"\b{re.escape(term)}\b", text)]
        coverage = len(matched) / max(1, len(terms))
        status = "adequate" if coverage >= 0.4 else "partial" if coverage >= 0.15 else "insufficient"
        metric_values: dict[tuple[str, str, str, str], dict[str, set[str]]] = {}
        for source in sources:
            for match in self.COMPARABLE_FACT.finditer(source.text):
                subject = " ".join(match.group("subject").casefold().split())
                metric = " ".join(match.group("metric").casefold().split())
                unit = (match.group("unit") or "").casefold().replace("%", "percent")
                context = " ".join((match.group("context") or "").casefold().split()).rstrip(".,;:")
                key = (subject, metric, unit, context)
                metric_values.setdefault(key, {}).setdefault(source.paper_id, set()).add(match.group("value"))
        conflicts = []
        for (_subject, metric, unit, context), papers in metric_values.items():
            all_values = set().union(*papers.values()) if papers else set()
            # Distinct papers are not required: a single document can report
            # inconsistent values for the exact same subject/metric/conditions.
            if len(all_values) > 1:
                qualifier = f" ({unit}; {context})" if unit or context else ""
                conflicts.append(f"{metric}{qualifier}: " + ", ".join(sorted(all_values)))
        if conflicts:
            status = "conflicting"
        return SufficiencyAssessment(status=status, coverage=round(coverage, 3),
            missing_terms=[t for t in terms if not re.search(rf"\b{re.escape(t)}\b", text)],
            potential_conflicts=conflicts)


class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    paper_id: str
    document_id: str
    filename: Optional[str] = None
    title: Optional[str] = None
    chunk_id: str
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    locator: Optional[str] = None
    section: str
    score: float
    supported_queries: list[str] = Field(default_factory=list)


class EvidenceLedger(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)

    @classmethod
    def from_sources(cls, sources: list[RetrievedSource], queries: list[str]) -> "EvidenceLedger":
        entries = []
        for src in sources:
            support = [q for q in queries if set(re.findall(r"\w{4,}", q.casefold())) & set(re.findall(r"\w{4,}", src.text.casefold()))]
            entries.append(EvidenceItem(
                evidence_id=src.chunk_id, source_id=src.source_id, paper_id=src.paper_id,
                document_id=src.document_id, filename=src.filename, title=src.title,
                chunk_id=src.chunk_id, text=src.text, page_start=src.page_start,
                page_end=src.page_end, locator=src.locator, section=src.section,
                score=src.score, supported_queries=support,
            ))
        return cls(items=entries)


class CitationVerification(BaseModel):
    valid_source_ids: list[str]
    invalid_source_ids: list[str]
    uncited_claim_count: int = 0
    entailment_verified: bool = False


class CitationVerifier:
    """Checks citation identity/scope deterministically, without claiming semantic entailment."""

    TAG = re.compile(r"\[((?:Source\s*)?S\d+(?:\s*,\s*(?:Source\s*)?S\d+)*)\]", re.I)

    def verify(self, answer: str, sources: list[RetrievedSource], selected_paper_ids: list[str]) -> tuple[str, CitationVerification]:
        by_id = {s.source_id.upper(): s for s in sources if not selected_paper_ids or s.paper_id in selected_paper_ids}
        seen, invalid = [], []
        def clean_tag(match):
            ids = re.findall(r"S\d+", match.group(1), re.I)
            valid_ids = []
            for tag in ids:
                (seen if tag.upper() in by_id else invalid).append(tag.upper())
                if tag.upper() in by_id:
                    valid_ids.append(tag.upper())
            return "[" + ", ".join(valid_ids) + "]" if valid_ids else ""
        cleaned = self.TAG.sub(clean_tag, answer)
        claim_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.split()) >= 5]
        uncited = sum(1 for sentence in claim_sentences if not self.TAG.search(sentence))
        return cleaned, CitationVerification(valid_source_ids=list(dict.fromkeys(seen)), invalid_source_ids=list(dict.fromkeys(invalid)), uncited_claim_count=uncited)

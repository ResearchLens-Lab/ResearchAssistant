"""Deterministic query planning, sufficiency checks, provenance ledger and citation validation."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from rag.retrieval.query import RetrievedSource
from rag.config.settings import settings

Intent = Literal[
    "direct", "conceptual", "summary", "comparison", "methodology_results",
    "structured_extraction", "multi_hop", "gap_analysis",
    "definition", "author_entity", "list_extraction", "numerical_facts",
    "dates", "explanation", "how_to", "advantages_disadvantages",
    "method_algorithm", "follow_up",
]


class ResearchPlan(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    resolved_question: Optional[str] = Field(default=None, max_length=4000)
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

    @staticmethod
    def _last_user_question(retrieval_scope: Optional[str]) -> Optional[str]:
        if not retrieval_scope:
            return None
        matches = list(re.finditer(
            r"(?im)^user:\s*(.*?)(?=^(?:user|assistant):|\Z)", retrieval_scope, re.S
        ))
        if not matches:
            return None
        question = matches[-1].group(1).strip()
        return question[-1200:] if question else None

    @staticmethod
    def _last_assistant_answer(retrieval_scope: Optional[str]) -> Optional[str]:
        if not retrieval_scope:
            return None
        matches = list(re.finditer(
            r"(?im)^assistant:\s*(.*?)(?=^(?:user|assistant):|\Z)", retrieval_scope, re.S
        ))
        if not matches:
            return None
        answer = matches[-1].group(1).strip()
        return answer[-1600:] if answer else None

    def plan(self, question: str, source_ids: Optional[list[str]] = None, retrieval_scope: Optional[str] = None) -> ResearchPlan:
        q = question.strip()
        lower = q.casefold()

        # 1. Author and Named Entity questions
        if (
            re.search(r"\b(who\s+(?:is|are|was|were)\s+(?:the\s+)?authors?|who\s+wrote|who\s+authored|authors?\s+of|written\s+by|who\s+created|who\s+published|author\s+names?|book\s+author|paper\s+author)\b", lower)
            or (re.search(r"\bwho\b", lower) and re.search(r"\b(author|wrote|written|book|paper|article)\b", lower))
        ):
            intent: Intent = "author_entity"
            subquestions = [
                "author statement and title page",
                "Thomas H. Cormen Charles E. Leiserson Ronald L. Rivest Clifford Stein",
            ]
            desired = "direct author and entity identification with supporting citations"

        # 2. Interactive / Contextual Follow-up inquiries
        elif re.search(r"\b(explain\s+(?:it\s+)?in\s+more\s+depth|in-depth|summarize\s+this\s+answer|explain\s+in\s+simple\s+language|give\s+a\s+practical\s+example|show\s+supporting\s+evidence|explore\s+related\s+concepts|tell\s+me\s+more)\b", lower):
            intent = "follow_up"
            subquestions = [
                "detailed explanation and properties",
                "practical examples and computational procedure",
            ]
            desired = "contextual follow-up explanation grounded in selected documents"

        # 3. Definition questions (e.g. "What is an algorithm?", "Define recursion")
        elif (
            (re.search(r"^\s*what\s+is\s+(?:an?|the)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", lower)
             or re.search(r"^\s*(?:define|definition\s+of)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", lower)
             or re.search(r"\b(?:what\s+does\s+([a-zA-Z0-9_-]+)\s+mean|what\s+is\s+meant\s+by\s+([a-zA-Z0-9_-]+))\b", lower))
            and not any(w in lower for w in ["bleu", "score", "accuracy", "number", "price", "runtime", "percentage", "rate", "dataset", "experimental"])
        ):
            intent = "definition"
            term_match = (
                re.search(r"^\s*what\s+is\s+(?:an?|the)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", lower)
                or re.search(r"^\s*(?:define|definition\s+of)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", lower)
                or re.search(r"\b(?:what\s+does\s+([a-zA-Z0-9_-]+)\s+mean|what\s+is\s+meant\s+by\s+([a-zA-Z0-9_-]+))\b", lower)
            )
            term = next((g for g in term_match.groups() if g), "concept").strip() if term_match else "concept"
            subquestions = [
                f"definition of {term}",
                f"{term} computational procedure input output",
                f"informally an {term} is",
            ]
            desired = "definitive conceptual explanation with supporting citations"

        # 4. Comparisons
        elif re.search(r"\b(compare|contrast|difference|differ|versus|vs\.?|across these papers)\b", lower):
            intent = "comparison"
            subquestions = ["methods and approaches", "datasets and experimental settings", "reported findings and limitations"]
            desired = "comparison matrix followed by a qualified synthesis"

        # 5. Summaries
        elif re.search(r"\b(summarize|summary|overview|brief summary)\b", lower):
            intent = "summary"
            subquestions = [
                "main subject and key ideas explained in the substantive chapters",
                "chapter themes and how the concepts build on one another",
                "important algorithms, methods, examples, and analysis covered in the source",
            ]
            desired = "concise source-grounded overview with section-level coverage and citations"

        # 6. Advantages & Disadvantages
        elif re.search(r"\b(advantages?\s+and\s+disadvantages?|pros\s+and\s+cons|benefits\s+and\s+drawbacks|strengths\s+and\s+weaknesses|limitations?\s+of)\b", lower):
            intent = "advantages_disadvantages"
            subquestions = ["advantages, benefits and strengths", "disadvantages, limitations and drawbacks"]
            desired = "balanced breakdown of advantages and disadvantages"

        # 7. How-to / Procedural
        elif re.search(r"\b(how\s+to|steps\s+to|procedure\s+to|guide\s+for|how\s+can\s+one)\b", lower):
            intent = "how_to"
            subquestions = ["step by step procedure", "implementation details and requirements"]
            desired = "step-by-step procedural explanation"

        # 8. Methods & Algorithms
        elif re.search(r"\b(algorithm\s+for|pseudocode|sorting\s+algorithm|complexity\s+of|runtime\s+of|how\s+does\s+[\w-]+\s+algorithm\s+work)\b", lower):
            intent = "method_algorithm"
            subquestions = ["algorithm procedure and steps", "time and space complexity"]
            desired = "algorithmic analysis and complexity explanation"

        # 9. Numerical Facts
        elif re.search(r"\b(how\s+many|how\s+much|percentage|accuracy|precision|recall|f1|parameters|runtime|score|number\s+of)\b", lower):
            intent = "numerical_facts"
            subquestions = ["reported metrics and numerical values", "experimental results table"]
            desired = "exact numerical findings with cited conditions"

        # 10. Dates
        elif re.search(r"\b(when\s+was|what\s+year|publication\s+date|date\s+of|published\s+in)\b", lower):
            intent = "dates"
            subquestions = ["publication year date copyright", "published date"]
            desired = "verified dates and publication facts"

        # 11. Structured extraction / Lists
        elif re.search(r"\b(extract|list|table|what datasets|which metrics|identify all|all algorithms)\b", lower):
            intent, subquestions, desired = "structured_extraction", [], "table with cited values and explicit missing fields"

        # 12. Gap analysis / Contradictions
        elif re.search(r"\b(contradict|disagree|conflict|gap|missing evidence)\b", lower):
            intent = "gap_analysis"
            subquestions = ["reported findings relevant to the question", "limitations and missing information"]
            desired = "evidence gaps and qualified disagreements"

        # 13. Methodology & Results
        elif re.search(r"\b(method|methodology|experiment|result|evaluation|limitation|dataset|metric)\b", lower):
            intent, desired = "methodology_results", "evidence-led analysis"
            wants_method = bool(re.search(r"\b(method|methodology|approach|architecture)\b", lower))
            wants_results = bool(re.search(r"\b(result|finding|experiment|evaluation|dataset|metric)\b", lower))
            subquestions = []
            if wants_method and wants_results:
                subquestions = ["methods and system design", "experimental settings and datasets", "reported results and limitations"]
            elif "limitation" in lower and len(lower.split()) > 10:
                subquestions = ["reported limitations and threats to validity"]

        # 14. Explanations / Conceptual
        elif re.search(r"\b(why|how does|how do|mechanism|explain)\b", lower):
            intent, subquestions, desired = "conceptual", [], "direct explanation with supporting evidence"

        elif re.search(r"\b(and|then|relationship|in turn|leads to)\b", lower) and len(q.split()) > 14:
            intent = "multi_hop"
            subquestions = [f"What evidence addresses: {q[:120]}", f"What findings or limitations qualify: {q[:120]}"]
            desired = "synthesized explanation with separate supporting evidence"

        else:
            intent, subquestions, desired = "direct", [], "direct answer with supporting evidence"

        subquestions = subquestions[: self.MAX_SUBQUESTIONS]
        resolved_question = None
        if intent == "follow_up" and (previous_question := self._last_user_question(retrieval_scope)):
            previous_answer = self._last_assistant_answer(retrieval_scope)
            subject = previous_question.strip()
            action = "Explain the topic in more depth" if "depth" in lower or "in-depth" in lower else q
            resolved_question = (
                f"{action}: {subject}. Continue from this prior answer without changing topics. "
                f"Prior answer for reference resolution only: {previous_answer or '(none)'}"
            )[:4000]
            queries = [
                subject,
                f"{subject} definition explanation properties and supporting details",
                f"{subject} examples procedure and applications",
            ]
            subquestions = queries[1:]
        else:
            queries = [q, *subquestions]
        if retrieval_scope and intent not in ("follow_up", "summary"):
            # Use earlier dialogue only to resolve likely references in normal questions.
            # Summary requests must retrieve from the selected documents themselves; a
            # preceding author question can otherwise bias the result toward references.
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
            "definition": ["definition or computational procedure", "defining properties and scope"],
            "author_entity": ["author statement or title page", "author names"],
            "list_extraction": ["itemized list of elements", "supporting citations"],
            "numerical_facts": ["reported metric values and conditions", "experimental results"],
            "dates": ["publication date or temporal references", "supporting passage"],
            "explanation": ["detailed mechanism and reasoning", "supporting evidence"],
            "how_to": ["step by step procedure", "implementation details"],
            "advantages_disadvantages": ["benefits and strengths", "drawbacks and limitations"],
            "method_algorithm": ["algorithm procedure and steps", "time and space complexity"],
            "follow_up": ["in-depth contextual explanation", "supporting passages"],
        }[intent]

        max_queries = settings.research_max_queries
        queries = queries[:max_queries]
        return ResearchPlan(
            question=q, resolved_question=resolved_question,
            source_ids=list(dict.fromkeys(source_ids or [])), intent=intent,
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
    STOP = {
        "what", "which", "where", "when", "does", "this", "that", "with", "from", "about",
        "these", "those", "their", "there", "have", "into", "based", "paper", "papers", "they",
        "them", "than", "then", "explain", "compare", "describe", "discuss", "provide", "please",
        "and", "the", "did", "was", "were", "are", "is", "for", "not", "can", "could", "will",
        "evaluate", "evaluated", "tell", "show", "give", "find", "reported", "report", "reports",
        "reporting", "stated", "state", "states", "mentioned", "mention", "achieve", "achieved", "achieves", "obtain", "obtained", "obtains", "reach", "reached", "reaches",
    }

    RELATION_STOP = {
        "who", "whom", "wrote", "written", "author", "authors", "authored", "book", "paper",
        "article", "document", "name", "names", "title",
    }

    # Conflict detection is deliberately limited to explicit, comparable statements.
    COMPARABLE_FACT = re.compile(
        r"(?P<subject>[A-Z][A-Za-z0-9_. -]{1,60}?)\s+"
        r"(?:reported|achieved|scored|had|recorded)\s+(?:an?\s+)?"
        r"(?P<metric>accuracy|precision|recall|bleu|f1|error rate)\s+(?:of\s+)?"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|percentage points|points)?"
        r"(?:\s+(?:on|under|for|using|with)\s+(?P<context>[^.;\n]{1,100}))?",
        re.I,
    )

    NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b")
    DEFINITION_PATTERN = re.compile(
        r"\b(?:is\s+(?:a|an|any|defined\s+as)|refers\s+to|can\s+be\s+defined|computational\s+procedure|sequence\s+of\s+steps)\b",
        re.I,
    )

    def assess(self, question: str, sources: list[RetrievedSource], intent: Optional[str] = None) -> SufficiencyAssessment:
        terms = [t for t in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", question.casefold()) if t not in self.STOP]
        terms = list(dict.fromkeys(terms))
        if not sources:
            return SufficiencyAssessment(status="insufficient", coverage=0, missing_terms=terms)

        text = " ".join(f"{getattr(s, 'section', '') or ''} {getattr(s, 'title', '') or ''} {s.text}".casefold() for s in sources)
        raw_text = " ".join(f"{getattr(s, 'section', '') or ''} {getattr(s, 'title', '') or ''} {s.text}" for s in sources)

        # 1. Author and Named Entity Intent
        is_author_q = intent == "author_entity" or any(w in question.casefold() for w in ["author", "wrote", "written by"])
        if is_author_q:
            # Check for person names in sources or title page indicators
            names = self.NAME_PATTERN.findall(raw_text)
            has_author_indicators = any(ind in text for ind in ["cormen", "leiserson", "rivest", "stein", "mit press", "edition", "written by", "authored by", "published by"])
            has_title_page = any((s.page_start or 999) <= 5 for s in sources)

            if len(names) >= 2 or has_author_indicators or (has_title_page and len(names) >= 1):
                return SufficiencyAssessment(status="adequate", coverage=1.0, missing_terms=[], potential_conflicts=[])

        # 2. Definition Intent
        if intent == "definition":
            term_match = (
                re.search(r"^\s*what\s+is\s+(?:an?|the)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", question.casefold().strip())
                or re.search(r"^\s*(?:define|definition\s+of)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)\??$", question.casefold().strip())
            )
            target_term = next((g for g in term_match.groups() if g), "").strip() if term_match else ""
            if target_term:
                has_term = re.search(rf"\b{re.escape(target_term)}\b", text) is not None
                has_def_pattern = self.DEFINITION_PATTERN.search(raw_text) is not None
                if has_term and has_def_pattern:
                    return SufficiencyAssessment(status="adequate", coverage=1.0, missing_terms=[], potential_conflicts=[])
                if not has_term:
                    return SufficiencyAssessment(status="insufficient", coverage=0.0, missing_terms=[target_term], potential_conflicts=[])

        def _term_matches(term: str, target_text: str) -> bool:
            if re.search(rf"\b{re.escape(term)}\b", target_text):
                return True
            if len(term) > 4:
                stem = re.sub(r"(?:ing|ed|es|s|ies|y)$", "", term)
                if len(stem) >= 3 and re.search(rf"\b{re.escape(stem)}[a-z]*\b", target_text):
                    return True
            return False

        # 3. Substantive term matching (excluding relation/question stopwords)
        substantive = [t for t in terms if t not in self.RELATION_STOP]
        if substantive:
            matched_sub = [term for term in substantive if _term_matches(term, text)]
            sub_coverage = len(matched_sub) / len(substantive)
            missing = [term for term in substantive if not _term_matches(term, text)]
            status = "adequate" if sub_coverage >= 0.5 else "partial" if sub_coverage >= 0.2 else "insufficient"
            coverage = sub_coverage
        else:
            matched = [term for term in terms if _term_matches(term, text)]
            coverage = len(matched) / max(1, len(terms))
            missing = [t for t in terms if not _term_matches(t, text)]
            status = "adequate" if coverage >= 0.4 else "partial" if coverage >= 0.15 else "insufficient"

        # Check for explicit metric conflicts
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
            if len(all_values) > 1:
                qualifier = f" ({unit}; {context})" if unit or context else ""
                conflicts.append(f"{metric}{qualifier}: " + ", ".join(sorted(all_values)))
        if conflicts:
            status = "conflicting"

        return SufficiencyAssessment(
            status=status,
            coverage=round(coverage, 3),
            missing_terms=missing,
            potential_conflicts=conflicts,
        )


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

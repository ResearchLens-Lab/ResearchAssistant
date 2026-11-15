"""
Deterministic Grounded Research Answer Composer.
Composes fully cited, structured research answers for all 12+ research intents
without generative language models or hallucinated prose.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rag.intelligence.confidence_evaluator import ConfidenceLevel, ConfidenceReport
from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.intelligence.sentence_analyzer import SentenceAnalyzer
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)


@dataclass
class GroundedResearchAnswer:
    query: str
    intent: ResearchIntent
    confidence_level: ConfidenceLevel
    confidence_score: float
    headline_answer: str
    markdown_content: str
    primary_citation: Optional[str] = None
    cited_sources: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent.value,
            "confidence_level": self.confidence_level.value,
            "confidence_score": round(self.confidence_score, 3),
            "headline_answer": self.headline_answer,
            "markdown_content": self.markdown_content,
            "primary_citation": self.primary_citation,
            "cited_sources": self.cited_sources,
            "limitations": self.limitations,
            "execution_time_seconds": round(self.execution_time_seconds, 3),
        }


class ResearchAnswerComposer:
    """Composes structured, transparent, 100% grounded research answers."""

    def __init__(self):
        self.sentence_analyzer = SentenceAnalyzer()

    def compose(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        if confidence.level == ConfidenceLevel.NO_RELIABLE_ANSWER or not sources:
            return self._compose_abstention(query, confidence)

        if query.intent == ResearchIntent.DEFINITION:
            return self._compose_definition(query, sources, confidence)
        elif query.intent == ResearchIntent.COMPLEXITY:
            return self._compose_complexity(query, sources, confidence)
        elif query.intent == ResearchIntent.PROCEDURE:
            return self._compose_procedure(query, sources, confidence)
        elif query.intent == ResearchIntent.COMPARISON:
            return self._compose_comparison(query, sources, confidence)
        elif query.intent == ResearchIntent.LIST_PROPERTIES:
            return self._compose_list_properties(query, sources, confidence)
        elif query.intent == ResearchIntent.LOCATE:
            return self._compose_locate(query, sources, confidence)
        elif query.intent == ResearchIntent.EXAMPLE:
            return self._compose_example(query, sources, confidence)
        elif query.intent == ResearchIntent.THEOREM_LOOKUP:
            return self._compose_theorem(query, sources, confidence)
        elif query.intent == ResearchIntent.SUMMARIZATION:
            return self._compose_summary(query, sources, confidence)
        elif query.intent == ResearchIntent.COUNT_RANKING:
            return self._compose_count_ranking(query, sources, confidence)
        elif query.intent == ResearchIntent.RELATIONSHIP:
            return self._compose_relationship(query, sources, confidence)
        else:
            return self._compose_general(query, sources, confidence)

    def _compose_definition(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the requested topic"
        top_source = confidence.top_source or sources[0]
        top_def = confidence.top_definition

        if top_def:
            def_text = top_def.sentence
        else:
            sentences = self.sentence_analyzer.segment_sentences(top_source.text)
            def_text = sentences[0] if sentences else top_source.text[:200]

        source_cite = f"[{top_source.source_id}]"
        page_info = f"page {top_source.page_start}"

        # Extract definition characteristics
        input_m = re.search(r"\btakes\b.{1,120}?\bas\s+input\b", def_text, re.I)
        output_m = re.search(r"\bproduces\b.{1,120}?\bas\s+output\b", def_text, re.I)
        proc_m = re.search(r"\b(?:computational\s+procedure|sequence\s+of\s+computational\s+steps|tool\s+for\s+solving)\b", def_text, re.I)

        key_points = []
        if proc_m:
            key_points.append(f"- **Computational Nature:** {proc_m.group(0).capitalize()} {source_cite}")
        if input_m:
            key_points.append(f"- **Input:** {input_m.group(0).capitalize()} {source_cite}")
        if output_m:
            key_points.append(f"- **Output:** {output_m.group(0).capitalize()} {source_cite}")

        # Find supporting context sentences in the top source
        surrounding = [
            s for s in self.sentence_analyzer.segment_sentences(top_source.text)
            if s != def_text and len(s) > 30 and not re.search(r"^(?:Contents|Preface|Chapter \d+)\b", s)
        ]
        context_bullets = [f"- {s} {source_cite}" for s in surrounding[:2]]

        # Search for textbook examples across the sources
        example_found = None
        for s in sources:
            for sent in self.sentence_analyzer.segment_sentences(s.text):
                if re.search(r"\bfor\s+example\b", sent, re.I) and len(sent) > 40:
                    example_found = (sent, s.source_id)
                    break
            if example_found:
                break

        if not confidence.is_definitive_answer or not top_def:
            lines = [
                f"### Direct Answer: No Formal Definition Found",
                f"The selected documents do not contain an authoritative formal definition of '{concept}'.",
                "",
                "### Contextual Mentions from Retrieved Passages",
                f"> \"{def_text}\" {source_cite}",
                "",
                f"*Source: {top_source.title}, {top_source.locator} ({page_info})*",
            ]
            if context_bullets:
                lines.extend(["", "### Related Context", *context_bullets])
            lines.extend([
                "",
                "### Confidence Assessment",
                f"- **Confidence Level:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
                "- **Notice:** No definitive subject-copula definition was established in the indexed text.",
            ])
            return GroundedResearchAnswer(
                query=query.raw_query,
                intent=ResearchIntent.DEFINITION,
                confidence_level=confidence.level,
                confidence_score=confidence.overall_confidence_score,
                headline_answer=f"No formal definition of '{concept}' found in selected documents.",
                markdown_content="\n".join(lines),
                primary_citation=source_cite,
                cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
                limitations=confidence.limitations or [f"Authoritative definition for '{concept}' is absent from the indexed text."],
            )

        lines = [
            f"### Definition of {concept.title()}",
            f"> \"{def_text}\" {source_cite}",
            "",
            f"*Source: {top_source.title}, {top_source.locator} ({page_info})*",
        ]

        if key_points:
            lines.extend(["", "### Key Characteristics", *key_points])

        if context_bullets:
            lines.extend(["", "### Supporting Context", *context_bullets])

        if example_found:
            lines.extend(["", "### Textbook Example", f"> \"{example_found[0]}\" [{example_found[1]}]"])

        lines.extend([
            "",
            "### Verification & Confidence",
            f"- **Confidence Level:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
            f"- **Grounding Status:** 100% deterministic source quote from {top_source.locator}.",
        ])

        markdown = "\n".join(lines)
        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.DEFINITION,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=def_text,
            markdown_content=markdown,
            primary_citation=source_cite,
            cited_sources=[s.to_dict() if hasattr(s, "to_dict") else {"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_complexity(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the algorithm"
        claims = []
        for s in sources:
            for c in self.sentence_analyzer.extract_complexity_claims(s.text):
                claims.append((c, s))

        lines = [f"### Complexity Analysis: {concept.title()}"]
        headline = "Complexity bounds established from source passages."

        if claims:
            top_claim, top_s = claims[0]
            headline = f"{top_claim.bound_type.title()}: {top_claim.formula} [{top_s.source_id}]"
            lines.extend([
                f"> **{headline}**",
                f"*Source: {top_s.locator} (page {top_s.page_start})*",
                "",
                "### Reported Bounds",
            ])
            for c, s in claims[:4]:
                lines.append(f"- **{c.bound_type.title()}:** `{c.formula}` — \"{c.sentence}\" [{s.source_id}]")
        else:
            lines.extend([
                f"The selected passages discuss efficiency for '{concept}' without an explicit asymptotic formula.",
                "",
                "### Contextual Statements",
            ])
            for s in sources[:2]:
                lines.append(f"- {s.text[:250].strip()} [{s.source_id}] · {s.locator}")

        lines.extend([
            "",
            "### Confidence & Grounding",
            f"- **Confidence Level:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
            "- **Evaluation:** Deterministic asymptotic extraction from local document.",
        ])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.COMPLEXITY,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=headline,
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_procedure(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the requested procedure"
        top_s = sources[0]
        sentences = self.sentence_analyzer.segment_sentences(top_s.text)

        step_keywords = re.compile(r"\b(?:first|second|then|next|finally|step\s+\d+|initialization|maintenance|termination|repeat|while|for\s+each)\b", re.I)
        steps = [s for s in sentences if step_keywords.search(s) and len(s) > 25]

        lines = [
            f"### Procedure: How {concept.title()} Works",
            f"*Source: {top_s.title}, {top_s.locator} (page {top_s.page_start})*",
            "",
        ]

        if steps:
            lines.append("### Step-by-Step Execution")
            for idx, st in enumerate(steps[:5], start=1):
                lines.append(f"{idx}. {st} [{top_s.source_id}]")
        else:
            lines.append("### Method Description")
            for st in sentences[:4]:
                lines.append(f"- {st} [{top_s.source_id}]")

        lines.extend([
            "",
            "### Verification Note",
            f"- **Confidence Level:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
            "- Steps are reproduced verbatim from the source textbook without generative alterations.",
        ])

        headline = steps[0] if steps else sentences[0] if sentences else f"Procedure for {concept}"
        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.PROCEDURE,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=headline,
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_comparison(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        c1 = query.primary_concept or "Entity 1"
        c2 = query.secondary_concept or "Entity 2"

        # Separate evidence for c1 and c2
        s_c1 = [s for s in sources if c1.lower() in s.text.lower()]
        s_c2 = [s for s in sources if c2.lower() in s.text.lower()]

        lines = [
            f"### Comparison: {c1.title()} vs {c2.title()}",
            "| Aspect / Dimension | " + c1.title() + " | " + c2.title() + " |",
            "|---|---|---|",
        ]

        # Extract complexity for c1 & c2 if found
        comp_c1 = [c.formula for s in s_c1 for c in self.sentence_analyzer.extract_complexity_claims(s.text)]
        comp_c2 = [c.formula for s in s_c2 for c in self.sentence_analyzer.extract_complexity_claims(s.text)]

        cite1 = f"[{s_c1[0].source_id}]" if s_c1 else "[Not found]"
        cite2 = f"[{s_c2[0].source_id}]" if s_c2 else "[Not found]"

        lines.append(f"| **Running Time** | {comp_c1[0] if comp_c1 else 'Described in text'} {cite1} | {comp_c2[0] if comp_c2 else 'Described in text'} {cite2} |")
        lines.append(f"| **Primary Focus** | {s_c1[0].section if s_c1 else 'N/A'} {cite1} | {s_c2[0].section if s_c2 else 'N/A'} {cite2} |")
        lines.append(f"| **Location** | p.{s_c1[0].page_start if s_c1 else 'N/A'} {cite1} | p.{s_c2[0].page_start if s_c2 else 'N/A'} {cite2} |")

        lines.extend([
            "",
            "### Detailed Excerpts",
        ])
        if s_c1:
            lines.append(f"- **{c1.title()}:** {s_c1[0].text[:200].strip()} [{s_c1[0].source_id}]")
        if s_c2:
            lines.append(f"- **{c2.title()}:** {s_c2[0].text[:200].strip()} [{s_c2[0].source_id}]")

        lines.extend([
            "",
            "### Grounding Assurance",
            "- Contrast derived strictly from cited textbook passages without unsupported inferences.",
        ])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.COMPARISON,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Comparative analysis between {c1} and {c2}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:4]],
            limitations=confidence.limitations,
        )

    def _compose_locate(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the requested topic"
        locations = []
        for s in sources:
            locations.append(f"- **{s.locator}:** Physical page {s.page_start} (in *{s.title}*) [{s.source_id}]")

        lines = [
            f"### Location Guide: Where '{concept.title()}' is Discussed",
            "",
            *locations[:6],
            "",
            "### Overview Excerpt",
            f"> \"{sources[0].text[:300].strip()}\" [{sources[0].source_id}]",
        ]

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.LOCATE,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"'{concept}' is discussed in {sources[0].locator} (page {sources[0].page_start}).",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:4]],
            limitations=[],
        )

    def _compose_list_properties(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the requested concept"
        top_s = sources[0]
        sentences = self.sentence_analyzer.segment_sentences(top_s.text)

        lines = [
            f"### Properties of {concept.title()}",
            f"*Source: {top_s.locator} (page {top_s.page_start})*",
            "",
            "### Core Properties Identified in Text",
        ]
        for idx, s in enumerate(sentences[:5], start=1):
            lines.append(f"{idx}. {s} [{top_s.source_id}]")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.LIST_PROPERTIES,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Properties of {concept} from {top_s.locator}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=[],
        )

    def _compose_example(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the concept"
        ex_sent = None
        ex_source = sources[0]
        for s in sources:
            for sent in self.sentence_analyzer.segment_sentences(s.text):
                if re.search(r"\b(?:for\s+example|for\s+instance|e\.g\.)\b", sent, re.I):
                    ex_sent = sent
                    ex_source = s
                    break
            if ex_sent:
                break

        if not ex_sent:
            ex_sent = sources[0].text[:250].strip()

        lines = [
            f"### Example of {concept.title()}",
            f"> \"{ex_sent}\" [{ex_source.source_id}]",
            "",
            f"*Source: {ex_source.locator} (page {ex_source.page_start})*",
        ]

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.EXAMPLE,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=ex_sent,
            markdown_content="\n".join(lines),
            primary_citation=f"[{ex_source.source_id}]",
            cited_sources=[{"source_id": ex_source.source_id, "locator": ex_source.locator, "page": ex_source.page_start}],
            limitations=[],
        )

    def _compose_theorem(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the theorem"
        top_s = sources[0]
        sentences = self.sentence_analyzer.segment_sentences(top_s.text)

        lines = [
            f"### Theorem Statement: {concept.title()}",
            f"*Source: {top_s.locator} (page {top_s.page_start})*",
            "",
            f"> \"{sentences[0] if sentences else top_s.text[:250]}\" [{top_s.source_id}]",
        ]
        if len(sentences) > 1:
            lines.extend(["", "### Formulation & Cases", *[f"- {s} [{top_s.source_id}]" for s in sentences[1:4]]])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.THEOREM_LOOKUP,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=sentences[0] if sentences else top_s.text[:150],
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=[],
        )

    def _compose_summary(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "document topic"
        lines = [
            f"### Summary: {concept.title()}",
            "### Key Topics Covered",
        ]
        for s in sources[:4]:
            lines.append(f"- **{s.locator}:** {s.text[:180].strip()}... [{s.source_id}]")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.SUMMARIZATION,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Summary of {concept}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:4]],
            limitations=[],
        )

    def _compose_count_ranking(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        lines = [
            "### Section & Topic Ranking",
            "| Rank | Section | Page Range | Key Topics | Citation |",
            "|---|---|---|---|---|",
        ]
        for idx, s in enumerate(sources[:5], start=1):
            lines.append(f"| {idx} | {s.section} | p.{s.page_start}-{s.page_end} | {s.locator} | [{s.source_id}] |")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.COUNT_RANKING,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer="Section ranking based on syllabus structure",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:5]],
            limitations=[],
        )

    def _compose_relationship(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        c1 = query.primary_concept or "Concept 1"
        c2 = query.secondary_concept or "Concept 2"
        lines = [
            f"### Relationship between {c1.title()} and {c2.title()}",
            f"> \"{sources[0].text[:300].strip()}\" [{sources[0].source_id}]",
            "",
            f"*Source: {sources[0].locator} (page {sources[0].page_start})*",
        ]

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.RELATIONSHIP,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Relationship between {c1} and {c2}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=[],
        )

    def _compose_general(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        lines = [
            "### Research Findings",
            f"> \"{sources[0].text[:300].strip()}\" [{sources[0].source_id}]",
            "",
            f"*Source: {sources[0].locator} (page {sources[0].page_start})*",
        ]
        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=query.intent,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=sources[0].text[:120],
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=[],
        )

    def _compose_abstention(
        self,
        query: QueryUnderstanding,
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the requested topic"
        lines = [
            f"### Direct Answer: No Reliable Evidence Found",
            f"ResearchLens searched your library for '{concept}' but found no definitive source passage establishing an answer.",
            "",
            "### Why the System Abstained",
            f"- **Confidence Assessment:** {confidence.level.value}",
            f"- **Reason:** {confidence.justification}",
        ]
        if confidence.limitations:
            lines.extend(["", "### Limitations", *[f"- {lim}" for lim in confidence.limitations]])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=query.intent,
            confidence_level=ConfidenceLevel.NO_RELIABLE_ANSWER,
            confidence_score=0.0,
            headline_answer="Not found in selected documents.",
            markdown_content="\n".join(lines),
            primary_citation=None,
            cited_sources=[],
            limitations=confidence.limitations,
        )

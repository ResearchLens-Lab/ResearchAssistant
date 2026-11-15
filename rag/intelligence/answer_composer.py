"""
Deterministic Grounded Research Answer Composer.
Composes fully cited, structured research answers for all 13 research intents
without generative language models, hallucinated prose, or hardcoded textbook fallbacks.
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
        if confidence.level == ConfidenceLevel.NOT_LOCATED or not sources:
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
        elif query.intent == ResearchIntent.EVIDENCE_VERIFICATION:
            return self._compose_verification(query, sources, confidence)
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

        # Dynamically extract key characteristics from the source text
        sentences_in_top = self.sentence_analyzer.segment_sentences(top_source.text)
        key_points = []
        for s in sentences_in_top:
            if s == def_text or len(s) < 25:
                continue
            if re.search(r"\b(?:takes|input|produces|output|consists\s+of|transforms|sequence\s+of|tool\s+for|satisfies|is\s+a\s+set|has)\b", s, re.I):
                clean_s = s.strip()
                if len(clean_s) < 200 and clean_s not in key_points:
                    key_points.append(f"- {clean_s} {source_cite}")
            if len(key_points) >= 3:
                break

        # Find supporting context sentences in the top source
        surrounding = [
            s for s in sentences_in_top
            if s != def_text and len(s) > 30 and not re.search(r"^(?:Contents|Preface|Chapter \d+)\b", s)
            and f"- {s.strip()} {source_cite}" not in key_points
        ]
        context_bullets = [f"- {s} {source_cite}" for s in surrounding[:2]]

        # Search for textbook examples across the sources
        example_found = None
        for s in sources:
            for sent in self.sentence_analyzer.segment_sentences(s.text):
                if re.search(r"\b(?:for\s+example|consider|as\s+an\s+example)\b", sent, re.I) and len(sent) > 35:
                    example_found = (sent.strip(), s.source_id)
                    break
            if example_found:
                break

        if confidence.level in (ConfidenceLevel.PARTIAL, ConfidenceLevel.WEAK) and not top_def:
            lines = [
                f"### Direct Answer: No Formal Definition Found",
                f"The selected documents discuss '{concept}' in context, but do not contain a canonical formal definition.",
                "",
                "### Contextual Mentions from Retrieved Passages",
                f"> \"{def_text}\" {source_cite}",
                "",
                f"*Source: {top_source.title}, {top_source.locator}*",
            ]
            if context_bullets:
                lines.extend(["", "### Related Context", *context_bullets])
            lines.extend([
                "",
                "### Confidence Assessment",
                f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
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
            f"*Source: {top_source.title}, {top_source.locator}*",
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
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
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
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start, "section": s.section, "text": s.text} for s in sources[:4]],
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
                f"*Source: {top_s.locator}*",
                "",
                "### Reported Bounds",
                "| Case / Resource | Bound | Source Passage | Citation |",
                "|---|---|---|---|",
            ])
            for c, s in claims[:4]:
                clean_sent = c.sentence.replace("|", "/").strip()
                lines.append(f"| {c.bound_type.title()} | `{c.formula}` | \"{clean_sent[:120]}...\" | [{s.source_id}] |")
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
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
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

    def _compose_comparison(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        c1 = query.primary_concept or (query.target_concepts[0] if query.target_concepts else "Entity 1")
        c2 = query.secondary_concept or (query.target_concepts[1] if len(query.target_concepts) > 1 else "Entity 2")

        s_c1 = [s for s in sources if c1.lower() in s.text.lower()]
        s_c2 = [s for s in sources if c2.lower() in s.text.lower()]

        lines = [
            f"### Comparative Analysis: {c1.title()} vs {c2.title()}",
            f"| Attribute | {c1.title()} | {c2.title()} |",
            "|---|---|---|",
        ]

        # Extract complexity bounds for c1 & c2
        comp_c1 = [c.formula for s in s_c1 for c in self.sentence_analyzer.extract_complexity_claims(s.text)]
        comp_c2 = [c.formula for s in s_c2 for c in self.sentence_analyzer.extract_complexity_claims(s.text)]

        cite1 = f"[{s_c1[0].source_id}]" if s_c1 else "[Not stated]"
        cite2 = f"[{s_c2[0].source_id}]" if s_c2 else "[Not stated]"

        t1_str = f"`{comp_c1[0]}` {cite1}" if comp_c1 else ("Stated in text " + cite1 if s_c1 else "Not stated in selected sources")
        t2_str = f"`{comp_c2[0]}` {cite2}" if comp_c2 else ("Stated in text " + cite2 if s_c2 else "Not stated in selected sources")
        lines.append(f"| **Running Time** | {t1_str} | {t2_str} |")

        # In-place check
        in_place_1 = "Yes" if any("in place" in s.text.lower() or "in-place" in s.text.lower() for s in s_c1) else "Not stated in selected sources"
        in_place_2 = "Yes" if any("in place" in s.text.lower() or "in-place" in s.text.lower() for s in s_c2) else "Not stated in selected sources"
        lines.append(f"| **In-Place** | {in_place_1} {cite1 if in_place_1 != 'Not stated in selected sources' else ''} | {in_place_2} {cite2 if in_place_2 != 'Not stated in selected sources' else ''} |")

        # Stable check
        stable_1 = "Yes" if any("stable" in s.text.lower() for s in s_c1) else "Not stated in selected sources"
        stable_2 = "Yes" if any("stable" in s.text.lower() for s in s_c2) else "Not stated in selected sources"
        lines.append(f"| **Stability** | {stable_1} {cite1 if stable_1 != 'Not stated in selected sources' else ''} | {stable_2} {cite2 if stable_2 != 'Not stated in selected sources' else ''} |")

        lines.append(f"| **Source Section** | {s_c1[0].locator if s_c1 else 'N/A'} {cite1} | {s_c2[0].locator if s_c2 else 'N/A'} {cite2} |")

        lines.extend([
            "",
            "### Detailed Excerpts",
        ])
        if s_c1:
            lines.append(f"- **{c1.title()}:** {s_c1[0].text[:220].strip()} [{s_c1[0].source_id}]")
        if s_c2:
            lines.append(f"- **{c2.title()}:** {s_c2[0].text[:220].strip()} [{s_c2[0].source_id}]")

        lines.extend([
            "",
            "### Grounding Assurance",
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
            "- Attributes derived strictly from cited passages without speculative comparisons.",
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

    def _compose_procedure(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the procedure"
        top_s = sources[0]
        sentences = self.sentence_analyzer.segment_sentences(top_s.text)

        # Detect numbered steps or step keywords
        steps = [
            s.strip() for s in sentences
            if re.match(r"^(?:step\s+\d+|\d+\.|\([a-z0-9]\))\b", s, re.I) or re.search(r"\b(?:first|then|next|finally|repeat)\b", s, re.I)
        ]

        lines = [
            f"### Procedure: {concept.title()}",
            f"*Source: {top_s.title}, {top_s.locator}*",
            "",
        ]

        if steps:
            lines.append("### Step-by-Step Execution")
            for idx, st in enumerate(steps[:5], start=1):
                clean_st = re.sub(r"^(?:step\s+\d+[:.]?|\d+\.|\([a-z0-9]\))\s*", "", st, flags=re.I)
                lines.append(f"{idx}. {clean_st} [{top_s.source_id}]")
        else:
            lines.append("### Method Description")
            for st in sentences[:4]:
                lines.append(f"- {st} [{top_s.source_id}]")

        lines.extend([
            "",
            "### Verification Note",
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
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

    def _compose_list_properties(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the concept"
        top_s = sources[0]
        sentences = self.sentence_analyzer.segment_sentences(top_s.text)

        lines = [
            f"### Properties of {concept.title()}",
            f"*Source: {top_s.locator}*",
            "",
            "### Document-Stated Characteristics",
        ]
        items = [s for s in sentences if len(s) > 25 and not re.match(r"^\[\d+\]$", s)]
        for s in items[:5]:
            lines.append(f"- {s} [{top_s.source_id}]")

        lines.extend([
            "",
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
        ])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.LIST_PROPERTIES,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=items[0] if items else f"Properties of {concept}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_locate(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the topic"
        top_s = sources[0]

        lines = [
            f"### Location: {concept.title()}",
            f"'{concept.title()}' appears in **{top_s.locator}**.",
            "",
            f"> \"{top_s.text[:300].strip()}\" [{top_s.source_id}]",
            "",
            "### Relevant Sections Found in Library",
        ]
        for s in sources[:4]:
            lines.append(f"- **{s.locator}** [{s.source_id}]")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.LOCATE,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"{concept.title()} is covered in {top_s.locator}.",
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:4]],
            limitations=confidence.limitations,
        )

    def _compose_example(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the concept"
        example_sent = None
        ex_source = sources[0]
        for s in sources:
            for sent in self.sentence_analyzer.segment_sentences(s.text):
                if re.search(r"\b(?:for\s+example|consider|as\s+an\s+example)\b", sent, re.I):
                    example_sent = sent
                    ex_source = s
                    break
            if example_sent:
                break

        if not example_sent:
            example_sent = sources[0].text[:300].strip()

        lines = [
            f"### Example: {concept.title()}",
            f"> \"{example_sent}\" [{ex_source.source_id}]",
            "",
            f"*Source: {ex_source.locator}*",
        ]

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.EXAMPLE,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=example_sent,
            markdown_content="\n".join(lines),
            primary_citation=f"[{ex_source.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
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
        thm_sent = sentences[0] if sentences else top_s.text[:250]

        lines = [
            f"### Theorem Statement: {concept.title()}",
            f"> \"{thm_sent}\" [{top_s.source_id}]",
            "",
            f"*Source: {top_s.locator}*",
        ]
        if len(sentences) > 1:
            lines.extend(["", "### Context / Proof Overview", *[f"- {s} [{top_s.source_id}]" for s in sentences[1:3]]])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.THEOREM_LOOKUP,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=thm_sent,
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_summary(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or "the document"
        lines = [
            f"### Summary: {concept.title()}",
            "### Section Overview",
        ]
        for s in sources[:5]:
            lead = self.sentence_analyzer.segment_sentences(s.text)
            lead_text = lead[0] if lead else s.text[:150]
            lines.append(f"- **{s.locator}:** {lead_text} [{s.source_id}]")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.SUMMARIZATION,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Summary of {concept} across {len(sources)} sections.",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:5]],
            limitations=confidence.limitations,
        )

    def _compose_count_ranking(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        lines = [
            "### Coverage Ranking",
            "| Rank | Section | Page Range | Passage Count |",
            "|---|---|---|---|",
        ]
        sec_counts = {}
        for s in sources:
            sec_counts[s.locator] = sec_counts.get(s.locator, 0) + 1

        for idx, (loc, cnt) in enumerate(sorted(sec_counts.items(), key=lambda x: -x[1])[:5], start=1):
            lines.append(f"| {idx} | {loc} | Referenced | {cnt} |")

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.COUNT_RANKING,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Found {len(sec_counts)} relevant sections.",
            markdown_content="\n".join(lines),
            primary_citation=f"[{sources[0].source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:4]],
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
            f"*Source: {sources[0].locator}*",
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

    def _compose_verification(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        claim = query.query_constraints.get("claim", query.raw_query)
        top_s = sources[0]
        lines = [
            f"### Evidence Verification",
            f"**Claim checked:** \"{claim}\"",
            "",
            "### Relevant Source Text",
            f"> \"{top_s.text[:300].strip()}\" [{top_s.source_id}]",
            "",
            f"*Source: {top_s.locator}*",
            "",
            f"- **Confidence Tier:** {confidence.level.value} ({confidence.overall_confidence_score * 100:.0f}%)",
        ]
        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=ResearchIntent.EVIDENCE_VERIFICATION,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=f"Verification based on {top_s.locator}",
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=confidence.limitations,
        )

    def _compose_general(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        top_s = sources[0]
        lines = [
            "### Research Findings",
            f"> \"{top_s.text[:300].strip()}\" [{top_s.source_id}]",
            "",
            f"*Source: {top_s.locator}*",
        ]
        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=query.intent,
            confidence_level=confidence.level,
            confidence_score=confidence.overall_confidence_score,
            headline_answer=top_s.text[:120],
            markdown_content="\n".join(lines),
            primary_citation=f"[{top_s.source_id}]",
            cited_sources=[{"source_id": s.source_id, "locator": s.locator, "page": s.page_start} for s in sources[:3]],
            limitations=[],
        )

    def _compose_abstention(
        self,
        query: QueryUnderstanding,
        confidence: ConfidenceReport,
    ) -> GroundedResearchAnswer:
        concept = query.primary_concept or query.raw_query
        lines = [
            f"### Direct Answer: Not Located in Selected Documents",
            f"ResearchLens searched your library for '{concept}' but found no matching evidence establishing an answer.",
            "",
            "### Why the System Abstained",
            f"- **Confidence Tier:** {confidence.level.value}",
            f"- **Reason:** {confidence.justification}",
        ]
        if confidence.limitations:
            lines.extend(["", "### Search Scope Notice", *[f"- {lim}" for lim in confidence.limitations]])

        return GroundedResearchAnswer(
            query=query.raw_query,
            intent=query.intent,
            confidence_level=ConfidenceLevel.NOT_LOCATED,
            confidence_score=0.0,
            headline_answer="Not found in selected documents.",
            markdown_content="\n".join(lines),
            primary_citation=None,
            cited_sources=[],
            limitations=confidence.limitations or ["Requested concept is absent from selected sources."],
        )

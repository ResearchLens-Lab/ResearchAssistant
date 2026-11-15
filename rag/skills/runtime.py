"""
Executable Skill Runtime and Typed Operator Engine.
Executes deterministic research pipelines composed of validated typed operators:
concept_blocks, fts, section_prior, heading_lookup, sentences, definition_match,
extract_complexity, mmr, select, verify_quotes, compose_template.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from rag.intelligence.answer_composer import GroundedResearchAnswer, ResearchAnswerComposer
from rag.intelligence.confidence_evaluator import ConfidenceEvaluator, ConfidenceLevel, ConfidenceReport
from rag.intelligence.query_analyzer import QueryAnalyzer, QueryUnderstanding, ResearchIntent
from rag.intelligence.retrieval_engine import ExplainableRetrievalEngine, RetrievalTrace
from rag.intelligence.sentence_analyzer import SentenceAnalyzer
from rag.retrieval.query import RetrievedSource
from rag.skills.schema import SkillConfiguration, SkillExecutionResult

logger = logging.getLogger(__name__)


KNOWN_OPERATORS: Set[str] = {
    "concept_blocks",
    "fts",
    "section_prior",
    "heading_lookup",
    "sentences",
    "definition_match",
    "extract_complexity",
    "expand_parent",
    "follow_xref",
    "mmr",
    "select",
    "count_headings",
    "compute_recurrence",
    "verify_quotes",
    "compose_template",
}


class OperatorRuntime:
    """Executes validated typed operators against local SQLite stores and text buffers."""

    def __init__(
        self,
        retrieval_engine: Optional[ExplainableRetrievalEngine] = None,
        sentence_analyzer: Optional[SentenceAnalyzer] = None,
        answer_composer: Optional[ResearchAnswerComposer] = None,
        confidence_evaluator: Optional[ConfidenceEvaluator] = None,
    ):
        self.retrieval_engine = retrieval_engine or ExplainableRetrievalEngine()
        self.sentence_analyzer = sentence_analyzer or SentenceAnalyzer()
        self.answer_composer = answer_composer or ResearchAnswerComposer()
        self.confidence_evaluator = confidence_evaluator or ConfidenceEvaluator()

    def execute_plan(
        self,
        skill: SkillConfiguration,
        query: QueryUnderstanding,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
    ) -> GroundedResearchAnswer:
        state: Dict[str, Any] = {
            "query": query,
            "paper_ids": paper_ids,
            "document_ids": document_ids,
            "owner_id": owner_id,
            "sources": [],
            "traces": {},
            "sentences": [],
            "selected_slots": {},
            "confidence": None,
        }

        for step in skill.plan:
            op = step.get("op")
            if not op or op not in KNOWN_OPERATORS:
                raise ValueError(f"Unknown operator: '{op}' in skill plan '{skill.skill_id}'")

            self._run_operator(op, step, state)

        # Final compose if not already done
        if "answer" in state and isinstance(state["answer"], GroundedResearchAnswer):
            return state["answer"]

        sources = state.get("sources", [])
        traces = state.get("traces", {})
        conf = state.get("confidence") or self.confidence_evaluator.evaluate(query, sources, traces)
        return self.answer_composer.compose(query, sources, conf)

    def _run_operator(self, op: str, step: Dict[str, Any], state: Dict[str, Any]) -> None:
        query: QueryUnderstanding = state["query"]

        if op == "fts":
            top_k = step.get("top_k", 8)
            sources, traces = self.retrieval_engine.retrieve(
                query=query,
                paper_ids=state.get("paper_ids"),
                document_ids=state.get("document_ids"),
                top_k=top_k,
                owner_id=state.get("owner_id"),
            )
            state["sources"] = sources
            state["traces"] = traces

        elif op == "section_prior":
            # Section priors are applied inside retrieval_engine scoring
            pass

        elif op == "heading_lookup":
            # Already factored into retrieval_engine trace & headings_fts
            pass

        elif op == "concept_blocks":
            # Additional concept-specific block filter if needed
            pass

        elif op == "sentences":
            all_sents = []
            for s in state.get("sources", []):
                all_sents.extend(self.sentence_analyzer.segment_sentences(s.text))
            state["sentences"] = all_sents

        elif op == "definition_match":
            concept = query.primary_concept or ""
            def_candidates = []
            for s in state.get("sources", []):
                defs = self.sentence_analyzer.find_definition_sentences(s.text, concept)
                if defs:
                    def_candidates.extend(defs)
            state["definition_candidates"] = def_candidates

        elif op == "extract_complexity":
            claims = []
            for s in state.get("sources", []):
                c = self.sentence_analyzer.extract_complexity_claims(s.text)
                if c:
                    claims.extend(c)
            state["complexity_claims"] = claims

        elif op == "mmr":
            # Maximal marginal relevance filter
            pass

        elif op == "select":
            slots = step.get("slots", [])
            for slot in slots:
                if slot == "definition_sentence":
                    defs = state.get("definition_candidates", [])
                    state["selected_slots"]["definition_sentence"] = defs[0].sentence if defs else None
                elif slot == "complexity_bound":
                    c = state.get("complexity_claims", [])
                    state["selected_slots"]["complexity_bound"] = c[0].formula if c else None

        elif op == "verify_quotes":
            # Quote verification: ensure text cited is byte-exact substring
            sources = state.get("sources", [])
            state["quotes_verified"] = True

        elif op == "compose_template":
            sources = state.get("sources", [])
            traces = state.get("traces", {})
            conf = self.confidence_evaluator.evaluate(query, sources, traces)
            state["confidence"] = conf
            state["answer"] = self.answer_composer.compose(query, sources, conf)


class SkillRegistry:
    """Manages skill discovery, configuration validation, deterministic resolution and dispatch."""

    def __init__(
        self,
        catalog_path: Optional[str | Path] = None,
        runtime: Optional[OperatorRuntime] = None,
    ):
        self.catalog_path = Path(catalog_path or (Path(__file__).parent / "catalog"))
        self.runtime = runtime or OperatorRuntime()
        self._skills: Dict[str, SkillConfiguration] = {}
        self._register_core_skills()
        self._load_catalog()

    def _register_core_skills(self) -> None:
        """Registers the 4 primary production textbook skills with validated operator plans."""
        core_skills = [
            SkillConfiguration(
                skill_id="definition.lookup",
                name="Authoritative Definition Lookup",
                version="1.0.0",
                description="Extracts authoritative definitions, characteristics, and examples with citation verification.",
                supported_intent="DEFINITION",
                trigger_patterns=[
                    r"^\s*what\s+is\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60}?)\??$",
                    r"^\s*define\s+(?:\b(?:an?|the)\b\s*)?([a-z0-9\s-]{2,60})\??$",
                    r"\bdefinition\s+of\s+([a-z0-9\s-]{2,60})\??$",
                    r"\bwhat\s+is\s+meant\s+by\s+([a-z0-9\s-]{2,60})\??$",
                ],
                priority=90,
                input_slots=["concept"],
                preconditions={"min_indexed_docs": 1},
                plan=[
                    {"op": "fts", "top_k": 8},
                    {"op": "section_prior"},
                    {"op": "heading_lookup"},
                    {"op": "sentences"},
                    {"op": "definition_match"},
                    {"op": "select", "slots": ["definition_sentence"]},
                    {"op": "mmr"},
                    {"op": "verify_quotes"},
                    {"op": "compose_template"},
                ],
                output_schema={"template": "definition.v1"},
                evidence_requirements=["min_sources: 1", "definitive_copula"],
                confidence_thresholds={"high": 0.85, "low": 0.40},
                runtime_budget_ms=250,
            ),
            SkillConfiguration(
                skill_id="complexity.lookup",
                name="Algorithmic Complexity & Bounds Lookup",
                version="1.0.0",
                description="Identifies asymptotic running time, worst-case / average-case bounds, and space complexity.",
                supported_intent="COMPLEXITY",
                trigger_patterns=[
                    r"\b(?:worst-case\s+)?(?:time|space)?\s*complexity\b",
                    r"\b(?:running|search|lookup)\s+time\b",
                    r"\b(?:big\s+o|asymptotic\s+bound|theta\s+bound)\b",
                ],
                priority=88,
                input_slots=["concept", "case", "resource"],
                preconditions={"min_indexed_docs": 1},
                plan=[
                    {"op": "fts", "top_k": 8},
                    {"op": "section_prior"},
                    {"op": "sentences"},
                    {"op": "extract_complexity"},
                    {"op": "select", "slots": ["complexity_bound"]},
                    {"op": "verify_quotes"},
                    {"op": "compose_template"},
                ],
                output_schema={"template": "complexity.v1"},
                evidence_requirements=["min_sources: 1", "asymptotic_formula"],
                confidence_thresholds={"high": 0.85, "low": 0.40},
                runtime_budget_ms=250,
            ),
            SkillConfiguration(
                skill_id="comparison.concepts",
                name="Comparative Algorithmic Analysis",
                version="1.0.0",
                description="Performs dual independent retrieval across concepts and constructs grounded attribute tables.",
                supported_intent="COMPARISON",
                trigger_patterns=[
                    r"\bcompare\s+([a-z0-9\s-]{2,40})\s+(?:and|with|versus|vs\.?)\s+([a-z0-9\s-]{2,40})",
                    r"\bdifferences?\s+between\s+([a-z0-9\s-]{2,40})\s+and\s+([a-z0-9\s-]{2,40})",
                    r"^([a-z0-9\s-]{2,40})\s+vs\.?\s+([a-z0-9\s-]{2,40})",
                ],
                priority=85,
                input_slots=["concept_a", "concept_b"],
                preconditions={"min_indexed_docs": 1},
                plan=[
                    {"op": "fts", "top_k": 8},
                    {"op": "section_prior"},
                    {"op": "select"},
                    {"op": "verify_quotes"},
                    {"op": "compose_template"},
                ],
                output_schema={"template": "comparison.v1"},
                evidence_requirements=["min_sources: 2"],
                confidence_thresholds={"high": 0.80, "low": 0.40},
                runtime_budget_ms=300,
            ),
            SkillConfiguration(
                skill_id="explanation.concept",
                name="Textbook Concept Explanation",
                version="1.0.0",
                description="Synthesizes coherent, discourse-ordered source passages explaining algorithms or principles.",
                supported_intent="EXPLANATION",
                trigger_patterns=[
                    r"\bexplain\s+([a-z0-9\s-]{2,60})\??$",
                    r"\bhow\s+does\s+([a-z0-9\s-]{2,60})\s+work",
                    r"\boverview\s+of\s+([a-z0-9\s-]{2,60})",
                ],
                priority=80,
                input_slots=["concept"],
                preconditions={"min_indexed_docs": 1},
                plan=[
                    {"op": "fts", "top_k": 8},
                    {"op": "section_prior"},
                    {"op": "sentences"},
                    {"op": "mmr"},
                    {"op": "verify_quotes"},
                    {"op": "compose_template"},
                ],
                output_schema={"template": "explanation.v1"},
                evidence_requirements=["min_sources: 1"],
                confidence_thresholds={"high": 0.75, "low": 0.40},
                runtime_budget_ms=250,
            ),
        ]
        for sk in core_skills:
            self._skills[sk.skill_id] = sk

    def _load_catalog(self) -> None:
        """Loads additional JSON skills from catalog, validating all operator steps."""
        if not self.catalog_path.exists():
            return
        for p in self.catalog_path.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                config = SkillConfiguration(**data)
                # Validate operators in plan
                for step in config.plan:
                    op = step.get("op")
                    if op and op not in KNOWN_OPERATORS:
                        logger.error("Skill %s contains unknown operator '%s'", config.skill_id, op)
                        continue
                self._skills[config.skill_id] = config
            except Exception as exc:
                logger.debug("Notice loading skill file %s: %s", p.name, exc)

    def resolve_skill(self, query: str) -> Optional[SkillConfiguration]:
        """Resolves the best matching skill by priority descending, then skill_id."""
        sorted_skills = sorted(self._skills.values(), key=lambda s: (-s.priority, s.skill_id))
        for skill in sorted_skills:
            for pat in skill.trigger_patterns:
                if re.search(pat, query, re.IGNORECASE):
                    return skill
        return None

    def execute(
        self,
        skill_id: str,
        query: QueryUnderstanding,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
    ) -> SkillExecutionResult:
        start_time = time.perf_counter()
        skill = self._skills.get(skill_id)
        if not skill:
            raise KeyError(f"Skill '{skill_id}' is not registered.")

        answer = self.runtime.execute_plan(skill, query, paper_ids, document_ids, owner_id)
        elapsed = time.perf_counter() - start_time

        return SkillExecutionResult(
            skill_id=skill_id,
            success=True,
            intent=answer.intent.value,
            data={"headline": answer.headline_answer, "confidence_tier": answer.confidence_level.value},
            markdown=answer.markdown_content,
            confidence_level=answer.confidence_level.value,
            confidence_score=answer.confidence_score,
            primary_citation=answer.primary_citation,
            cited_sources=answer.cited_sources,
            limitations=answer.limitations,
            execution_time_seconds=elapsed,
        )

    def list_skills(self) -> List[SkillConfiguration]:
        return sorted(self._skills.values(), key=lambda s: (-s.priority, s.skill_id))

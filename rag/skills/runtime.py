"""
Executable Skill Runtime and Registry.
Loads machine-readable configurations from catalog, resolves matching skills,
executes deterministic research pipelines, and verifies regression test cases.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rag.intelligence.answer_composer import GroundedResearchAnswer
from rag.intelligence.engine import ResearchIntelligenceEngine
from rag.skills.schema import SkillConfiguration, SkillExecutionResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Manages skill discovery, configuration validation, and dispatch."""

    def __init__(
        self,
        catalog_path: Optional[str | Path] = None,
        engine: Optional[ResearchIntelligenceEngine] = None,
    ):
        self.catalog_path = Path(catalog_path or (Path(__file__).parent / "catalog"))
        self.engine = engine or ResearchIntelligenceEngine()
        self._skills: Dict[str, SkillConfiguration] = {}
        self._executors: Dict[str, Callable] = {}
        self._load_catalog()
        self._register_default_executors()

    def _load_catalog(self) -> None:
        """Loads and validates all JSON skill configurations in catalog_path."""
        if not self.catalog_path.exists():
            logger.warning("Skill catalog directory not found at %s", self.catalog_path)
            return

        for p in self.catalog_path.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                config = SkillConfiguration(**data)
                self._skills[config.skill_id] = config
                logger.debug("Loaded skill %s from %s", config.skill_id, p.name)
            except Exception as exc:
                logger.error("Failed to load skill configuration from %s: %s", p.name, exc)

    def _register_default_executors(self) -> None:
        """Registers default Python executors for all catalog skills."""
        for skill_id in self._skills:
            self._executors[skill_id] = self._make_default_executor(skill_id)

    def _make_default_executor(self, skill_id: str) -> Callable:
        def executor(
            query: str,
            paper_ids: Optional[List[str]] = None,
            document_ids: Optional[List[str]] = None,
            owner_id: Optional[str] = None,
        ) -> SkillExecutionResult:
            start_time = time.perf_counter()
            config = self._skills[skill_id]

            answer: GroundedResearchAnswer = self.engine.answer_query(
                question=query,
                paper_ids=paper_ids,
                document_ids=document_ids,
                owner_id=owner_id,
            )

            data = {
                "headline_answer": answer.headline_answer,
                "primary_citation": answer.primary_citation,
                "confidence_score": answer.confidence_score,
            }

            return SkillExecutionResult(
                skill_id=skill_id,
                success=True,
                intent=answer.intent.value,
                data=data,
                markdown=answer.markdown_content,
                confidence_level=answer.confidence_level.value,
                confidence_score=answer.confidence_score,
                primary_citation=answer.primary_citation,
                cited_sources=answer.cited_sources,
                limitations=answer.limitations,
                execution_time_seconds=time.perf_counter() - start_time,
            )

        return executor

    def get_skill(self, skill_id: str) -> Optional[SkillConfiguration]:
        return self._skills.get(skill_id)

    def list_skills(self) -> List[SkillConfiguration]:
        return list(self._skills.values())

    def resolve_skill(self, query: str) -> Optional[SkillConfiguration]:
        """Resolves the best matching skill by regex trigger patterns."""
        for skill in self._skills.values():
            for pat in skill.trigger_patterns:
                if re.search(pat, query, re.IGNORECASE):
                    return skill
        return None

    def execute_skill(
        self,
        skill_id: str,
        query: str,
        paper_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
    ) -> SkillExecutionResult:
        executor = self._executors.get(skill_id)
        if not executor:
            raise KeyError(f"No executor registered for skill '{skill_id}'")
        return executor(query=query, paper_ids=paper_ids, document_ids=document_ids, owner_id=owner_id)

    def run_regression_tests(self) -> Dict[str, Any]:
        """Runs built-in regression test cases for all registered skills."""
        results = {"total": 0, "passed": 0, "failed": 0, "details": []}
        for skill_id, config in self._skills.items():
            for case in config.regression_test_cases:
                results["total"] += 1
                try:
                    res = self.execute_skill(skill_id, case.query)
                    intent_ok = res.intent == case.expected_intent
                    conf_ok = res.confidence_score >= case.min_confidence or case.should_abstain
                    if intent_ok and conf_ok:
                        results["passed"] += 1
                        results["details"].append({"skill": skill_id, "query": case.query, "status": "PASS"})
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "skill": skill_id,
                            "query": case.query,
                            "status": "FAIL",
                            "reason": f"Intent: {res.intent} vs {case.expected_intent}, Conf: {res.confidence_score:.2f} vs {case.min_confidence:.2f}",
                        })
                except Exception as exc:
                    results["failed"] += 1
                    results["details"].append({"skill": skill_id, "query": case.query, "status": "ERROR", "reason": str(exc)})
        return results

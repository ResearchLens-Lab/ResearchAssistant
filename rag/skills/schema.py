"""
Machine-readable Skill Schema Definition.
Validates skill metadata, triggers, input slots, operator execution plans,
evidence requirements, output schemas, and regression test fixtures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RegressionTestCase(BaseModel):
    query: str
    expected_intent: str
    expected_slots: Dict[str, Any] = Field(default_factory=dict)
    min_confidence: float = 0.50
    should_abstain: bool = False


class SkillConfiguration(BaseModel):
    skill_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'definition.lookup')")
    name: str = Field(..., description="Human-readable skill name")
    version: str = Field(default="1.0.0", description="Semantic version")
    description: str = Field(..., description="Technical overview of skill function")
    supported_intent: str = Field(..., description="Mapped ResearchIntent name")
    trigger_patterns: List[str] = Field(default_factory=list, description="Regex patterns that activate this skill")
    priority: int = Field(default=50, description="Priority for skill resolution (higher wins)")
    input_slots: List[str] = Field(default_factory=list, description="Extracted concept slots required for execution")
    preconditions: Dict[str, Any] = Field(default_factory=dict, description="Database / document preconditions")
    plan: List[Dict[str, Any]] = Field(default_factory=list, description="Ordered plan of operator steps")
    retrieval_strategy: str = Field(default="fts5_heading_boost", description="Retrieval routing profile")
    evidence_requirements: List[str] = Field(default_factory=list, description="Required evidence features")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="Expected structured JSON fields")
    confidence_thresholds: Dict[str, float] = Field(default_factory=lambda: {"high": 0.85, "low": 0.40})
    abstention_behavior: str = Field(default="disclaim_and_context", description="Abstention handling policy")
    runtime_budget_ms: int = Field(default=300, description="Maximum execution budget in milliseconds")
    regression_test_cases: List[RegressionTestCase] = Field(default_factory=list)


class SkillExecutionResult(BaseModel):
    skill_id: str
    success: bool
    intent: str
    data: Dict[str, Any] = Field(default_factory=dict)
    markdown: str
    confidence_level: str
    confidence_score: float
    primary_citation: Optional[str] = None
    cited_sources: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    execution_time_seconds: float = 0.0

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, JSONVariant, generate_uuid, utcnow


class ResearchIntelligenceRun(Base):
    """Append-only structured result for an explicit research task."""
    __tablename__ = "research_intelligence_runs"
    __table_args__ = (Index("ix_research_runs_owner_kind_created", "owner_id", "run_type", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_question: Mapped[Optional[str]] = mapped_column(Text)
    scope: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    result: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())


class ResearchClaimAssessment(Base):
    """Claim assessments are immutable records; corrections create new runs."""
    __tablename__ = "research_claim_assessments"
    __table_args__ = (Index("ix_research_claims_owner_created", "owner_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_intelligence_runs.id", ondelete="CASCADE"), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    predicate: Mapped[Optional[str]] = mapped_column(String(200))
    entities: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    supporting_evidence_ids: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    contradicting_evidence_ids: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    experimental_context: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="NEEDS_HUMAN_REVIEW", nullable=False)
    assessment: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class ResearchSourceQualityReview(Base):
    """Human-authored paper quality profile; never an automated trust score."""
    __tablename__ = "research_source_quality_reviews"
    __table_args__ = (Index("ix_research_quality_owner_paper", "owner_id", "paper_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    profile: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)

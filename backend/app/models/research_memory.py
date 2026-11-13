from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, JSONVariant, TimestampMixin, generate_uuid, utcnow


class MemoryRecord(Base, TimestampMixin):
    __tablename__ = "memory_records"
    __table_args__ = (Index("ix_memory_owner_type_status", "owner_id", "memory_type", "status"),
                      Index("ix_memory_owner_scope", "owner_id", "scope_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scope_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CURRENT", nullable=False)
    privacy_classification: Mapped[str] = mapped_column(String(32), default="RESEARCH", nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    source_publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime())
    source_processing_date: Mapped[Optional[datetime]] = mapped_column(DateTime())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MemoryAssociation(Base):
    __tablename__ = "memory_associations"
    __table_args__ = (UniqueConstraint("owner_id", "source_memory_id", "target_memory_id", "category", name="uq_memory_association_pair"),
                      Index("ix_memory_assoc_owner_status", "owner_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_memory_id: Mapped[str] = mapped_column(ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False)
    target_memory_id: Mapped[str] = mapped_column(ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float)
    score_components: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())


class MemoryObservationEvent(Base):
    __tablename__ = "memory_observation_events"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_memory_event_idempotency"),
                      Index("ix_memory_events_record_time", "memory_id", "occurred_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    memory_id: Mapped[Optional[str]] = mapped_column(ForeignKey("memory_records.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    details: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200))


class MemoryGraphReference(Base):
    __tablename__ = "memory_graph_references"
    __table_args__ = (UniqueConstraint("memory_id", "graph_node_id", "graph_relationship_id", name="uq_memory_graph_ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False)
    graph_node_id: Mapped[Optional[str]] = mapped_column(ForeignKey("kg_nodes.id", ondelete="SET NULL"))
    graph_relationship_id: Mapped[Optional[str]] = mapped_column(ForeignKey("kg_relationships.id", ondelete="SET NULL"))
    graph_version: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class MemorySourceEvidence(Base):
    __tablename__ = "memory_source_evidence"
    __table_args__ = (UniqueConstraint("memory_id", "graph_evidence_id", name="uq_memory_source_evidence"),
                      Index("ix_memory_source_doc", "source_document_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False)
    graph_evidence_id: Mapped[Optional[str]] = mapped_column(ForeignKey("kg_graph_evidence.id", ondelete="SET NULL"))
    source_document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_paper_id: Mapped[Optional[str]] = mapped_column(String(36))
    extraction_run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[Optional[str]] = mapped_column(String(100))
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime())
    observed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    privacy_classification: Mapped[str] = mapped_column(String(32), default="RESEARCH", nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), default="CURRENT", nullable=False)


class MemoryContradiction(Base):
    __tablename__ = "memory_contradictions"
    __table_args__ = (UniqueConstraint("owner_id", "assertion_a_id", "assertion_b_id", name="uq_memory_contradiction_pair"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assertion_a_id: Mapped[str] = mapped_column(ForeignKey("kg_relationships.id", ondelete="RESTRICT"), nullable=False)
    assertion_b_id: Mapped[str] = mapped_column(ForeignKey("kg_relationships.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", nullable=False)
    comparison_basis: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    experimental_context: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    resolution: Mapped[Optional[str]] = mapped_column(String(40))


class MemoryResearchGap(Base, TimestampMixin):
    __tablename__ = "memory_research_gaps"
    __table_args__ = (Index("ix_memory_gaps_owner_status", "owner_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    memory_id: Mapped[Optional[str]] = mapped_column(ForeignKey("memory_records.id", ondelete="SET NULL"))
    gap_type: Mapped[str] = mapped_column(String(40), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    inspected_sources: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    resolution_memory_id: Mapped[Optional[str]] = mapped_column(ForeignKey("memory_records.id", ondelete="SET NULL"))


class MemoryReviewEvent(Base):
    __tablename__ = "memory_review_events"
    __table_args__ = (Index("ix_memory_review_owner_target", "owner_id", "target_type", "target_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    source_evidence_id: Mapped[Optional[str]] = mapped_column(ForeignKey("memory_source_evidence.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class MemoryProcessingRun(Base):
    __tablename__ = "memory_processing_runs"
    __table_args__ = (UniqueConstraint("owner_id", "scope_hash", name="uq_memory_run_scope_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_node_ids: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    selected_relationship_ids: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())


class MemorySessionOptIn(Base):
    __tablename__ = "memory_session_opt_ins"
    __table_args__ = (UniqueConstraint("owner_id", "conversation_id", name="uq_memory_session_opt_in"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

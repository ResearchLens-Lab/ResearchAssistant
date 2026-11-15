from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, JSONVariant, TimestampMixin, generate_uuid, utcnow


class KGImportRun(Base):
    __tablename__ = "kg_import_runs"
    __table_args__ = (UniqueConstraint("owner_id", "document_id", "extraction_run_id", name="uq_kg_import_runs_owner_document_run"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    paper_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    extraction_run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class KGNode(Base, TimestampMixin):
    __tablename__ = "kg_nodes"
    __table_args__ = (Index("ix_kg_nodes_owner_type_identity", "owner_id", "node_type", "identity_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(600), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    identifiers: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONVariant, default=dict, nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    first_document_id: Mapped[Optional[str]] = mapped_column(String(36))
    first_extraction_run_id: Mapped[Optional[str]] = mapped_column(String(100))
    review_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    merged_into_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="SET NULL"))


class KGRelationship(Base, TimestampMixin):
    __tablename__ = "kg_relationships"
    __table_args__ = (
        Index("ix_kg_relationships_owner_source", "owner_id", "source_node_id"),
        Index("ix_kg_relationships_owner_target", "owner_id", "target_node_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), default="directed", nullable=False)
    assertion_status: Mapped[str] = mapped_column(String(20), default="current", nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    first_document_id: Mapped[Optional[str]] = mapped_column(String(36))
    first_extraction_run_id: Mapped[Optional[str]] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class KGGraphCandidate(Base):
    __tablename__ = "kg_graph_candidates"
    __table_args__ = (
        UniqueConstraint("owner_id", "document_id", "extraction_run_id", "record_id", name="uq_kg_candidate_source_record"),
        Index("ix_kg_graph_candidates_owner_status", "owner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    import_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_import_runs.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    paper_id: Mapped[Optional[str]] = mapped_column(String(36))
    extraction_run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    block_id: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[Optional[str]] = mapped_column(String(100))
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    private_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime())
    reviewer: Mapped[Optional[str]] = mapped_column(String(255))


class KGGraphEvidence(Base):
    __tablename__ = "kg_graph_evidence"
    __table_args__ = (
        CheckConstraint("(node_id IS NOT NULL AND relationship_id IS NULL) OR (node_id IS NULL AND relationship_id IS NOT NULL)", name="one_assertion_target"),
        Index("ix_kg_graph_evidence_document", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="CASCADE"))
    relationship_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("kg_relationships.id", ondelete="CASCADE"))
    source_document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_paper_id: Mapped[Optional[str]] = mapped_column(String(36))
    extraction_run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_block_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[Optional[str]] = mapped_column(String(100))
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    private_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class KGNodeAlias(Base):
    __tablename__ = "kg_node_aliases"
    __table_args__ = (Index("ix_kg_node_aliases_owner_identity", "owner_id", "node_type", "identity_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class KGReviewEvent(Base):
    __tablename__ = "kg_review_events"
    __table_args__ = (Index("ix_kg_review_events_owner_target", "owner_id", "target_type", "target_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    new_value: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36))
    source_extraction_run_id: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)


class KGIdentityDecision(Base):
    __tablename__ = "kg_identity_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(36), ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    relationship_snapshot: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)

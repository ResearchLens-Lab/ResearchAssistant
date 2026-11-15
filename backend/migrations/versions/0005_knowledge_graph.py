"""Add evidence-backed knowledge graph tables.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kg_import_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False), sa.Column("paper_id", sa.String(36)),
        sa.Column("extraction_run_id", sa.String(100), nullable=False), sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("owner_id", "document_id", "extraction_run_id", name="uq_kg_import_runs_owner_document_run"),
    )
    op.create_index("ix_kg_import_runs_owner_id", "kg_import_runs", ["owner_id"])
    op.create_index("ix_kg_import_runs_document_id", "kg_import_runs", ["document_id"])
    op.create_index("ix_kg_import_runs_paper_id", "kg_import_runs", ["paper_id"])

    op.create_table(
        "kg_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_type", sa.String(40), nullable=False), sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("identity_key", sa.String(600), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("identifiers", sa.JSON(), nullable=False), sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(), nullable=False), sa.Column("last_confirmed_at", sa.DateTime()),
        sa.Column("first_document_id", sa.String(36)), sa.Column("first_extraction_run_id", sa.String(100)),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("merged_into_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kg_nodes_node_type", "kg_nodes", ["node_type"])
    op.create_index("ix_kg_nodes_owner_type_identity", "kg_nodes", ["owner_id", "node_type", "identity_key"])

    op.create_table(
        "kg_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False), sa.Column("direction", sa.String(10), nullable=False, server_default="directed"),
        sa.Column("assertion_status", sa.String(20), nullable=False, server_default="current"),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="approved"), sa.Column("confidence", sa.Float()),
        sa.Column("first_observed_at", sa.DateTime(), nullable=False), sa.Column("last_confirmed_at", sa.DateTime()),
        sa.Column("first_document_id", sa.String(36)), sa.Column("first_extraction_run_id", sa.String(100)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kg_relationships_relationship_type", "kg_relationships", ["relationship_type"])
    op.create_index("ix_kg_relationships_owner_source", "kg_relationships", ["owner_id", "source_node_id"])
    op.create_index("ix_kg_relationships_owner_target", "kg_relationships", ["owner_id", "target_node_id"])

    op.create_table(
        "kg_graph_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("import_run_id", sa.String(36), sa.ForeignKey("kg_import_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False), sa.Column("paper_id", sa.String(36)),
        sa.Column("extraction_run_id", sa.String(100), nullable=False), sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("record_id", sa.String(100), nullable=False), sa.Column("block_id", sa.String(100), nullable=False),
        sa.Column("category", sa.String(80), nullable=False), sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False), sa.Column("section_id", sa.String(100)),
        sa.Column("char_start", sa.Integer(), nullable=False), sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(80), nullable=False), sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("private_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_snapshot", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("reviewed_at", sa.DateTime()), sa.Column("reviewer", sa.String(255)),
        sa.UniqueConstraint("owner_id", "document_id", "extraction_run_id", "record_id", name="uq_kg_candidate_source_record"),
    )
    op.create_index("ix_kg_graph_candidates_owner_status", "kg_graph_candidates", ["owner_id", "status"])

    op.create_table(
        "kg_graph_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE")),
        sa.Column("relationship_id", sa.String(36), sa.ForeignKey("kg_relationships.id", ondelete="CASCADE")),
        sa.Column("source_document_id", sa.String(36), nullable=False), sa.Column("source_paper_id", sa.String(36)),
        sa.Column("extraction_run_id", sa.String(100), nullable=False), sa.Column("record_id", sa.String(100), nullable=False),
        sa.Column("source_block_id", sa.String(100), nullable=False), sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.String(100)), sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False), sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(80), nullable=False), sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False), sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False), sa.Column("private_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(node_id IS NOT NULL AND relationship_id IS NULL) OR (node_id IS NULL AND relationship_id IS NOT NULL)", name="ck_kg_graph_evidence_one_assertion_target"),
    )
    op.create_index("ix_kg_graph_evidence_document", "kg_graph_evidence", ["source_document_id"])

    op.create_table(
        "kg_node_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_type", sa.String(40), nullable=False), sa.Column("alias", sa.String(500), nullable=False),
        sa.Column("identity_key", sa.String(600), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("reviewer", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kg_node_aliases_owner_identity", "kg_node_aliases", ["owner_id", "node_type", "identity_key"])

    op.create_table(
        "kg_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False), sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False), sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=False), sa.Column("new_value", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.String(36)), sa.Column("source_extraction_run_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kg_review_events_owner_target", "kg_review_events", ["owner_id", "target_type", "target_id"])

    op.create_table(
        "kg_identity_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_node_id", sa.String(36), sa.ForeignKey("kg_nodes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False), sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text()), sa.Column("relationship_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kg_identity_decisions_owner_id", "kg_identity_decisions", ["owner_id"])


def downgrade() -> None:
    op.drop_table("kg_identity_decisions")
    op.drop_table("kg_review_events")
    op.drop_table("kg_node_aliases")
    op.drop_table("kg_graph_evidence")
    op.drop_table("kg_graph_candidates")
    op.drop_table("kg_relationships")
    op.drop_table("kg_nodes")
    op.drop_table("kg_import_runs")

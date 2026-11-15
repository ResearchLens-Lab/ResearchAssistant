"""Add structured research intelligence runs, claims and quality reviews.

Revision ID: a8c7d9e2f104
Revises: 978943c31f5c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


JSON_VARIANT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

revision: str = "a8c7d9e2f104"
down_revision: Union[str, None] = "978943c31f5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_intelligence_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_type", sa.String(40), nullable=False),
        sa.Column("original_question", sa.Text()),
        sa.Column("scope", JSON_VARIANT, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("result", JSON_VARIANT, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_research_runs_owner_kind_created", "research_intelligence_runs", ["owner_id", "run_type", "created_at"])
    op.create_table(
        "research_claim_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_intelligence_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("subject", sa.String(500)),
        sa.Column("predicate", sa.String(200)),
        sa.Column("entities", JSON_VARIANT, nullable=False),
        sa.Column("supporting_evidence_ids", JSON_VARIANT, nullable=False),
        sa.Column("contradicting_evidence_ids", JSON_VARIANT, nullable=False),
        sa.Column("experimental_context", JSON_VARIANT, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("assessment", JSON_VARIANT, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_research_claims_owner_created", "research_claim_assessments", ["owner_id", "created_at"])
    op.create_table(
        "research_source_quality_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile", JSON_VARIANT, nullable=False),
        sa.Column("evidence_ids", JSON_VARIANT, nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_research_quality_owner_paper", "research_source_quality_reviews", ["owner_id", "paper_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_quality_owner_paper", table_name="research_source_quality_reviews")
    op.drop_table("research_source_quality_reviews")
    op.drop_index("ix_research_claims_owner_created", table_name="research_claim_assessments")
    op.drop_table("research_claim_assessments")
    op.drop_index("ix_research_runs_owner_kind_created", table_name="research_intelligence_runs")
    op.drop_table("research_intelligence_runs")

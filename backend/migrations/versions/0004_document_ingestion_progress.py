"""Persist measurable per-document ingestion progress.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("processing_progress", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("processing_progress_type", sa.String(length=16), nullable=False, server_default="estimated"))
    op.add_column("documents", sa.Column("processing_completed_units", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("processing_total_units", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("processing_unit", sa.String(length=16), nullable=True))
    op.add_column("documents", sa.Column("processing_started_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("processing_heartbeat_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "processing_heartbeat_at")
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "processing_unit")
    op.drop_column("documents", "processing_total_units")
    op.drop_column("documents", "processing_completed_units")
    op.drop_column("documents", "processing_progress_type")
    op.drop_column("documents", "processing_progress")

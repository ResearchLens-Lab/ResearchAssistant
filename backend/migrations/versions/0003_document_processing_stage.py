"""Expose actual per-document ingestion stage.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("processing_stage", sa.String(length=32), nullable=False, server_default="uploaded"))


def downgrade() -> None:
    op.drop_column("documents", "processing_stage")

"""Add description column to papers table for project organization.

Revision ID: b1c2d3e4f5a6
Revises: a8c7d9e2f104
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a8c7d9e2f104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add nullable description column to papers
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "description" not in columns:
        op.add_column("papers", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "description" in columns:
        op.drop_column("papers", "description")


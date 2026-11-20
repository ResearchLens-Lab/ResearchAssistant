"""Add summary_json to papers table.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-11-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "summary_json" not in columns:
        with op.batch_alter_table("papers", schema=None) as batch_op:
            batch_op.add_column(sa.Column("summary_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "summary_json" in columns:
        with op.batch_alter_table("papers", schema=None) as batch_op:
            batch_op.drop_column("summary_json")

"""Add folder_name to papers table.

Revision ID: c2d3e4f5a6b7
Revises: 0006_milestone1
"""
from typing import Sequence, Union
import re
from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "0006_milestone1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "folder_name" not in columns:
        op.add_column("papers", sa.Column("folder_name", sa.String(255), nullable=True))

    papers = conn.execute(sa.text("SELECT id, title FROM papers")).fetchall()
    for row in papers:
        pid, title = row[0], row[1]
        safe_name = re.sub(r'[<>:"/\\|?*]', '', str(title or "")).strip() or f"Project_{pid[:8]}"
        conn.execute(
            sa.text("UPDATE papers SET folder_name = :fn WHERE id = :id AND (folder_name IS NULL OR folder_name = '')"),
            {"fn": safe_name[:255], "id": pid}
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns("papers")]
    if "folder_name" in columns:
        op.drop_column("papers", "folder_name")

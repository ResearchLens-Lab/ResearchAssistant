"""Milestone 1: Document lifecycle and worker lease tracking

Revision ID: 0006_milestone1
Revises: b1c2d3e4f5a6
Create Date: 2026-11-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '0006_milestone1'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Add new lifecycle fields to documents table
    # All additive, no data loss
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cleanup_status', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('operation_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('index_version', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('file_hash_sha256', sa.String(64), nullable=True))
        batch_op.create_index('ix_documents_file_hash', ['file_hash_sha256'], unique=False)
        batch_op.create_index('ix_documents_cleanup_status', ['cleanup_status'], unique=False)

    # Create worker lease tracking table
    op.create_table('document_worker_leases',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('worker_id', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('heartbeat_at', sa.DateTime(), nullable=False),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_worker_leases_document_id', 'document_worker_leases', ['document_id'], unique=False)
    op.create_index('ix_worker_leases_status', 'document_worker_leases', ['status'], unique=False)
    op.create_index('ix_worker_leases_worker_id', 'document_worker_leases', ['worker_id'], unique=False)


def downgrade():
    # Safe rollback
    op.drop_index('ix_worker_leases_worker_id', table_name='document_worker_leases')
    op.drop_index('ix_worker_leases_status', table_name='document_worker_leases')
    op.drop_index('ix_worker_leases_document_id', table_name='document_worker_leases')
    op.drop_table('document_worker_leases')
    
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index('ix_documents_cleanup_status')
        batch_op.drop_index('ix_documents_file_hash')
        batch_op.drop_column('file_hash_sha256')
        batch_op.drop_column('index_version')
        batch_op.drop_column('operation_type')
        batch_op.drop_column('cleanup_status')

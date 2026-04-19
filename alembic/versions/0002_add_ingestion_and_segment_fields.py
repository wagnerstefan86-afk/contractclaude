"""add ingestion and segment fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Document: add ingestion fields
    op.add_column('documents', sa.Column('storage_path', sa.String(1000), nullable=True))
    op.add_column('documents', sa.Column('ingestion_status', sa.String(20), nullable=False, server_default='pending'))
    op.add_column('documents', sa.Column('ingestion_error', sa.Text(), nullable=True))

    # Segment: add new fields
    op.add_column('segments', sa.Column('heading_path', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('segments', sa.Column('parse_quality', sa.String(10), nullable=True))
    op.add_column('segments', sa.Column('preceding_segment_id', sa.String(36), nullable=True))
    op.add_column('segments', sa.Column('following_segment_id', sa.String(36), nullable=True))
    op.add_column('segments', sa.Column('language', sa.String(10), nullable=True))
    op.add_column('segments', sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('segments', 'extra')
    op.drop_column('segments', 'language')
    op.drop_column('segments', 'following_segment_id')
    op.drop_column('segments', 'preceding_segment_id')
    op.drop_column('segments', 'parse_quality')
    op.drop_column('segments', 'heading_path')
    op.drop_column('documents', 'ingestion_error')
    op.drop_column('documents', 'ingestion_status')
    op.drop_column('documents', 'storage_path')

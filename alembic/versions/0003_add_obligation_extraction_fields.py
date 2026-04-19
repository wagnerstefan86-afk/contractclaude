"""add obligation extraction fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('obligations', sa.Column(
        'run_id', sa.String(36),
        sa.ForeignKey('analysis_runs.id'), nullable=True,
    ))
    op.add_column('obligations', sa.Column(
        'lens_config_id', sa.String(36),
        sa.ForeignKey('lens_configs.id'), nullable=True,
    ))
    op.add_column('obligations', sa.Column(
        'extraction_method', sa.String(20), nullable=True,
    ))
    op.add_column('obligations', sa.Column(
        'evidence_segment_ids',
        postgresql.JSONB(astext_type=sa.Text()), nullable=True,
    ))
    op.add_column('obligations', sa.Column(
        'raw_extraction',
        postgresql.JSONB(astext_type=sa.Text()), nullable=True,
    ))
    op.create_index('ix_obligations_run_id', 'obligations', ['run_id'])
    op.create_index('ix_obligations_lens_config_id', 'obligations', ['lens_config_id'])


def downgrade() -> None:
    op.drop_index('ix_obligations_lens_config_id')
    op.drop_index('ix_obligations_run_id')
    op.drop_column('obligations', 'raw_extraction')
    op.drop_column('obligations', 'evidence_segment_ids')
    op.drop_column('obligations', 'extraction_method')
    op.drop_column('obligations', 'lens_config_id')
    op.drop_column('obligations', 'run_id')

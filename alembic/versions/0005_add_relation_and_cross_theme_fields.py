"""add relation run_id and cross-theme obligation_ids

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('obligation_relations', sa.Column(
        'run_id', sa.String(36),
        sa.ForeignKey('analysis_runs.id'), nullable=True,
    ))
    op.create_index('ix_obligation_relations_run_id', 'obligation_relations', ['run_id'])

    op.add_column('cross_theme_finding_candidates', sa.Column(
        'obligation_ids_theme_a',
        postgresql.JSONB(astext_type=sa.Text()), nullable=True,
    ))
    op.add_column('cross_theme_finding_candidates', sa.Column(
        'obligation_ids_theme_b',
        postgresql.JSONB(astext_type=sa.Text()), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('cross_theme_finding_candidates', 'obligation_ids_theme_b')
    op.drop_column('cross_theme_finding_candidates', 'obligation_ids_theme_a')
    op.drop_index('ix_obligation_relations_run_id')
    op.drop_column('obligation_relations', 'run_id')

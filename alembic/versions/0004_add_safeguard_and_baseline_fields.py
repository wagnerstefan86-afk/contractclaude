"""add safeguard and baseline match fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MissingSafeguard: make finding_id nullable, add run_id, lens_config_id, obligation_id, status
    op.alter_column('missing_safeguards', 'finding_id', nullable=True)
    op.add_column('missing_safeguards', sa.Column(
        'run_id', sa.String(36),
        sa.ForeignKey('analysis_runs.id'), nullable=True,
    ))
    op.add_column('missing_safeguards', sa.Column(
        'lens_config_id', sa.String(36),
        sa.ForeignKey('lens_configs.id'), nullable=True,
    ))
    op.add_column('missing_safeguards', sa.Column(
        'obligation_id', sa.String(36),
        sa.ForeignKey('obligations.id'), nullable=True,
    ))
    op.add_column('missing_safeguards', sa.Column(
        'status', sa.String(20), nullable=False, server_default='missing',
    ))
    op.create_index('ix_missing_safeguards_run_id', 'missing_safeguards', ['run_id'])
    op.create_index('ix_missing_safeguards_lens_config_id', 'missing_safeguards', ['lens_config_id'])

    # Obligation: add baseline_match_status, baseline_gap_description
    op.add_column('obligations', sa.Column(
        'baseline_match_status', sa.String(30), nullable=True,
    ))
    op.add_column('obligations', sa.Column(
        'baseline_gap_description', sa.Text(), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('obligations', 'baseline_gap_description')
    op.drop_column('obligations', 'baseline_match_status')
    op.drop_index('ix_missing_safeguards_lens_config_id')
    op.drop_index('ix_missing_safeguards_run_id')
    op.drop_column('missing_safeguards', 'status')
    op.drop_column('missing_safeguards', 'obligation_id')
    op.drop_column('missing_safeguards', 'lens_config_id')
    op.drop_column('missing_safeguards', 'run_id')
    op.alter_column('missing_safeguards', 'finding_id', nullable=False)

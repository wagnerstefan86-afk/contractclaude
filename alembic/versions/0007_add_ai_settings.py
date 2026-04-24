"""add ai_settings singleton + analysis_runs llm snapshot fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-24

The ai_settings table is a strict singleton (id = 1). One active LLM
provider per instance; no per-contract routing, no policy engine.

Two new columns on analysis_runs carry the provider + model that were
active at run-start, so we keep a retrospective trace even if the
active provider is later changed in the UI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "active_provider", sa.String(length=20),
            nullable=False,
            server_default="openai",
        ),
        sa.Column("local_base_url", sa.String(length=500), nullable=True),
        sa.Column("local_model", sa.String(length=200), nullable=True),
        sa.Column("local_api_key", sa.String(length=500), nullable=True),
        sa.Column("openai_api_key", sa.String(length=500), nullable=True),
        sa.Column("openai_model", sa.String(length=200), nullable=True),
        sa.Column("openai_base_url", sa.String(length=500), nullable=True),
        sa.Column("gemini_api_key", sa.String(length=500), nullable=True),
        sa.Column("gemini_model", sa.String(length=200), nullable=True),
        sa.Column("anthropic_api_key", sa.String(length=500), nullable=True),
        sa.Column("anthropic_model", sa.String(length=200), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed default singleton so the UI has a row to update from day one.
    # active_provider stays "openai" to preserve the existing-instance
    # behaviour until a human actively switches in the UI.
    op.execute(
        "INSERT INTO ai_settings (id, active_provider) VALUES (1, 'openai') "
        "ON CONFLICT (id) DO NOTHING"
    )

    # Per-run snapshot of provider/model for retrospective trace.
    op.add_column(
        "analysis_runs",
        sa.Column("llm_provider", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("llm_model", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "llm_model")
    op.drop_column("analysis_runs", "llm_provider")
    op.drop_table("ai_settings")

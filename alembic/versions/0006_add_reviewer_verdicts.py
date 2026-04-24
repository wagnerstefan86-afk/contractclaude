"""add reviewer_verdicts (shadow-mode pipeline feedback, 1:1 per finding)

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reviewer_verdicts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "finding_id",
            sa.String(length=36),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        # Stored as plain string. Allowed values are enforced in app
        # logic (schemas + endpoint), not via a DB enum, so values can
        # evolve without a migration.
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        # Reviewer is a placeholder field only — no auth, no dropdown,
        # no user model. Kept optional for later attribution.
        sa.Column("reviewer", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("reviewer_verdicts")

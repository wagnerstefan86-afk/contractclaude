"""add segment page_start / page_end (segments can span pages)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-25

The PDF parser already produces page_from / page_to per segment; the
DB previously only stored a single ``page_number`` field. This
migration adds explicit ``page_start`` / ``page_end`` columns and
backfills them from the existing single value so existing data keeps
working. ``page_number`` stays as a non-breaking convenience column.

DOCX-sourced segments have no reliable page info — those rows keep
``page_start`` / ``page_end`` as NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("segments", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("segments", sa.Column("page_end", sa.Integer(), nullable=True))
    # Backfill: every previously stored single page becomes both start
    # and end. Segments with NULL page_number stay NULL.
    op.execute(
        "UPDATE segments SET page_start = page_number, page_end = page_number "
        "WHERE page_number IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("segments", "page_end")
    op.drop_column("segments", "page_start")

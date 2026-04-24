"""Reviewer-Verdict model — 1:1 shadow-mode feedback per finding.

Separate datenebene vom Business-`status` (open/accepted/...). Das
Verdict-Feld signalisiert, ob die Pipeline fachlich richtig lag; der
Business-Status bleibt davon unabhängig.

Nur ein Datensatz pro Finding (UPSERT). Keine Historie, keine Audit-
Log-Tabelle — `updated_at` reicht für diesen Shadow-Mode-Schritt.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ALLOWED_VERDICTS = (
    "correct",
    "false_positive",
    "false_negative",
    "review_only",
)


class ReviewerVerdict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reviewer_verdicts"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Not a DB enum — allowed values enforced in schemas + endpoint.
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)

    finding = relationship("Finding", backref="reviewer_verdict", uselist=False)

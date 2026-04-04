from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import FindingSeverity, FindingStatus, Materiality, ReviewDecisionType, Theme


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "findings"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False, index=True
    )
    theme: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=10), nullable=False
    )
    materiality: Mapped[Materiality] = mapped_column(
        Enum(Materiality, native_enum=False, length=10), nullable=False
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, native_enum=False, length=10), nullable=False, default=FindingStatus.OPEN
    )
    playbook_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("playbook_entries.id"), nullable=True
    )
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidences: Mapped[list["Evidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    missing_safeguards: Mapped[list["MissingSafeguard"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    review_decision: Mapped["ReviewDecision | None"] = relationship(
        back_populates="finding", cascade="all, delete-orphan", uselist=False
    )


class Evidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidences"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id"), nullable=False, index=True
    )
    obligation_id: Mapped[str | None] = mapped_column(
        ForeignKey("obligations.id"), nullable=True
    )
    segment_id: Mapped[str | None] = mapped_column(
        ForeignKey("segments.id"), nullable=True
    )
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship(back_populates="evidences")


class MissingSafeguard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "missing_safeguards"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id"), nullable=False, index=True
    )
    safeguard_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship(back_populates="missing_safeguards")


class ReviewDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_decisions"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id"), nullable=False, unique=True, index=True
    )
    decision: Mapped[ReviewDecisionType] = mapped_column(
        Enum(ReviewDecisionType, native_enum=False, length=10), nullable=False
    )
    reviewer: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship(back_populates="review_decision")

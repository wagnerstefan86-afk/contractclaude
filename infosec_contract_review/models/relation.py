from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import Materiality, RelationType, Theme


class ObligationRelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "obligation_relations"

    obligation_a_id: Mapped[str] = mapped_column(
        ForeignKey("obligations.id"), nullable=False, index=True
    )
    obligation_b_id: Mapped[str] = mapped_column(
        ForeignKey("obligations.id"), nullable=False, index=True
    )
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType, native_enum=False, length=20), nullable=False
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)


class CrossThemeFindingCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cross_theme_finding_candidates"

    rule_id: Mapped[str] = mapped_column(
        ForeignKey("cross_theme_rules.id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    materiality: Mapped[Materiality] = mapped_column(
        Enum(Materiality, native_enum=False, length=10), nullable=False
    )

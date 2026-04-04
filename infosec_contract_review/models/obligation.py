from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import Materiality, ObligationDirection, ObligationType, Theme


class Obligation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "obligations"

    segment_id: Mapped[str] = mapped_column(
        ForeignKey("segments.id"), nullable=False, index=True
    )
    theme: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False, index=True
    )
    obligation_type: Mapped[ObligationType] = mapped_column(
        Enum(ObligationType, native_enum=False, length=10), nullable=False
    )
    direction: Mapped[ObligationDirection] = mapped_column(
        Enum(ObligationDirection, native_enum=False, length=20), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    verbatim_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    materiality: Mapped[Materiality] = mapped_column(
        Enum(Materiality, native_enum=False, length=10), nullable=False
    )
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)

    limits: Mapped["ObligationLimits | None"] = relationship(
        back_populates="obligation", cascade="all, delete-orphan", uselist=False
    )


class ObligationLimits(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "obligation_limits"

    obligation_id: Mapped[str] = mapped_column(
        ForeignKey("obligations.id"), nullable=False, unique=True, index=True
    )
    frequency_limit: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_limit: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_limit: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_limit: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_limits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    obligation: Mapped["Obligation"] = relationship(back_populates="limits")

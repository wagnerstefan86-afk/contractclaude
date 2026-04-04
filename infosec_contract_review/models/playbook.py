from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import Theme


class PlaybookEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "playbook_entries"

    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    theme: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False, index=True
    )
    risk_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    standard_position: Mapped[str] = mapped_column(Text, nullable=False)
    alt_wordings: Mapped[list] = mapped_column(JSONB, nullable=False)
    bidder_questions: Mapped[list] = mapped_column(JSONB, nullable=False)
    applicable_when: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)

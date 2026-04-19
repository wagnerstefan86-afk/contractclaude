from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import SegmentType


class Segment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "segments"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_type: Mapped[SegmentType] = mapped_column(
        Enum(SegmentType, native_enum=False, length=20), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    heading_path: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    routing_tier: Mapped[str | None] = mapped_column(String(30), nullable=True)
    deterministic_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    routed_themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parse_quality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    preceding_segment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    following_segment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

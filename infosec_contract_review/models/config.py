from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import Materiality, Theme


class LensConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lens_configs"

    lens_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    theme: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False
    )
    prompt_template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    segment_filter: Mapped[dict] = mapped_column(JSONB, nullable=False)
    include_neighbor_context: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_segments_per_call: Mapped[int] = mapped_column(default=25, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)

    expected_safeguards: Mapped[list["ExpectedSafeguard"]] = relationship(
        back_populates="lens_config", cascade="all, delete-orphan"
    )


class ExpectedSafeguard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "expected_safeguards"

    lens_config_id: Mapped[str] = mapped_column(
        ForeignKey("lens_configs.id"), nullable=False, index=True
    )
    safeguard_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    maps_to_limit_field: Mapped[str | None] = mapped_column(String(100), nullable=True)

    lens_config: Mapped["LensConfig"] = relationship(back_populates="expected_safeguards")


class CrossThemeRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cross_theme_rules"

    rule_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    theme_a: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False
    )
    theme_b: Mapped[Theme] = mapped_column(
        Enum(Theme, native_enum=False, length=40), nullable=False
    )
    trigger_condition: Mapped[str] = mapped_column(Text, nullable=False)
    check_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    default_materiality_floor: Mapped[Materiality] = mapped_column(
        Enum(Materiality, native_enum=False, length=10), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)

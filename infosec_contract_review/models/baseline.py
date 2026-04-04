from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import DeliveryModel, ServiceType, TenantModel


class ProviderBaseline(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provider_baselines"

    version: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan"
    )
    standard_positions: Mapped[list["StandardPosition"]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan"
    )
    service_profiles: Mapped[list["ServiceProfile"]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan"
    )


class Certification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "baseline_certifications"

    baseline_id: Mapped[str] = mapped_column(
        ForeignKey("provider_baselines.id"), nullable=False, index=True
    )
    standard: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[str | None] = mapped_column(String(10), nullable=True)
    covers_all_services: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    excluded_services: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    baseline: Mapped["ProviderBaseline"] = relationship(back_populates="certifications")


class StandardPosition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "baseline_standard_positions"

    baseline_id: Mapped[str] = mapped_column(
        ForeignKey("provider_baselines.id"), nullable=False, index=True
    )
    theme: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    accepted: Mapped[str] = mapped_column(Text, nullable=False)
    not_accepted: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_threshold: Mapped[str] = mapped_column(Text, nullable=False)

    baseline: Mapped["ProviderBaseline"] = relationship(back_populates="standard_positions")


class ServiceProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "baseline_service_profiles"

    baseline_id: Mapped[str] = mapped_column(
        ForeignKey("provider_baselines.id"), nullable=False, index=True
    )
    service_type: Mapped[ServiceType] = mapped_column(
        Enum(ServiceType, native_enum=False, length=30), nullable=False
    )
    delivery_model: Mapped[DeliveryModel] = mapped_column(
        Enum(DeliveryModel, native_enum=False, length=20), nullable=False
    )
    tenant_model: Mapped[TenantModel] = mapped_column(
        Enum(TenantModel, native_enum=False, length=20), nullable=False
    )
    baseline_controls: Mapped[list] = mapped_column(JSONB, nullable=False)

    baseline: Mapped["ProviderBaseline"] = relationship(back_populates="service_profiles")

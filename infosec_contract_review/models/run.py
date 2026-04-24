from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import RunStatus, StepType


class AnalysisRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_runs"

    package_id: Mapped[str] = mapped_column(
        ForeignKey("contract_packages.id"), nullable=False, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=10), nullable=False, default=RunStatus.PENDING
    )
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshot of the active LLM provider + model at run start (Phase 4).
    # Not used for pipeline branching; retrospective trace only.
    llm_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    steps: Mapped[list["RunStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "run_steps"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False, index=True
    )
    step_type: Mapped[StepType] = mapped_column(
        Enum(StepType, native_enum=False, length=20), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=10), nullable=False, default=RunStatus.PENDING
    )
    input_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["AnalysisRun"] = relationship(back_populates="steps")

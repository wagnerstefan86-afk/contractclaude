"""AI provider settings — strict singleton (id = 1).

One active LLM provider per instance. No per-contract routing, no
policy engine, no audit trail. The row is updated in place; nothing
is inserted beyond the seed default.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


ALLOWED_PROVIDERS = ("local", "openai", "gemini", "anthropic")


class AiSettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="openai", server_default="openai"
    )

    local_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    local_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    local_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    openai_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    openai_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    openai_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    gemini_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gemini_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    anthropic_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    anthropic_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

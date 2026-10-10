"""Audit trail of every governed AI call (usage, latency, mode)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AiCall(Base):
    __tablename__ = "ai_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(64), default="general")
    actor_id: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(64), default="")
    mode: Mapped[str] = mapped_column(String(16), default="stub")  # live | stub
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    preview: Mapped[str] = mapped_column(Text, default="")  # first chars of output
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

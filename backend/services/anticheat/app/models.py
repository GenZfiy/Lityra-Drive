"""Anti-cheating models (schema: drive_anticheat)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ProctorSession(Base):
    __tablename__ = "proctor_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    exam_session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    drive_id: Mapped[str | None] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))
    browser: Mapped[str | None] = mapped_column(String(128))
    violation_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|flagged|auto_submitted
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    proctor_session_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str | None] = mapped_column(String(64))
    browser: Mapped[str | None] = mapped_column(String(128))
    device: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

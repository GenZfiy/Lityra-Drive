"""Notification models (schema: shared_notify)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("key", "channel", "locale", name="uq_template"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(16))  # email|inapp|sms|whatsapp
    locale: Mapped[str] = mapped_column(String(8), default="en")
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(4096))
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Critical templates (security/exam) ignore channel preferences.
    critical: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    template_key: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(4096), default="")
    # queued|sent|suppressed|failed|not_configured
    status: Mapped[str] = mapped_column(String(16), default="queued")
    dedupe_key: Mapped[str | None] = mapped_column(String(128), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_preference"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

"""The attention engine's derived actions (schema: drive_action).

Actions are regenerated from current cross-service state (evidence conflicts,
decision queue). A ``dedupe_key`` keeps regeneration idempotent; resolution /
dismissal is user state that survives regeneration.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("drive_id", "dedupe_key", name="uq_action_dedupe"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(12), default="medium")  # critical|high|medium
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text)
    target_ref: Mapped[str | None] = mapped_column(String(64))
    impact_note: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(12), default="open")  # open|resolved|dismissed
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

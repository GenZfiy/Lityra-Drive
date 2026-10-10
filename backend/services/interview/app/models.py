"""Interview models (schema: drive_interview)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    round_id: Mapped[str | None] = mapped_column(String(64))
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(24), default="technical")  # technical|hr|ppo
    mode: Mapped[str] = mapped_column(String(16), default="online")  # online|in_person
    link: Mapped[str | None] = mapped_column(String(512))
    slot: Mapped[str | None] = mapped_column(String(64))
    interviewer_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled|completed
    decision: Mapped[str | None] = mapped_column(String(16))  # select|reject|hold|next_round
    decision_reason: Mapped[str | None] = mapped_column(String(512))
    avg_rating: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    interviewer_id: Mapped[str] = mapped_column(String(64))
    competency: Mapped[str] = mapped_column(String(32))  # technical|communication|problem_solving|culture
    score: Mapped[float] = mapped_column(Float)  # 1..5
    remark: Mapped[str | None] = mapped_column(String(512))

"""Result & offer models (schema: drive_result)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("drive_id", "candidate_id", name="uq_result"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16), default="fail")  # pass|fail|shortlist|selected
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|published
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    role_id: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(8), default="offer")  # offer | ppo
    company_name: Mapped[str | None] = mapped_column(String(255))
    role_title: Mapped[str | None] = mapped_column(String(255))
    ctc: Mapped[str | None] = mapped_column(String(64))
    letter_file_id: Mapped[str | None] = mapped_column(String(64))
    verify_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="issued")  # issued|accepted|declined
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

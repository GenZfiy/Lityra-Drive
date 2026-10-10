"""Submission models (schema: drive_submission).

Append-only answer history + a materialized latest view + immutable final
snapshot. Guarantees no accepted-answer loss (SB-1..SB-7)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AnswerEvent(Base):
    """Append-only: every write is a new row (never updated/deleted)."""
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="autosave")  # autosave|final
    client_seq: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AnswerLatest(Base):
    """Materialized last-write-wins latest answer per (session, question)."""
    __tablename__ = "answer_latest"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_latest"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    client_seq: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class TimeSpent(Base):
    __tablename__ = "time_spent"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_time"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64))
    seconds: Mapped[int] = mapped_column(Integer, default=0)


class FinalSubmission(Base):
    __tablename__ = "final_submissions"
    __table_args__ = (UniqueConstraint("session_id", name="uq_final"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # {question_id: response}
    answer_count: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finalized: Mapped[bool] = mapped_column(Boolean, default=True)

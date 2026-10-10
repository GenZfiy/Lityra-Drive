"""Exam engine models (schema: drive_exam).

The Exam Engine owns session + timing + section-lock state and the *latest*
answer per question (for resume). The Submission Service owns the durable,
append-only answer history (auto-save mirrors there in production)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str | None] = mapped_column(String(64), index=True)
    round_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    total_time_min: Mapped[int] = mapped_column(Integer, default=60)
    negative_marking: Mapped[float] = mapped_column(Float, default=0.0)
    nav_rule: Mapped[str] = mapped_column(String(8), default="free")  # free | linear
    # sections: [{"id","title","order","time_limit_min",
    #             "questions":[{"id","type","stem","options","weight"}]}]
    sections: Mapped[list] = mapped_column(JSON, default=list)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExamSession(Base):
    __tablename__ = "exam_sessions"
    __table_args__ = (UniqueConstraint("exam_id", "candidate_id", name="uq_session"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress|submitted|expired
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # section_state: {section_id: {"locked":bool}}
    section_state: Mapped[dict] = mapped_column(JSON, default=dict)
    auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False)


class ExamAnswer(Base):
    """Latest answer per (session, question) — for resume. Durable append-only
    history lives in the Submission Service."""
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_answer"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

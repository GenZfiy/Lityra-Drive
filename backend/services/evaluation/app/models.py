"""Evaluation models (schema: drive_evaluation)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    exam_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # [{"question_id","type","correct","weight"}] — correct never exposed
    items: Mapped[list] = mapped_column(JSON, default=list)
    passing_pct: Mapped[int] = mapped_column(Integer, default=60)
    negative_marking: Mapped[float] = mapped_column(Float, default=0.0)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("session_id", name="uq_eval_session"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Set when a coding item could not be executed due to a SYSTEM error (never a
    # student error) — those items are held for manual review, not auto-zeroed.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    question_scores: Mapped[list] = mapped_column(JSON, default=list)  # [{qid,awarded,max,correct}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Rank(Base):
    __tablename__ = "ranks"
    __table_args__ = (UniqueConstraint("exam_id", "candidate_id", name="uq_rank"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64))
    rank: Mapped[int] = mapped_column(Integer)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    tie_break: Mapped[str | None] = mapped_column(String(128))

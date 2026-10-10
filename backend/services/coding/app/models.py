"""Coding assessment models (schema: drive_coding)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255))
    statement: Mapped[str] = mapped_column(String(4096))
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["python"])
    time_limit_sec: Mapped[int] = mapped_column(Integer, default=5)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    # [{"input":"..","expected":".."}] — samples are visible, hidden are not
    sample_cases: Mapped[list] = mapped_column(JSON, default=list)
    hidden_cases: Mapped[list] = mapped_column(JSON, default=list)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)
    # LMS practice metadata — feeds the Cognitive Twin (skill map). A problem is
    # exposed in the Lityra Learn practice bank only when practice=True; Drive exam
    # problems keep the default and never appear there.
    skill: Mapped[str] = mapped_column(String(64), default="General")  # e.g. Arrays, Strings, DP
    difficulty: Mapped[str] = mapped_column(String(16), default="easy")  # easy|medium|hard
    practice: Mapped[bool] = mapped_column(Boolean, default=False)


class CodingSession(Base):
    __tablename__ = "coding_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    problem_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    exam_session_id: Mapped[str | None] = mapped_column(String(64))
    # "exam" (Drive coding round) or "practice" (Lityra Learn practice). Only
    # practice sessions feed the LMS skill map.
    kind: Mapped[str] = mapped_column(String(16), default="exam", index=True)
    language: Mapped[str] = mapped_column(String(16), default="python")
    draft_code: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|submitted
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class CodingSubmission(Base):
    __tablename__ = "coding_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    coding_session_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    cases_passed: Mapped[int] = mapped_column(Integer, default=0)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[list] = mapped_column(JSON, default=list)  # per-hidden-case pass/fail (no expected)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CodingViva(Base):
    """Adversarial viva: after a submission, the AI asks the author to explain
    their approach and grades the explanation. Passing tests + explaining *why*
    it works is far harder to fake than a pasted solution — this is what makes a
    'verified skill' actually mean something (cheat-resistant proof of competence)."""
    __tablename__ = "coding_vivas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    coding_session_id: Mapped[str] = mapped_column(String(64), index=True)
    problem_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(String(1024), default="")
    answer: Mapped[str] = mapped_column(String(4096), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    verdict: Mapped[str] = mapped_column(String(1024), default="")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="asked")  # asked|graded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

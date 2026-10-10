"""Question bank models (schema: drive_questionbank)."""
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


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # mcq | multi | fill_blank | match | true_false | coding | sql | output
    type: Mapped[str] = mapped_column(String(16), index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)  # aptitude|technical|verbal|programming
    difficulty: Mapped[str] = mapped_column(String(8), default="easy", index=True)  # easy|medium|hard
    tags: Mapped[list] = mapped_column(JSON, default=list)
    stem: Mapped[str] = mapped_column(String(2048))
    options: Mapped[list] = mapped_column(JSON, default=list)   # [{id,text}]
    # answer key: {"option":"b"} | {"options":[...]} | {"answer":"..."} | {"testcase_set_id":"..."}
    answer_key: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str | None] = mapped_column(String(1024))
    weight: Mapped[float] = mapped_column(default=1.0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|active|retired
    author_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Blueprint(Base):
    __tablename__ = "blueprints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    # spec: [{"category":"aptitude","difficulty":"easy","count":5}, ...]
    spec: Mapped[list] = mapped_column(JSON, default=list)

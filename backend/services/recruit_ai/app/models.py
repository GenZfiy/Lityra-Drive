"""Recruitment insights + interviewer calibration (schema: drive_recruit_ai).

Insights follow the Observation -> Reason -> Impact -> Recommended-Action
contract the UI renders verbatim. In this cut they are *derived* deterministically
from evidence + the decision queue (mode = "derived"); an LLM narration layer via
ai_orchestration can be added later without changing the stored shape.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(12), default="brand")  # risk|warn|brand|teal
    title: Mapped[str] = mapped_column(String(255))
    observation: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[dict] = mapped_column(JSON, default=dict)
    related_refs: Mapped[list] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(12), default="derived")  # derived|live
    model: Mapped[str] = mapped_column(String(40), default="rule-based")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Calibration(Base):
    __tablename__ = "calibration"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    interviewer_id: Mapped[str] = mapped_column(String(64))
    competency_key: Mapped[str] = mapped_column(String(64))
    mean_delta: Mapped[float] = mapped_column(Float, default=0.0)  # signal pts vs consensus
    sample_n: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

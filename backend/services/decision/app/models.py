"""Decisions with immutable evidence lineage (schema: drive_decision).

A decision records an advance/hold/reject that cites the exact evidence it was
based on (``decision_evidence``). Coverage, agreement, and missing competencies
are computed deterministically at decision time and stored for audit.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    round_key: Mapped[str | None] = mapped_column(String(64))
    verdict: Mapped[str] = mapped_column(String(12))  # advance|hold|reject
    decided_by: Mapped[str | None] = mapped_column(String(64))
    evidence_coverage_pct: Mapped[float | None] = mapped_column(Float)
    panel_agreement: Mapped[str] = mapped_column(String(12), default="unknown")  # aligned|divergent|unknown
    missing_competencies: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    cited: Mapped[list["DecisionEvidence"]] = relationship(cascade="all, delete-orphan")


class DecisionEvidence(Base):
    """Immutable lineage: the exact evidence rows a decision cited."""

    __tablename__ = "decision_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(64))

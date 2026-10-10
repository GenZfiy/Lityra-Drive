"""Append-only evidence ledger (schema: drive_evidence).

Every score in LARE Drive derives from typed, sourced, confidence-tagged
evidence rows recorded here — rankings, decisions, and AI insights all trace
back to these rows. Rows are INSERT-only at the application layer (there are no
update/delete routes). Phase 6 hardens this at the database with grants that
revoke UPDATE/DELETE on these tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


SOURCE_TYPES = ("assessment", "interview", "coding", "referral", "screen")
CONFIDENCE = ("high", "medium", "low")


class Evidence(Base):
    """One typed, sourced observation about a candidate, mapped to a competency."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    competency_key: Mapped[str] = mapped_column(String(64), index=True, default="overall")
    source_type: Mapped[str] = mapped_column(String(24))  # SOURCE_TYPES
    source_ref: Mapped[str | None] = mapped_column(String(128))
    signal: Mapped[float] = mapped_column(Float)  # normalised 0..100
    confidence: Mapped[str] = mapped_column(String(8), default="medium")  # CONFIDENCE
    rationale: Mapped[str | None] = mapped_column(Text)
    round_key: Mapped[str | None] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(64))  # who/what produced it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvidenceConflict(Base):
    """A materialised divergence between two evidence rows for the same
    candidate + competency. Detected on append; resolution is user state."""

    __tablename__ = "evidence_conflicts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    competency_key: Mapped[str] = mapped_column(String(64))
    evidence_a: Mapped[str] = mapped_column(String(64))
    evidence_b: Mapped[str] = mapped_column(String(64))
    delta: Mapped[float] = mapped_column(Float)  # signal-point gap
    status: Mapped[str] = mapped_column(String(12), default="open")  # open|resolved
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


Index("ix_evidence_drive_cand_comp", Evidence.drive_id, Evidence.candidate_id, Evidence.competency_key)

"""Competency catalogue + per-drive evaluation models (schema: drive_competency).

The evaluation model — which competencies a drive hires for and their weights —
changes independently of the drive lifecycle, so it lives in its own service.
One active model per drive; setting a new one deactivates the previous.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvaluationModel(Base):
    __tablename__ = "evaluation_models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    weights: Mapped[list["ModelWeight"]] = relationship(cascade="all, delete-orphan")


class ModelWeight(Base):
    __tablename__ = "model_weights"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    model_id: Mapped[str] = mapped_column(ForeignKey("evaluation_models.id", ondelete="CASCADE"), index=True)
    competency_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    band_good: Mapped[float] = mapped_column(Float, default=75.0)
    band_warn: Mapped[float] = mapped_column(Float, default=50.0)

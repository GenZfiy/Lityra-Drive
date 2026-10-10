"""Analytics models (schema: shared_analytics).

A generic append-only fact store fed by domain events, plus read-side
aggregations computed on demand (materialized views in production)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


class DashboardLayout(Base):
    """Per-user customizable dashboard widget layout (req #24)."""
    __tablename__ = "dashboard_layouts"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # widgets: [{id, type, w, h, x, y, config}]
    widgets: Mapped[list] = mapped_column(JSON, default=list)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # learner|college|drive
    college_id: Mapped[str | None] = mapped_column(String(64), index=True)
    cohort_id: Mapped[str | None] = mapped_column(String(64))
    learner_id: Mapped[str | None] = mapped_column(String(64), index=True)
    drive_id: Mapped[str | None] = mapped_column(String(64), index=True)
    metric: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

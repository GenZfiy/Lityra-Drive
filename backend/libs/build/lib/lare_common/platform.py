"""Cross-cutting platform primitives shared by every service:

* Feature flags  — enable/disable features without code changes (env + Redis
  override; per-tenant overrides supported).
* Soft delete / retention — a mixin + helpers for PII-safe soft deletion,
  archival, and consent tracking (compliance).
* Tagging — a normaliser used by the shared Tag model everywhere.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .redis_helper import get_redis


# ---------------- feature flags ----------------
# Defaults (safe). Override via env FLAG_<NAME>=true/false, or per-tenant in
# Redis key flag:<tenant>:<name>. Read once per call — cheap.
_DEFAULTS = {
    "resume_parsing": True,
    "ai_resume_ranking": True,
    "hall_tickets": True,
    "seat_allocation": True,
    "dynamic_offer_letters": True,
    "question_approval": True,
    "global_search": True,
    "workflow_automation": True,
    "advanced_analytics": True,
}


def feature_enabled(name: str, tenant_id: str | None = None) -> bool:
    env = os.getenv(f"FLAG_{name.upper()}")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    if tenant_id:
        r = get_redis(os.getenv("REDIS_URL", ""))
        if r is not None:
            try:
                v = r.get(f"flag:{tenant_id}:{name}")
                if v is not None:
                    return str(v).lower() in ("1", "true", "yes", "on")
            except Exception:  # noqa: BLE001
                pass
    return _DEFAULTS.get(name, False)


def all_flags(tenant_id: str | None = None) -> dict[str, bool]:
    return {k: feature_enabled(k, tenant_id) for k in _DEFAULTS}


# ---------------- soft delete / retention (compliance) ----------------
def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class SoftDeleteMixin:
    """Add soft-delete + archive columns to any model for data-retention and
    PII compliance. Queries should filter ``deleted_at.is_(None)`` for live rows."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_erased: Mapped[bool] = mapped_column(Boolean, default=False)


def soft_delete(obj) -> None:
    obj.deleted_at = _utcnow()


def erase_pii(obj, fields: list[str], placeholder: str = "[erased]") -> None:
    """Right-to-be-forgotten: null/placeholder PII fields, keep the row for audit."""
    for f in fields:
        if hasattr(obj, f):
            setattr(obj, f, placeholder)
    obj.pii_erased = True


# ---------------- tagging ----------------
def normalize_tags(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = raw.split(",")
    seen: list[str] = []
    for t in raw:
        t = str(t).strip().lower().replace(" ", "-")
        if t and t not in seen:
            seen.append(t)
    return seen

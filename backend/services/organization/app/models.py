"""Organization layer above companies/colleges (req #2).

An organization owns a tenant and carries branding, a custom domain, SMTP config,
timezone, a security policy, and per-org feature-flag overrides. Companies and
colleges reference an org via tenant_id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from lare_common.db import Base
from lare_common.platform import SoftDeleteMixin


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Organization(Base, SoftDeleteMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    custom_domain: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(48), default="Asia/Kolkata")

    # JSON blobs for flexible config.
    branding: Mapped[dict] = mapped_column(JSON, default=dict)        # logo_url, primary_color, ...
    smtp_config: Mapped[dict] = mapped_column(JSON, default=dict)     # host, port, user, from (secrets in vault)
    security_policy: Mapped[dict] = mapped_column(JSON, default=dict) # password_min_len, mfa_required, session_timeout_min
    feature_overrides: Mapped[dict] = mapped_column(JSON, default=dict)  # {flag: bool}

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


DEFAULT_SECURITY = {
    "password_min_len": 8,
    "mfa_required": False,
    "session_timeout_min": 30,
    "allowed_login_attempts": 5,
}

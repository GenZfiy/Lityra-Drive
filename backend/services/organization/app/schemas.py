from __future__ import annotations

from pydantic import BaseModel, Field


class OrgIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=80, pattern="^[a-z0-9-]+$")
    tenant_id: str | None = None
    timezone: str = "Asia/Kolkata"
    custom_domain: str | None = None
    branding: dict = Field(default_factory=dict)


class OrgUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    custom_domain: str | None = None
    branding: dict | None = None
    smtp_config: dict | None = None
    security_policy: dict | None = None
    feature_overrides: dict | None = None

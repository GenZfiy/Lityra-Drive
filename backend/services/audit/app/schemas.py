from __future__ import annotations

from pydantic import BaseModel, Field


class AuditIn(BaseModel):
    partition_key: str = Field(default="global", max_length=64)
    actor_type: str = Field(default="user", pattern="^(user|service)$")
    actor_id: str | None = None
    action: str = Field(min_length=1, max_length=64)
    entity_type: str | None = None
    entity_id: str | None = None
    meta: dict = {}
    ip: str | None = None
    device: str | None = None
    correlation_id: str | None = None


class ActivityIn(BaseModel):
    user_id: str | None = None
    session_id: str | None = None
    event: str = Field(min_length=1, max_length=64)
    context: dict = {}

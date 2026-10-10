from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateIn(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    channel: str = Field(pattern="^(email|inapp|sms|whatsapp)$")
    locale: str = "en"
    subject: str | None = None
    body: str = Field(min_length=1, max_length=4096)
    critical: bool = False


class SendIn(BaseModel):
    user_id: str
    template_key: str
    channel: str = Field(pattern="^(email|inapp|sms|whatsapp)$")
    locale: str = "en"
    variables: dict = {}
    dedupe_key: str | None = None


class PreferenceIn(BaseModel):
    channel: str = Field(pattern="^(email|inapp|sms|whatsapp)$")
    enabled: bool

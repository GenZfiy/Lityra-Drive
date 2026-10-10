from __future__ import annotations

from pydantic import BaseModel, Field


class UploadUrlIn(BaseModel):
    purpose: str = Field(pattern="^(resume|avatar|certificate|content|code|report|proctor)$")
    filename: str | None = None
    mime: str
    size: int = Field(ge=1)
    entity_type: str | None = None
    entity_id: str | None = None

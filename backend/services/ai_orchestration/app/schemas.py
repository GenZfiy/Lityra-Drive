from __future__ import annotations

from pydantic import BaseModel, Field


class CompleteIn(BaseModel):
    prompt_key: str = Field(min_length=1)
    variables: dict = Field(default_factory=dict)
    purpose: str = "general"
    want_json: bool = False
    history: list[dict] | None = None
    json_fallback: dict | None = None

from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionIn(BaseModel):
    drive_id: str = Field(min_length=1, max_length=64)
    candidate_id: str = Field(min_length=1, max_length=64)
    round_key: str | None = Field(default=None, max_length=64)
    verdict: str = Field(pattern="^(advance|hold|reject)$")
    note: str | None = None
    evidence_ids: list[str] = []

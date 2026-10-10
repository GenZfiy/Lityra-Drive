from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceIn(BaseModel):
    drive_id: str = Field(min_length=1, max_length=64)
    candidate_id: str = Field(min_length=1, max_length=64)
    competency_key: str = Field(default="overall", min_length=1, max_length=64)
    source_type: str = Field(pattern="^(assessment|interview|coding|referral|screen)$")
    source_ref: str | None = Field(default=None, max_length=128)
    signal: float = Field(ge=0, le=100)
    confidence: str = Field(default="medium", pattern="^(high|medium|low)$")
    rationale: str | None = None
    round_key: str | None = Field(default=None, max_length=64)

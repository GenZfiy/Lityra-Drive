from __future__ import annotations

from pydantic import BaseModel, Field


class FactIn(BaseModel):
    kind: str = Field(pattern="^(learner|college|drive)$")
    metric: str = Field(min_length=1, max_length=32)
    value: float = 0.0
    college_id: str | None = None
    cohort_id: str | None = None
    learner_id: str | None = None
    drive_id: str | None = None


class IngestIn(BaseModel):
    facts: list[FactIn]

from __future__ import annotations

from pydantic import BaseModel, Field


class ResultRow(BaseModel):
    candidate_id: str
    final_score: float = Field(ge=0)
    interview_decision: str | None = None  # select|reject|hold|next_round


class CompileIn(BaseModel):
    drive_id: str
    cutoff: float = Field(default=60.0, ge=0, le=100)
    rows: list[ResultRow]


class OfferIn(BaseModel):
    drive_id: str
    candidate_id: str
    role_id: str | None = None
    type: str = Field(default="offer", pattern="^(offer|ppo)$")
    company_name: str | None = None
    role_title: str | None = None
    ctc: str | None = None


class OfferStatusIn(BaseModel):
    status: str = Field(pattern="^(accepted|declined)$")


class ExportIn(BaseModel):
    format: str = Field(default="csv", pattern="^(csv|excel|pdf)$")

from __future__ import annotations

from pydantic import BaseModel, Field


class KeyItem(BaseModel):
    question_id: str
    type: str = Field(pattern="^(mcq|multi|true_false|coding)$")
    correct: dict = {}      # {"option":"b"} | {"options":[...]} ; empty for coding
    weight: float = Field(default=1.0, gt=0)
    # coding only: all test cases (sample + hidden) to run against, and a
    # fallback language if the submission doesn't record one.
    cases: list = []        # [{"input": "...", "expected": "..."}]
    language: str | None = None


class KeyIn(BaseModel):
    exam_id: str
    items: list[KeyItem]
    passing_pct: int = Field(default=60, ge=0, le=100)
    negative_marking: float = Field(default=0.0, ge=0)


class RunIn(BaseModel):
    exam_id: str
    session_id: str
    candidate_id: str
    answers: dict = {}          # {question_id: response}
    coding_scores: dict = {}    # {question_id: numeric score (already computed)}


class RankIn(BaseModel):
    exam_id: str

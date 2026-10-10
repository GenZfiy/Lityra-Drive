from __future__ import annotations

from pydantic import BaseModel, Field


class AnswerIn(BaseModel):
    question_id: str
    response: dict = {}
    client_seq: int = Field(default=0, ge=0)
    time_spent_sec: int | None = Field(default=None, ge=0)


class FinalizeIn(BaseModel):
    # optional trailing answers submitted with the final action
    answers: list[AnswerIn] = []

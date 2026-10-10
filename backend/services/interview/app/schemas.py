from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewerIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    email: str = Field(min_length=3, max_length=255)


class ScheduleIn(BaseModel):
    drive_id: str
    candidate_id: str
    round_id: str | None = None
    stage: str = Field(default="technical", pattern="^(technical|hr|ppo)$")
    mode: str = Field(default="online", pattern="^(online|in_person)$")
    link: str | None = None
    slot: str | None = None
    # Panel the interview is assigned to — every interviewer is emailed the invite.
    interviewers: list[InterviewerIn] = []
    # Back-compat single interviewer (merged into the panel if given).
    interviewer_name: str | None = Field(default=None, max_length=128)
    interviewer_email: str | None = Field(default=None, max_length=255)


class AllocateIn(BaseModel):
    interviewer_id: str


class RateIn(BaseModel):
    competency: str = Field(pattern="^(technical|communication|problem_solving|culture)$")
    score: float = Field(ge=1, le=5)
    remark: str | None = None


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(select|reject|hold|next_round)$")
    reason: str | None = None

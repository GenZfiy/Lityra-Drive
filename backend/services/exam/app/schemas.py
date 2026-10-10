from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SectionIn(BaseModel):
    title: str
    order: int = 1
    time_limit_min: int = 0
    questions: list[dict] = []  # exam-facing (no keys): {id,type,stem,options,weight}

    @field_validator("questions")
    @classmethod
    def _no_blank_questions(cls, qs: list[dict]) -> list[dict]:
        """A question with no stem — or an MCQ with under two options — renders as
        an empty card the candidate cannot answer. Reject the paper outright so a
        broken exam can never reach a live drive."""
        for i, q in enumerate(qs, start=1):
            where = f"question {i} ({q.get('id') or 'unnamed'})"
            if not str(q.get("stem") or "").strip():
                raise ValueError(f"{where} has no question text")
            if q.get("type") != "coding" and len(
                [o for o in (q.get("options") or []) if str(
                    (o.get("text") if isinstance(o, dict) else o) or "").strip()]
            ) < 2:
                raise ValueError(f"{where} needs at least 2 answer options")
        return qs


class ExamIn(BaseModel):
    drive_id: str | None = None
    round_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    total_time_min: int = Field(default=60, ge=1)
    negative_marking: float = Field(default=0.0, ge=0)
    nav_rule: str = Field(default="free", pattern="^(free|linear)$")
    sections: list[SectionIn]


class StartIn(BaseModel):
    # Optional: only staff may start a session on behalf of a candidate.
    candidate_id: str | None = None


class SaveIn(BaseModel):
    # {question_id: response}
    answers: dict


class LockIn(BaseModel):
    section_id: str

"""Interview logic: schedule, allocate, rate, decide."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, Forbidden, NotFound
from lare_common.security import new_id

from .models import Interview, Rating


class InterviewService:
    def schedule(self, s: Session, data) -> Interview:
        iv = Interview(id=new_id(), drive_id=data.drive_id, candidate_id=data.candidate_id,
                       round_id=data.round_id, stage=data.stage, mode=data.mode,
                       link=data.link, slot=data.slot)
        s.add(iv)
        s.flush()
        return iv

    def get(self, s: Session, iid: str) -> Interview:
        iv = s.get(Interview, iid)
        if not iv:
            raise NotFound("Interview not found", code="interview_not_found")
        return iv

    def allocate(self, s: Session, iid: str, interviewer_id: str) -> Interview:
        iv = self.get(s, iid)
        iv.interviewer_id = interviewer_id
        s.flush()
        return iv

    def rate(self, s: Session, iid: str, interviewer_id: str, data) -> dict:
        iv = self.get(s, iid)
        if iv.interviewer_id and iv.interviewer_id != interviewer_id:
            raise Forbidden("Only the allocated interviewer may rate")
        s.add(Rating(id=new_id(), interview_id=iid, interviewer_id=interviewer_id,
                     competency=data.competency, score=data.score, remark=data.remark))
        s.flush()  # autoflush is off — flush so the AVG below sees the new row
        # recompute average across competencies
        avg = s.execute(
            select(func.avg(Rating.score)).where(Rating.interview_id == iid)
        ).scalar_one()
        iv.avg_rating = round(float(avg), 2) if avg is not None else None
        s.flush()
        return {"interview_id": iid, "competency": data.competency, "score": data.score,
                "avg_rating": iv.avg_rating}

    def decide(self, s: Session, iid: str, interviewer_id: str, data) -> Interview:
        iv = self.get(s, iid)
        if iv.interviewer_id and iv.interviewer_id != interviewer_id:
            raise Forbidden("Only the allocated interviewer may decide")
        if iv.decision:
            raise Conflict("Decision already recorded", code="already_decided")
        iv.decision = data.decision
        iv.decision_reason = data.reason
        iv.status = "completed"
        s.flush()
        return iv

    def dossier(self, s: Session, iid: str) -> dict:
        iv = self.get(s, iid)
        ratings = s.execute(select(Rating).where(Rating.interview_id == iid)).scalars().all()
        return {
            **self.out(iv),
            "ratings": [{"competency": r.competency, "score": r.score,
                         "remark": r.remark, "interviewer_id": r.interviewer_id}
                        for r in ratings],
        }

    def for_drive(self, s: Session, drive_id: str) -> list[dict]:
        rows = s.execute(
            select(Interview).where(Interview.drive_id == drive_id)
        ).scalars().all()
        return [self.out(iv) for iv in rows]

    @staticmethod
    def out(iv: Interview) -> dict:
        return {"id": iv.id, "drive_id": iv.drive_id, "candidate_id": iv.candidate_id,
                "stage": iv.stage, "mode": iv.mode, "link": iv.link, "slot": iv.slot,
                "interviewer_id": iv.interviewer_id, "status": iv.status,
                "decision": iv.decision, "avg_rating": iv.avg_rating}

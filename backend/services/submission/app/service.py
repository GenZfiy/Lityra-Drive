"""Submission logic: durable append-only writes + latest view + final snapshot.

Every accepted write is persisted (append-only) before ack. Latest state uses
last-write-wins by client_seq (ties broken by timestamp). Final snapshot is
write-once."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict
from lare_common.security import new_id

from .models import AnswerEvent, AnswerLatest, FinalSubmission, TimeSpent


class SubmissionService:
    def is_finalized(self, s: Session, session_id: str) -> bool:
        return s.execute(
            select(FinalSubmission).where(FinalSubmission.session_id == session_id)
        ).scalar_one_or_none() is not None

    def write_answer(self, s: Session, session_id: str, data, source: str = "autosave") -> dict:
        if self.is_finalized(s, session_id):
            raise Conflict("Session already finalized", code="already_finalized")

        # Append-only event (durable history).
        s.add(AnswerEvent(id=new_id(), session_id=session_id, question_id=data.question_id,
                          response=data.response, source=source, client_seq=data.client_seq))

        # Update materialized latest with last-write-wins by client_seq.
        latest = s.execute(
            select(AnswerLatest).where(
                AnswerLatest.session_id == session_id,
                AnswerLatest.question_id == data.question_id)
        ).scalar_one_or_none()
        if latest is None:
            latest = AnswerLatest(id=new_id(), session_id=session_id,
                                  question_id=data.question_id, response=data.response,
                                  client_seq=data.client_seq)
            s.add(latest)
        elif data.client_seq >= latest.client_seq:
            latest.response = data.response
            latest.client_seq = data.client_seq
        # else: stale/late write — kept in history, ignored for latest

        if data.time_spent_sec is not None:
            ts = s.execute(
                select(TimeSpent).where(
                    TimeSpent.session_id == session_id,
                    TimeSpent.question_id == data.question_id)
            ).scalar_one_or_none()
            if ts is None:
                s.add(TimeSpent(id=new_id(), session_id=session_id,
                                question_id=data.question_id, seconds=data.time_spent_sec))
            else:
                ts.seconds = data.time_spent_sec
        s.flush()
        return {"question_id": data.question_id, "accepted": True,
                "client_seq": data.client_seq}

    def finalize(self, s: Session, session_id: str, answers) -> dict:
        existing = s.execute(
            select(FinalSubmission).where(FinalSubmission.session_id == session_id)
        ).scalar_one_or_none()
        if existing:
            # idempotent finalize returns the existing immutable snapshot
            return {"session_id": session_id, "answer_count": existing.answer_count,
                    "finalized": True, "already": True}

        for a in answers:
            self.write_answer(s, session_id, a, source="final")

        latest = s.execute(
            select(AnswerLatest).where(AnswerLatest.session_id == session_id)
        ).scalars().all()
        snapshot = {r.question_id: r.response for r in latest}
        fs = FinalSubmission(id=new_id(), session_id=session_id, snapshot=snapshot,
                             answer_count=len(snapshot))
        s.add(fs)
        s.flush()
        return {"session_id": session_id, "answer_count": len(snapshot), "finalized": True}

    def latest(self, s: Session, session_id: str) -> dict:
        rows = s.execute(
            select(AnswerLatest).where(AnswerLatest.session_id == session_id)
        ).scalars().all()
        return {r.question_id: r.response for r in rows}

    def export(self, s: Session, session_id: str) -> dict:
        """Authoritative answer set for Evaluation/Audit."""
        final = s.execute(
            select(FinalSubmission).where(FinalSubmission.session_id == session_id)
        ).scalar_one_or_none()
        history_count = s.execute(
            select(func.count(AnswerEvent.id)).where(AnswerEvent.session_id == session_id)
        ).scalar_one()
        time_spent = {
            t.question_id: t.seconds for t in s.execute(
                select(TimeSpent).where(TimeSpent.session_id == session_id)
            ).scalars().all()
        }
        return {
            "session_id": session_id,
            "finalized": final is not None,
            "answers": final.snapshot if final else self.latest(s, session_id),
            "answer_count": final.answer_count if final else len(self.latest(s, session_id)),
            "history_events": history_count,
            "time_spent": time_spent,
        }

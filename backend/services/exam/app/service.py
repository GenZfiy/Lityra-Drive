"""Exam engine logic: sessions, server-authoritative timer, section locking,
auto-save, resume, auto-submit."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, Forbidden, NotFound
from lare_common.security import new_id

from .models import Exam, ExamAnswer, ExamSession


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class ExamEngine:
    # ---------- authoring ----------
    def create_exam(self, s: Session, data) -> Exam:
        sections = []
        for i, sec in enumerate(data.sections):
            sections.append({
                "id": new_id(), "title": sec.title, "order": sec.order or (i + 1),
                "time_limit_min": sec.time_limit_min, "questions": sec.questions,
            })
        exam = Exam(id=new_id(), drive_id=data.drive_id, round_id=data.round_id,
                    title=data.title, total_time_min=data.total_time_min,
                    negative_marking=data.negative_marking, nav_rule=data.nav_rule,
                    sections=sections)
        s.add(exam)
        s.flush()
        return exam

    def get_exam(self, s: Session, eid: str) -> Exam:
        e = s.get(Exam, eid)
        if not e:
            raise NotFound("Exam not found", code="exam_not_found")
        return e

    def delete_exam(self, s: Session, eid: str) -> None:
        s.delete(self.get_exam(s, eid))
        s.flush()

    def list_exams(self, s: Session, drive_id: str | None = None) -> list[dict]:
        q = select(Exam)
        if drive_id:
            q = q.where(Exam.drive_id == drive_id)
        rows = s.execute(q).scalars().all()
        return [{"id": e.id, "title": e.title, "drive_id": e.drive_id,
                 "round_id": e.round_id, "total_time_min": e.total_time_min,
                 "sections": len(e.sections)} for e in rows]

    # ---------- timer ----------
    def _remaining(self, exam: Exam, sess: ExamSession) -> int:
        elapsed = (_utcnow() - _aware(sess.started_at)).total_seconds()
        return max(0, int(exam.total_time_min * 60 - elapsed))

    def _auto_submit_if_expired(self, s: Session, exam: Exam, sess: ExamSession) -> bool:
        if sess.status == "in_progress" and self._remaining(exam, sess) <= 0:
            sess.status = "expired"
            sess.auto_submitted = True
            sess.submitted_at = _utcnow()
            s.flush()
            return True
        return False

    # ---------- session lifecycle ----------
    def start(self, s: Session, eid: str, candidate_id: str) -> dict:
        exam = self.get_exam(s, eid)
        now = _utcnow()
        if exam.window_start and now < _aware(exam.window_start):
            raise Conflict("Exam window not open yet", code="window_not_open")
        if exam.window_end and now > _aware(exam.window_end):
            raise Conflict("Exam window has closed", code="window_closed")

        sess = s.execute(
            select(ExamSession).where(
                ExamSession.exam_id == eid, ExamSession.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if sess is None:
            sess = ExamSession(id=new_id(), exam_id=eid, candidate_id=candidate_id,
                               section_state={sec["id"]: {"locked": False} for sec in exam.sections})
            s.add(sess)
            s.flush()
        else:
            # resume: enforce single active session (idempotent start)
            self._auto_submit_if_expired(s, exam, sess)
            # One attempt only: once submitted/expired/auto-submitted, the exam can
            # never be reopened by the same candidate.
            if sess.status != "in_progress":
                raise Conflict(
                    "You have already taken this exam. It cannot be reopened.",
                    code="already_submitted")
        return self.state(s, eid, sess)

    def _session(self, s: Session, session_id: str, candidate_id: str) -> ExamSession:
        sess = s.get(ExamSession, session_id)
        if not sess:
            raise NotFound("Session not found", code="session_not_found")
        if sess.candidate_id != candidate_id:
            raise Forbidden("Not your session")
        return sess

    def save(self, s: Session, session_id: str, candidate_id: str, answers: dict) -> dict:
        sess = self._session(s, session_id, candidate_id)
        exam = self.get_exam(s, sess.exam_id)
        if self._auto_submit_if_expired(s, exam, sess) or sess.status != "in_progress":
            raise Conflict("Exam is not active (submitted or expired)", code="not_active")

        # Reject saves to locked sections.
        locked_qids = self._locked_question_ids(exam, sess)
        saved = 0
        for qid, resp in answers.items():
            if qid in locked_qids:
                continue
            row = s.execute(
                select(ExamAnswer).where(
                    ExamAnswer.session_id == session_id, ExamAnswer.question_id == qid)
            ).scalar_one_or_none()
            if row is None:
                row = ExamAnswer(id=new_id(), session_id=session_id, question_id=qid, response=resp)
                s.add(row)
            else:
                row.response = resp
            saved += 1
        s.flush()
        # In production: mirror each write to the Submission Service (durable).
        return {"saved": saved, "remaining_sec": self._remaining(exam, sess)}

    def lock_section(self, s: Session, session_id: str, candidate_id: str, section_id: str) -> dict:
        sess = self._session(s, session_id, candidate_id)
        exam = self.get_exam(s, sess.exam_id)
        if self._auto_submit_if_expired(s, exam, sess):
            raise Conflict("Exam expired", code="not_active")
        if section_id not in sess.section_state:
            raise NotFound("Section not found", code="section_not_found")
        state = dict(sess.section_state)
        state[section_id] = {"locked": True}
        sess.section_state = state
        s.flush()
        return {"section_id": section_id, "locked": True}

    def force_submit(self, s: Session, session_id: str, reason: str = "anticheat") -> dict:
        """Server-side forced submission (triggered by Anti-Cheating on threshold
        breach). Idempotent; marks the session auto-submitted."""
        sess = s.get(ExamSession, session_id)
        if not sess:
            raise NotFound("Session not found", code="session_not_found")
        if sess.status == "in_progress":
            sess.status = "submitted"
            sess.auto_submitted = True
            sess.submitted_at = _utcnow()
            s.flush()
        return {"session_id": session_id, "status": sess.status,
                "auto_submitted": sess.auto_submitted, "reason": reason}

    def submit(self, s: Session, session_id: str, candidate_id: str) -> dict:
        sess = self._session(s, session_id, candidate_id)
        exam = self.get_exam(s, sess.exam_id)
        if sess.status != "in_progress":
            # idempotent finalize
            return self.state(s, sess.exam_id, sess)
        sess.status = "submitted"
        sess.submitted_at = _utcnow()
        s.flush()
        return self.state(s, sess.exam_id, sess)

    # ---------- read ----------
    def _locked_question_ids(self, exam: Exam, sess: ExamSession) -> set[str]:
        locked = set()
        for sec in exam.sections:
            if sess.section_state.get(sec["id"], {}).get("locked"):
                locked.update(q["id"] for q in sec.get("questions", []))
        return locked

    def state(self, s: Session, eid: str, sess: ExamSession) -> dict:
        exam = self.get_exam(s, eid)
        self._auto_submit_if_expired(s, exam, sess)
        answers = {
            a.question_id: a.response for a in s.execute(
                select(ExamAnswer).where(ExamAnswer.session_id == sess.id)
            ).scalars().all()
        }
        return {
            "session_id": sess.id, "exam_id": eid, "title": exam.title,
            "status": sess.status, "remaining_sec": self._remaining(exam, sess),
            "auto_submitted": sess.auto_submitted, "nav_rule": exam.nav_rule,
            "sections": [
                {"id": sec["id"], "title": sec["title"], "order": sec["order"],
                 "locked": sess.section_state.get(sec["id"], {}).get("locked", False),
                 "questions": sec.get("questions", [])}
                for sec in sorted(exam.sections, key=lambda x: x["order"])
            ],
            "answers": answers,
        }

    @staticmethod
    def exam_out(e: Exam) -> dict:
        return {"id": e.id, "title": e.title, "total_time_min": e.total_time_min,
                "nav_rule": e.nav_rule, "sections": len(e.sections)}

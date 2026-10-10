"""HTTP layer for the Exam Engine Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest, Forbidden
from lare_common.responses import created, ok


def _check_bound_drive(exam):
    """A gated candidate is bound to one drive (Gateway injects X-Drive-Id) — an
    exam from any other drive is off-limits, even via a direct URL."""
    bound = request.headers.get("X-Drive-Id")
    if bound and getattr(exam, "drive_id", None) and exam.drive_id != bound:
        raise Forbidden("This assessment is not part of your drive.", code="wrong_drive")

from .schemas import ExamIn, LockIn, SaveIn, StartIn
from .service import ExamEngine

bp = Blueprint("exam", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter")


def _svc() -> ExamEngine:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


def _submission_snapshot(s, sid: str) -> dict | None:
    """Assemble the exam.submitted payload from committed session state."""
    from .models import Exam, ExamAnswer, ExamSession
    sess = s.get(ExamSession, sid)
    if not sess:
        return None
    exam = s.get(Exam, sess.exam_id)
    from sqlalchemy import select
    answers = {
        a.question_id: a.response
        for a in s.execute(select(ExamAnswer).where(ExamAnswer.session_id == sid)).scalars().all()
    }
    return {
        "session_id": sid, "exam_id": sess.exam_id, "candidate_id": sess.candidate_id,
        "drive_id": exam.drive_id if exam else None,
        "round_id": exam.round_id if exam else None,
        "answers": answers, "auto_submitted": sess.auto_submitted,
    }


def _publish_submitted(snapshot: dict | None, reason: str | None = None) -> None:
    if not snapshot:
        return
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("exam.submitted", {**snapshot, "reason": reason})


@bp.post("/drive/v1/exams")
@require_roles(*MANAGE)
def create_exam():
    data = _parse(ExamIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().exam_out(_svc().create_exam(s, data)))


@bp.get("/drive/v1/exams")
def list_exams():
    # Students list exams for a drive they're in; staff may list all.
    ident = current_identity()
    drive_id = request.args.get("drive_id")
    if not drive_id and not ident.has_role(*MANAGE):
        raise BadRequest("drive_id is required", code="drive_id_required")
    with _db().session() as s:
        return ok(_svc().list_exams(s, drive_id))


@bp.get("/drive/v1/exams/<eid>")
def get_exam(eid):
    current_identity()
    with _db().session() as s:
        exam = _svc().get_exam(s, eid)
        _check_bound_drive(exam)
        return ok(_svc().exam_out(exam))


@bp.delete("/drive/v1/exams/<eid>")
@require_roles(*MANAGE)
def delete_exam(eid):
    with _db().session() as s:
        _svc().delete_exam(s, eid)
        return ok({"deleted": True})


@bp.get("/drive/v1/exams/<eid>/paper")
@require_roles(*MANAGE)
def exam_paper(eid):
    # Admin question-paper view: full questions with the correct answers merged
    # in (fetched from the Evaluation service's answer key).
    from lare_common.service_client import ServiceClient
    with _db().session() as s:
        exam = _svc().get_exam(s, eid)
        exam_id, exam_title = exam.id, exam.title
        exam_time = exam.total_time_min
        sections = exam.sections
    key_items = {}
    try:
        resp = ServiceClient("drive-exam", default_roles=["company_admin"]).get(
            "drive-evaluation", f"/drive/v1/evaluations/keys/{eid}")
        for it in ((resp or {}).get("data") or {}).get("items", []):
            key_items[it["question_id"]] = it
    except Exception:  # noqa: BLE001 — show the paper even if the key is missing
        pass
    out_sections = []
    for sec in sorted(sections, key=lambda x: x.get("order", 0)):
        qs = []
        for q in sec.get("questions", []):
            k = key_items.get(q.get("id"), {})
            qs.append({**q,
                       "correct": k.get("correct"),        # {"option": "b"} for MCQ
                       "cases": k.get("cases"),            # coding test cases
                       "weight": k.get("weight", q.get("weight"))})
        out_sections.append({"id": sec.get("id"), "title": sec.get("title"),
                             "order": sec.get("order"), "questions": qs})
    return ok({"id": exam_id, "title": exam_title,
               "total_time_min": exam_time, "sections": out_sections})


@bp.post("/drive/v1/exams/<eid>/start")
def start(eid):
    ident = current_identity()
    data = _parse(StartIn, request.get_json(silent=True))
    # A candidate always starts their OWN session; only staff may start on behalf.
    if data.candidate_id and ident.has_role(*MANAGE):
        candidate_id = data.candidate_id
    else:
        candidate_id = ident.user_id
    with _db().session() as s:
        _check_bound_drive(_svc().get_exam(s, eid))
        return created(_svc().start(s, eid, candidate_id))


@bp.get("/drive/v1/exam-sessions/<sid>/state")
def state(sid):
    ident = current_identity()
    with _db().session() as s:
        from .models import ExamSession
        sess = s.get(ExamSession, sid)
        if not sess:
            raise BadRequest("Session not found", code="session_not_found")
        # ownership check inside _session via save/lock; for state allow owner or staff
        if sess.candidate_id != ident.user_id and not ident.has_role(*MANAGE):
            from lare_common.errors import Forbidden
            raise Forbidden("Not your session")
        return ok(_svc().state(s, sess.exam_id, sess))


@bp.post("/drive/v1/exam-sessions/<sid>/save")
def save(sid):
    ident = current_identity()
    data = _parse(SaveIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().save(s, sid, ident.user_id, data.answers))


@bp.post("/drive/v1/exam-sessions/<sid>/lock-section")
def lock_section(sid):
    ident = current_identity()
    data = _parse(LockIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().lock_section(s, sid, ident.user_id, data.section_id))


@bp.post("/drive/v1/exam-sessions/<sid>/submit")
def submit(sid):
    ident = current_identity()
    from .models import ExamSession
    with _db().session() as s:
        was_active = (getattr(s.get(ExamSession, sid), "status", None) == "in_progress")
        result = _svc().submit(s, sid, ident.user_id)
        snap = _submission_snapshot(s, sid) if was_active else None
    _publish_submitted(snap, reason="candidate")  # after commit; no-op if not transitioned
    return ok(result)


# Internal: forced submission from the Anti-Cheating service on threshold breach.
@bp.post("/drive/v1/exam-sessions/<sid>/force-submit")
@require_roles("super_admin", "company_admin", "recruiter")
def force_submit(sid):
    body = request.get_json(silent=True) or {}
    from .models import ExamSession
    with _db().session() as s:
        was_active = (getattr(s.get(ExamSession, sid), "status", None) == "in_progress")
        result = _svc().force_submit(s, sid, body.get("reason", "anticheat"))
        snap = _submission_snapshot(s, sid) if was_active else None
    _publish_submitted(snap, reason=body.get("reason", "anticheat"))
    return ok(result)

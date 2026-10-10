"""HTTP layer for the Coding Assessment Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest, Forbidden
from lare_common.responses import created, ok

from .schemas import OpenPracticeIn, OpenSessionIn, ProblemIn, RunIn, SaveIn
from .service import CodingService

bp = Blueprint("coding", __name__)

AUTHOR = ("super_admin", "company_admin", "trainer", "recruiter")
# LMS practice is authored by trainers/admins; solved by students.
PRACTICE_STAFF = ("super_admin", "company_admin", "college_admin", "trainer")
PRACTICE_READ = ("super_admin", "company_admin", "college_admin", "trainer", "student")


def _svc() -> CodingService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/coding/problems")
@require_roles(*AUTHOR)
def create_problem():
    data = _parse(ProblemIn, request.get_json(silent=True))
    with _db().session() as s:
        p = _svc().create_problem(s, data)
        return created({"id": p.id, "title": p.title,
                        "hidden_case_count": len(p.hidden_cases)})


@bp.post("/drive/v1/coding/session")
def open_session():
    ident = current_identity()
    data = _parse(OpenSessionIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().open_session(s, ident.user_id, data))


@bp.post("/drive/v1/coding/<sid>/save")
def save(sid):
    ident = current_identity()
    data = _parse(SaveIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().save(s, sid, ident.user_id, data.code))


@bp.get("/drive/v1/coding/languages")
def languages():
    # Language version management: which toolchains are available on this host.
    return ok(_svc().languages())


@bp.post("/drive/v1/coding/run-adhoc")
def run_adhoc():
    # Run exam coding answers against their (visible) sample cases — any
    # authenticated candidate. Hidden-case grading happens on exam submit.
    current_identity()
    b = request.get_json(silent=True) or {}
    lang = b.get("language", "python")
    code = b.get("code", "")
    cases = b.get("cases") or []
    if not code.strip():
        raise BadRequest("No code to run", code="empty_code")
    return ok(_svc().run_adhoc(lang, code, cases))


@bp.post("/drive/v1/coding/<sid>/run")
def run(sid):
    ident = current_identity()
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().run_samples(s, sid, ident.user_id, data.code))


@bp.post("/drive/v1/coding/<sid>/submit")
def submit(sid):
    ident = current_identity()
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().submit(s, sid, ident.user_id, data.code))


@bp.get("/drive/v1/coding/<sid>/result")
def result(sid):
    current_identity()
    with _db().session() as s:
        return ok(_svc().result(s, sid))


# ---------------------------------------------------------------------------
# Lityra Learn — coding practice (feeds the Cognitive Twin / skill map).
# Same sandbox engine as Drive coding rounds, but a separate, student-facing
# surface that records per-learner skill progress. Product-separated by URL.
# ---------------------------------------------------------------------------
@bp.get("/lms/v1/practice/problems")
@require_roles(*PRACTICE_READ)
def practice_problems():
    skill = request.args.get("skill")
    difficulty = request.args.get("difficulty")
    with _db().session() as s:
        return ok(_svc().list_practice(s, skill, difficulty))


@bp.post("/lms/v1/practice/session")
@require_roles(*PRACTICE_READ)
def practice_open():
    ident = current_identity()
    data = _parse(OpenPracticeIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().open_practice(s, ident.user_id, data))


@bp.post("/lms/v1/practice/<sid>/run")
@require_roles(*PRACTICE_READ)
def practice_run(sid):
    ident = current_identity()
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().run_samples(s, sid, ident.user_id, data.code))


@bp.post("/lms/v1/practice/<sid>/submit")
@require_roles(*PRACTICE_READ)
def practice_submit(sid):
    ident = current_identity()
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().submit(s, sid, ident.user_id, data.code))


@bp.get("/lms/v1/practice/skills/<learner_id>")
@require_roles(*PRACTICE_READ)
def practice_skills(learner_id):
    """A learner's coding skill profile (per skill + per language). Students see
    only their own; staff may view any (used by the Twin east-west call)."""
    ident = current_identity()
    if not ident.has_role(*PRACTICE_STAFF) and learner_id != ident.user_id:
        raise Forbidden("You can only view your own coding skills.")
    with _db().session() as s:
        return ok(_svc().practice_skills(s, learner_id))


@bp.post("/lms/v1/practice/<sid>/viva")
@require_roles(*PRACTICE_READ)
def practice_viva_start(sid):
    """Adversarial viva: after submitting, get one question that checks you can
    explain your own solution (cheat-resistant proof of competence)."""
    ident = current_identity()
    with _db().session() as s:
        return created(_svc().start_viva(s, sid, ident.user_id))


@bp.post("/lms/v1/practice/viva/<viva_id>")
@require_roles(*PRACTICE_READ)
def practice_viva_grade(viva_id):
    """Submit your explanation; the AI grades whether you truly understand it."""
    ident = current_identity()
    answer = (request.get_json(silent=True) or {}).get("answer", "")
    with _db().session() as s:
        return ok(_svc().grade_viva(s, viva_id, ident.user_id, answer))

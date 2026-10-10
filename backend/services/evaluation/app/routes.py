"""HTTP layer for the Evaluation Service (internal/staff-facing)."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest, Forbidden
from lare_common.responses import created, ok

from .schemas import KeyIn, RankIn, RunIn
from .service import EvaluationService

bp = Blueprint("evaluation", __name__)

STAFF = ("super_admin", "company_admin", "recruiter")


def _svc() -> EvaluationService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/evaluations/keys")
@require_roles(*STAFF)
def upsert_key():
    data = _parse(KeyIn, request.get_json(silent=True))
    with _db().session() as s:
        k = _svc().upsert_key(s, data)
        return created({"exam_id": k.exam_id, "items": len(k.items),
                        "passing_pct": k.passing_pct})


@bp.get("/drive/v1/evaluations/keys/<exam_id>")
@require_roles(*STAFF)
def get_key(exam_id):
    # Staff-only: the correct answers for an exam, to show in the admin paper view.
    with _db().session() as s:
        return ok(_svc().get_key(s, exam_id))


@bp.post("/drive/v1/evaluations/run")
@require_roles(*STAFF)
def run():
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().run(s, data))


@bp.post("/drive/v1/evaluations/<session_id>/reevaluate")
@require_roles(*STAFF)
def reevaluate(session_id):
    # Re-run using the current key + provided answers (after a key correction).
    data = _parse(RunIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().run(s, data))


@bp.get("/drive/v1/evaluations/<session_id>")
@require_roles(*STAFF)
def get_eval(session_id):
    with _db().session() as s:
        return ok(_svc().get(s, session_id))


@bp.get("/drive/v1/evaluations/twin/<candidate_id>")
@require_roles("super_admin", "company_admin", "recruiter", "student")
def twin(candidate_id):
    """Cognitive Twin skill profile. A student may only view their own; staff
    (recruiters/admins) may view any candidate's."""
    ident = current_identity()
    is_staff = ident.has_role(*STAFF)
    if not is_staff and candidate_id != ident.user_id:
        raise Forbidden("You can only view your own skill map.")
    with _db().session() as s:
        return ok(_svc().skill_profile(s, candidate_id))


@bp.post("/drive/v1/evaluations/rank")
@require_roles(*STAFF)
def rank():
    data = _parse(RankIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().compute_ranks(s, data.exam_id))


@bp.get("/drive/v1/evaluations/exam/<exam_id>/ranks")
@require_roles(*STAFF)
def get_ranks(exam_id):
    with _db().session() as s:
        return ok(_svc().compute_ranks(s, exam_id))


@bp.get("/drive/v1/evaluations/exam/<exam_id>/difficulty")
@require_roles(*STAFF)
def difficulty(exam_id):
    with _db().session() as s:
        return ok(_svc().difficulty(s, exam_id))

"""HTTP layer for the Submission Service.

Written by the Exam Engine / Coding services (internal); read by Evaluation and
Audit. Not candidate-facing directly."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import require_roles
from lare_common.errors import BadRequest
from lare_common.responses import ok

from .schemas import AnswerIn, FinalizeIn
from .service import SubmissionService

bp = Blueprint("submission", __name__)

# Internal writers/readers run as company/recruiter/service context.
WRITE = ("super_admin", "company_admin", "recruiter", "trainer")
READ = ("super_admin", "company_admin", "recruiter", "trainer")


def _svc() -> SubmissionService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/submissions/<sid>/answer")
@require_roles(*WRITE)
def answer(sid):
    data = _parse(AnswerIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().write_answer(s, sid, data))


@bp.post("/drive/v1/submissions/<sid>/final")
@require_roles(*WRITE)
def final(sid):
    data = _parse(FinalizeIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().finalize(s, sid, data.answers))


@bp.get("/drive/v1/submissions/<sid>/latest")
@require_roles(*READ)
def latest(sid):
    with _db().session() as s:
        return ok(_svc().latest(s, sid))


@bp.get("/drive/v1/submissions/<sid>/export")
@require_roles(*READ)
def export(sid):
    with _db().session() as s:
        return ok(_svc().export(s, sid))

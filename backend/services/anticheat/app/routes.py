"""HTTP layer for the Anti-Cheating Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import EventIn, StartProctorIn
from .service import AntiCheatService

bp = Blueprint("anticheat", __name__)

ADMIN = ("super_admin", "company_admin", "recruiter")


def _svc() -> AntiCheatService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/proctor/start")
def start():
    # candidate's client (or exam engine) starts a proctoring session
    current_identity()
    data = _parse(StartProctorIn, request.get_json(silent=True))
    with _db().session() as s:
        ps = _svc().start(s, data)
        return created({"exam_session_id": ps.exam_session_id, "status": ps.status})


@bp.post("/drive/v1/proctor/<exam_session_id>/events")
def ingest(exam_session_id):
    current_identity()
    data = _parse(EventIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().ingest(s, exam_session_id, data))


@bp.get("/drive/v1/proctor/<exam_session_id>/summary")
@require_roles(*ADMIN)
def summary(exam_session_id):
    with _db().session() as s:
        return ok(_svc().summary(s, exam_session_id))


@bp.get("/drive/v1/proctor/drive/<drive_id>/report")
@require_roles(*ADMIN)
def drive_report(drive_id):
    with _db().session() as s:
        return ok(_svc().drive_report(s, drive_id))

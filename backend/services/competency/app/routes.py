"""HTTP layer for the Competency service (catalogue + evaluation models)."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import CompetencyIn, ModelIn
from .service import CompetencyService

bp = Blueprint("competency", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter")
READ = ("super_admin", "company_admin", "recruiter", "college_admin", "trainer", "student")


def _svc() -> CompetencyService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


@bp.get("/drive/v1/competency/catalogue")
@require_roles(*READ)
def catalogue():
    with _db().session() as s:
        return ok(_svc().catalogue(s))


@bp.post("/drive/v1/competency/catalogue")
@require_roles(*MANAGE)
def add_competency():
    try:
        body = CompetencyIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        raise BadRequest("Invalid competency") from e
    with _db().session() as s:
        return created(_svc().add_competency(s, key=body.key, name=body.name, description=body.description))


@bp.post("/drive/v1/competency/models")
@require_roles(*MANAGE)
def set_model():
    try:
        body = ModelIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        raise BadRequest("Invalid evaluation model") from e
    with _db().session() as s:
        return created(_svc().set_model(s, drive_id=body.drive_id, weights=[w.model_dump() for w in body.weights]))


@bp.get("/drive/v1/competency/models/<did>")
@require_roles(*READ)
def get_model(did):
    with _db().session() as s:
        return ok(_svc().active_model(s, did))

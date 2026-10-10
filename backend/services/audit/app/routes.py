"""HTTP layer for the Audit Service. Ingest is internal; query/verify are admin."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import require_permission, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import ActivityIn, AuditIn
from .service import AuditService

bp = Blueprint("audit", __name__)

# Any authenticated internal service/staff may write audit events.
WRITE = ("super_admin", "company_admin", "recruiter", "trainer", "college_admin")
ADMIN = ("super_admin", "company_admin")


def _svc() -> AuditService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/audit/v1/events")
@require_roles(*WRITE)
def append_event():
    data = _parse(AuditIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().append(s, data))


@bp.post("/audit/v1/activity")
@require_roles(*WRITE)
def activity():
    data = _parse(ActivityIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().activity(s, data))


@bp.get("/audit/v1/logs")
@require_permission("platform.audit.view")
def logs():
    with _db().session() as s:
        return ok(_svc().query(
            s,
            partition_key=request.args.get("partition_key"),
            actor_id=request.args.get("actor_id"),
            action=request.args.get("action"),
            entity_type=request.args.get("entity_type"),
            entity_id=request.args.get("entity_id"),
            correlation_id=request.args.get("correlation_id"),
            limit=min(int(request.args.get("limit", 100)), 1000),
        ))


@bp.get("/audit/v1/logs/verify")
@require_permission("platform.audit.view")
def verify():
    partition = request.args.get("partition_key", "global")
    with _db().session() as s:
        return ok(_svc().verify(s, partition))


@bp.get("/audit/v1/drive/<drive_id>/integrity")
@require_roles("super_admin", "company_admin", "recruiter")
def drive_integrity(drive_id):
    with _db().session() as s:
        return ok(_svc().drive_integrity(s, drive_id))

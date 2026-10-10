"""HTTP layer for the Analytics Service."""
from __future__ import annotations

from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, current_scope, require_roles
from lare_common.errors import BadRequest, Forbidden
from lare_common.responses import ok
from lare_common.responses import created

from .schemas import IngestIn
from .service import AnalyticsService

bp = Blueprint("analytics", __name__)

WRITE = ("super_admin", "company_admin", "trainer", "recruiter")
READ = ("super_admin", "company_admin", "college_admin", "recruiter", "trainer")
ADMIN = ("super_admin", "company_admin")


def _svc() -> AnalyticsService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/analytics/v1/events")
@require_roles(*WRITE)
def ingest():
    data = _parse(IngestIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().ingest(s, data.facts))


@bp.get("/analytics/v1/college/<college_id>/readiness")
@require_roles(*READ)
def readiness(college_id):
    # Data-scope isolation: only a platform-wide caller, or one whose scope
    # includes this college, may read its readiness.
    if not current_scope().allows_college(college_id):
        raise Forbidden("Outside your college scope")
    with _db().session() as s:
        return ok(_svc().readiness(s, college_id))


@bp.get("/analytics/v1/colleges/ranking")
@require_roles(*ADMIN)  # cross-college "best college" ranking is admin-only
def ranking():
    with _db().session() as s:
        return ok(_svc().ranking(s))


@bp.get("/analytics/v1/scorecard/<learner_id>")
@require_roles(*READ)
def scorecard(learner_id):
    with _db().session() as s:
        return ok(_svc().scorecard(s, learner_id))


@bp.get("/analytics/v1/drive/<drive_id>")
@require_roles("super_admin", "company_admin", "recruiter")
def drive_analytics(drive_id):
    with _db().session() as s:
        return ok(_svc().drive_analytics(s, drive_id))


@bp.get("/analytics/v1/dashboard/<role>")
@require_roles(*READ)
def dashboard(role):
    with _db().session() as s:
        return ok(_svc().dashboard(s, role))


@bp.post("/analytics/v1/reports/export")
@require_roles(*ADMIN)
def export():
    body = request.get_json(silent=True) or {}
    kind = body.get("kind", "ranking")   # ranking | drive | funnel
    ref = body.get("ref")                # drive_id for drive/funnel
    fmt = body.get("format", "csv")      # csv | excel | pdf
    with _db().session() as s:
        blob, mime, filename = _svc().export_report(s, kind, ref, fmt)
    if isinstance(blob, str):
        blob = blob.encode("utf-8")
    return Response(blob, mimetype=mime,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@bp.get("/analytics/v1/dashboard/widgets")
def get_widgets():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().get_widgets(s, ident.user_id))


@bp.put("/analytics/v1/dashboard/widgets")
def set_widgets():
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_widgets(s, ident.user_id, body.get("widgets") or []))


@bp.get("/analytics/v1/drive/<drive_id>/funnel")
@require_roles("super_admin", "company_admin", "recruiter")
def funnel(drive_id):
    with _db().session() as s:
        return ok(_svc().hiring_funnel(s, drive_id))


@bp.get("/analytics/v1/recruiters")
@require_roles(*ADMIN)
def recruiters():
    with _db().session() as s:
        return ok(_svc().recruiter_performance(s))

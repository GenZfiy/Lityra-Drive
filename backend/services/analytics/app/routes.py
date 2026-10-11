"""HTTP layer for the Analytics Service."""
from __future__ import annotations

from urllib.error import HTTPError
from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, current_scope, require_permission
from lare_common.errors import BadRequest, Forbidden, NotFound, ServiceUnavailable
from lare_common.responses import ok
from lare_common.responses import created
from lare_common.service_client import ServiceClient

from .schemas import IngestIn
from .service import AnalyticsService

bp = Blueprint("analytics", __name__)
_DRIVE = ServiceClient("hire-analytics")

WRITE = ("super_admin", "company_admin", "trainer", "recruiter")
READ = ("super_admin", "company_admin", "college_admin", "recruiter", "trainer")
ADMIN = ("super_admin", "company_admin")


def _svc() -> AnalyticsService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _assert_drive_scope(drive_id: str) -> None:
    try:
        _DRIVE.get("drive-core", f"/drive/v1/drives/{drive_id}",
                   context_token=request.headers.get("X-Internal-Token") or None)
    except HTTPError as exc:
        if exc.code == 403:
            raise Forbidden("This drive is outside your assigned scope") from exc
        if exc.code == 404:
            raise NotFound("Drive not found", code="drive_not_found") from exc
        raise ServiceUnavailable("Could not verify drive access") from exc
    except Exception as exc:  # noqa: BLE001
        raise ServiceUnavailable("Could not verify drive access") from exc


def _assert_candidate_scope(learner_id: str) -> None:
    ident = current_identity()
    if ident.user_id == learner_id:
        return
    try:
        response = _DRIVE.get("drive-core", "/drive/v1/assigned-candidates",
                              context_token=request.headers.get("X-Internal-Token") or None)
    except Exception as exc:  # noqa: BLE001
        raise ServiceUnavailable("Could not verify candidate access") from exc
    if learner_id not in ((response or {}).get("data") or []):
        raise NotFound("Learner not found", code="learner_not_found")


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/analytics/v1/events")
@require_permission("analytics.event.ingest")
def ingest():
    data = _parse(IngestIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().ingest(s, data.facts))


@bp.get("/analytics/v1/college/<college_id>/readiness")
@require_permission("analytics.college.view", "analytics.platform.view")
def readiness(college_id):
    # Data-scope isolation: only a platform-wide caller, or one whose scope
    # includes this college, may read its readiness.
    ident = current_identity()
    if ident.scope_level not in ("platform", "college") or not current_scope().allows_college(college_id):
        raise Forbidden("Outside your college scope")
    with _db().session() as s:
        return ok(_svc().readiness(s, college_id))


@bp.get("/analytics/v1/colleges/ranking")
@require_permission("analytics.platform.view")  # cross-college ranking is platform-only
def ranking():
    with _db().session() as s:
        return ok(_svc().ranking(s))


@bp.get("/analytics/v1/scorecard/<learner_id>")
@require_permission("analytics.student.view", "drive.candidate.view")
def scorecard(learner_id):
    _assert_candidate_scope(learner_id)
    ident = current_identity()
    scope = None if ident.has_permission("drive.candidate.view") else ident
    with _db().session() as s:
        return ok(_svc().scorecard(s, learner_id, scope))


@bp.get("/analytics/v1/drive/<drive_id>")
@require_permission("drive.analytics.view")
def drive_analytics(drive_id):
    _assert_drive_scope(drive_id)
    with _db().session() as s:
        return ok(_svc().drive_analytics(s, drive_id))


@bp.get("/analytics/v1/dashboard/<role>")
@require_permission("analytics.platform.view", "analytics.college.view",
                    "analytics.branch.view", "analytics.section.view",
                    "analytics.student.view", "drive.analytics.view")
def dashboard(role):
    with _db().session() as s:
        return ok(_svc().dashboard(s, role, current_identity()))


@bp.post("/analytics/v1/reports/export")
@require_permission("analytics.export", "drive.data.export")
def export():
    body = request.get_json(silent=True) or {}
    kind = body.get("kind", "ranking")   # ranking | drive | funnel
    ref = body.get("ref")                # drive_id for drive/funnel
    fmt = body.get("format", "csv")      # csv | excel | pdf
    ident = current_identity()
    if kind in ("drive", "funnel") and ref:
        if not ident.has_permission("drive.data.export", "analytics.export"):
            raise Forbidden("Export is not permitted")
        _assert_drive_scope(ref)
    elif kind == "ranking":
        if not ident.has_permission("analytics.platform.view"):
            raise Forbidden("Platform analytics are required for this report")
    else:
        raise BadRequest("Unsupported report kind or missing reference", code="invalid_report")
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
@require_permission("drive.analytics.view")
def funnel(drive_id):
    _assert_drive_scope(drive_id)
    with _db().session() as s:
        return ok(_svc().hiring_funnel(s, drive_id))


@bp.get("/analytics/v1/recruiters")
@require_permission("analytics.platform.view")
def recruiters():
    with _db().session() as s:
        return ok(_svc().recruiter_performance(s))

"""HTTP layer for the Recruitment Drive Service."""
from __future__ import annotations

import time

import jwt
from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest, Forbidden
from lare_common.responses import created, ok

from .schemas import (
    AdvanceIn, DriveAccessCodeIn, DriveAccessStatusIn, DriveAccessValidateIn, DriveIn,
    EligibilityIn, PpoIn, RegisterIn, RoleIn, RoundIn, ShortlistIn,
)
from .service import DriveService

bp = Blueprint("drive", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter")
READ = ("super_admin", "company_admin", "recruiter", "college_admin", "student")

DRIVE_GRANT_TTL = 12 * 3600


def _mint_drive_grant(user_id: str, drive_id: str) -> str:
    now = int(time.time())
    secret = current_app.config["LARE"].INTERNAL_JWT_SECRET
    return jwt.encode({"sub": user_id, "drive_id": drive_id, "scope": "drive_access",
                       "iat": now, "exp": now + DRIVE_GRANT_TTL}, secret, algorithm="HS256")


def _svc() -> DriveService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


@bp.put("/drive/v1/drives/<did>/workflow")
@require_roles(*MANAGE)
def set_workflow(did):
    body = request.get_json(silent=True) or {}
    stages = body.get("stages") or []
    with _db().session() as s:
        return ok(_svc().set_workflow(s, did, stages))


@bp.get("/drive/v1/drives/<did>/workflow")
@require_roles(*READ)
def get_workflow(did):
    with _db().session() as s:
        return ok(_svc().workflow(s, did))


@bp.delete("/drive/v1/drives/<did>/rounds/<int:order>")
@require_roles(*MANAGE)
def delete_round(did, order):
    """Delete a round mid-pipeline; later rounds shift up and candidates flow on."""
    with _db().session() as s:
        return ok(_svc().delete_round(s, did, order))


# ---------- round marks sheet (written auto + panel-scored rounds) ----------
@bp.get("/drive/v1/drives/<did>/rounds/<int:order>/scores")
@require_roles(*MANAGE)
def round_scores(did, order):
    with _db().session() as s:
        return ok(_svc().round_scores(s, did, order))


@bp.post("/drive/v1/drives/<did>/rounds/<int:order>/scores")
@require_roles(*MANAGE)
def set_round_score(did, order):
    ident = current_identity()
    b = request.get_json(silent=True) or {}
    if not b.get("candidate_id"):
        raise BadRequest("candidate_id required", code="candidate_id_required")
    with _db().session() as s:
        return ok(_svc().set_round_score(
            s, did, order, b["candidate_id"], marks=b.get("marks"),
            max_marks=b.get("max_marks"), remarks=b.get("remarks"),
            cleared=b.get("cleared"), entered_by=ident.user_id))


@bp.post("/drive/v1/drives/<did>/rounds/<int:order>/candidates")
@require_roles(*MANAGE)
def add_round_candidate(did, order):
    ident = current_identity()
    b = request.get_json(silent=True) or {}
    if not b.get("candidate_id"):
        raise BadRequest("candidate_id required", code="candidate_id_required")
    with _db().session() as s:
        return created(_svc().add_round_candidate(s, did, order, b["candidate_id"], ident.user_id))


@bp.delete("/drive/v1/drives/<did>/rounds/<int:order>/candidates/<candidate_id>")
@require_roles(*MANAGE)
def remove_round_candidate(did, order, candidate_id):
    with _db().session() as s:
        return ok(_svc().remove_round_candidate(s, did, order, candidate_id))


@bp.post("/drive/v1/drives/<did>/rounds/<int:order>/publish")
@require_roles(*MANAGE)
def publish_round(did, order):
    with _db().session() as s:
        result = _svc().publish_round(s, did, order)
    # Fan out one event per shortlisted/selected candidate → Notification sends
    # the in-app message + company email. Done after commit so a delivery hiccup
    # never rolls back the publish.
    from flask import current_app
    to_notify = result.pop("notify", [])
    bus = current_app.extensions.get("bus")
    if bus:
        for c in to_notify:
            bus.publish("round.shortlisted", c)
    return ok(result)


@bp.post("/drive/v1/drives/<did>/joining/<candidate_id>")
@require_roles(*MANAGE)
def set_joining(did, candidate_id):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_joining_status(s, did, candidate_id, body.get("status", "")))


@bp.get("/drive/v1/search")
@require_roles(*READ)
def search():
    q = request.args.get("q", "").strip()
    with _db().session() as s:
        return ok(_svc().search(s, q) if q else [])


@bp.put("/drive/v1/drives/<did>/form")
@require_roles(*MANAGE)
def set_form(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_form(s, did, body.get("fields") or []))


@bp.get("/drive/v1/drives/<did>/form")
@require_roles(*READ)
def get_form(did):
    with _db().session() as s:
        return ok(_svc().get_form(s, did))


@bp.post("/drive/v1/drives/<did>/form/submit")
def submit_form(did):
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().submit_form(s, did, ident.user_id, body.get("answers") or {}))


@bp.get("/drive/v1/drives/<did>/form/submissions")
@require_roles(*MANAGE)
def form_submissions(did):
    with _db().session() as s:
        return ok(_svc().form_submissions(s, did))


@bp.put("/drive/v1/drives/<did>/schedule")
@require_roles(*MANAGE)
def set_schedule(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_schedule(s, did, body))


@bp.get("/drive/v1/calendar")
@require_roles(*READ)
def calendar():
    did = request.args.get("drive_id")
    with _db().session() as s:
        return ok(_svc().calendar(s, did))


@bp.post("/drive/v1/drives/<did>/seats/allocate")
@require_roles(*MANAGE)
def allocate_seats(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().allocate_seats(s, did, body.get("labs") or []))


@bp.get("/drive/v1/drives/<did>/seats")
@require_roles(*READ)
def seats(did):
    with _db().session() as s:
        return ok(_svc().seat_map(s, did))


@bp.get("/drive/v1/drives/<did>/hall-ticket/<candidate_id>")
def hall_ticket(did, candidate_id):
    """Hall ticket PDF with reporting details + QR payload (req #17). Staff for
    anyone; a candidate only for themselves."""
    from lare_common.platform import feature_enabled
    ident = current_identity()
    if not (ident.has_role(*MANAGE) or ident.user_id == candidate_id):
        raise Forbidden("Not permitted")
    if not feature_enabled("hall_tickets", ident.tenant_id):
        raise BadRequest("Hall tickets are disabled", code="feature_disabled")
    with _db().session() as s:
        blob, filename = _svc().hall_ticket(s, did, candidate_id)
    return Response(blob, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/drives")
@require_roles(*MANAGE)
def create():
    ident = current_identity()
    data = _parse(DriveIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().out(_svc().create(s, data, ident.user_id)))


@bp.get("/drive/v1/drives")
@require_roles(*READ)
def list_drives():
    status = request.args.get("status")
    limit = min(int(request.args.get("limit", 50)), 200)
    # A candidate who passed the Drive Access Gate is bound to exactly one drive
    # (the Gateway injects X-Drive-Id from their grant) — show only that drive.
    bound = request.headers.get("X-Drive-Id")
    with _db().session() as s:
        drives = _svc().list(s, status, limit)
        if bound:
            drives = [d for d in drives if d.id == bound]
        return ok([_svc().out(d) for d in drives])


@bp.get("/drive/v1/drives/<did>/my-round")
@require_roles(*READ)
def my_round(did):
    """The calling candidate's current round + the drive pipeline (for gating
    which round's assessment is visible)."""
    with _db().session() as s:
        return ok(_svc().candidate_round(s, did, current_identity().user_id))


@bp.get("/drive/v1/opportunities")
@require_roles(*READ)
def opportunities():
    """Skills-to-Opportunity (Lityra Hire): open drives ranked by how well the
    candidate's drive-exam skills match the roles. A student sees their own; staff
    may pass ?candidate_id= to view any."""
    ident = current_identity()
    cid = request.args.get("candidate_id") or ident.user_id
    if not ident.has_role("super_admin", "company_admin", "recruiter", "college_admin") \
            and cid != ident.user_id:
        raise Forbidden("You can only view your own opportunities.")
    bound = request.headers.get("X-Drive-Id")  # gated candidate → only their drive
    with _db().session() as s:
        return ok(_svc().match_opportunities(s, cid, bound_drive_id=bound))


@bp.get("/drive/v1/drives/<did>")
@require_roles(*READ)
def get_drive(did):
    with _db().session() as s:
        d = _svc().get(s, did)
        return ok({**_svc().out(d),
                   "roles": [_svc().role_out(r) for r in d.roles],
                   "rounds": [_svc().round_out(r) for r in _svc().rounds(s, did)]})


# Delete a drive and all its data. Restricted to admins (not recruiters).
@bp.delete("/drive/v1/drives/<did>")
@require_roles(*MANAGE)
def delete_drive(did):
    with _db().session() as s:
        return ok(_svc().delete(s, did))


@bp.post("/drive/v1/drives/<did>/roles")
@require_roles(*MANAGE)
def add_role(did):
    data = _parse(RoleIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().role_out(_svc().add_role(s, did, data)))


@bp.post("/drive/v1/drives/<did>/eligibility")
@require_roles(*MANAGE)
def set_eligibility(did):
    data = _parse(EligibilityIn, request.get_json(silent=True))
    with _db().session() as s:
        er = _svc().set_eligibility(s, did, data)
        return ok({"drive_id": did, "rule": er.rule})


@bp.post("/drive/v1/drives/<did>/rounds")
@require_roles(*MANAGE)
def add_round(did):
    data = _parse(RoundIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().round_out(_svc().add_round(s, did, data)))


@bp.post("/drive/v1/drives/<did>/open")
@require_roles(*MANAGE)
def open_drive(did):
    with _db().session() as s:
        return ok(_svc().out(_svc().open_drive(s, did)))


@bp.post("/drive/v1/drives/<did>/register")
@require_roles(*MANAGE)
def register(did):
    data = _parse(RegisterIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().register(s, did, data))


@bp.post("/drive/v1/drives/<did>/shortlist")
@require_roles(*MANAGE)
def shortlist(did):
    data = _parse(ShortlistIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().shortlist(s, did, data.candidate_ids))


@bp.post("/drive/v1/drives/<did>/advance")
@require_roles(*MANAGE)
def advance(did):
    data = _parse(AdvanceIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().advance(s, did, data.candidate_id))


@bp.get("/drive/v1/drives/<did>/registrations")
@require_roles(*MANAGE)
def registrations(did):
    with _db().session() as s:
        return ok(_svc().registrations(s, did))


@bp.get("/drive/v1/drives/<did>/funnel")
@require_roles(*MANAGE)
def funnel(did):
    with _db().session() as s:
        return ok(_svc().funnel(s, did))


@bp.get("/drive/v1/drives/<did>/analytics")
@require_roles(*MANAGE)
def analytics(did):
    with _db().session() as s:
        return ok(_svc().analytics(s, did))


@bp.get("/drive/v1/drives/<did>/rounds/<int:order>/export")
@require_roles(*MANAGE)
def export_round(did, order):
    """Download a round's marks as .xlsx. ?cleared=true → only cleared students."""
    cleared_only = request.args.get("cleared", "").lower() in ("1", "true", "yes")
    with _db().session() as s:
        blob, filename = _svc().export_round(s, did, order, cleared_only)
    return Response(
        blob,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.post("/drive/v1/drives/<did>/ppo-config")
@require_roles("super_admin", "company_admin")
def set_ppo(did):
    data = _parse(PpoIn, request.get_json(silent=True))
    with _db().session() as s:
        _svc().set_ppo(s, did, data)
        return ok({"drive_id": did, "ppo_configured": True})


# ---------- Drive Access Gate ----------
@bp.post("/drive/v1/access/codes")
@require_roles(*MANAGE)
def create_drive_access_code():
    data = _parse(DriveAccessCodeIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().access_code_out(
            _svc().create_access_code(s, data, current_identity().user_id)))


@bp.get("/drive/v1/access/codes")
@require_roles(*MANAGE)
def list_drive_access_codes():
    drive_id = request.args.get("drive_id")
    with _db().session() as s:
        return ok([_svc().access_code_out(ac) for ac in _svc().list_access_codes(s, drive_id)])


@bp.post("/drive/v1/access/codes/<cid>/status")
@require_roles(*MANAGE)
def set_drive_access_status(cid):
    data = _parse(DriveAccessStatusIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().access_code_out(_svc().set_access_status(s, cid, data.status)))


@bp.post("/drive/v1/access/codes/<cid>/regenerate")
@require_roles(*MANAGE)
def regenerate_drive_access_code(cid):
    with _db().session() as s:
        return ok(_svc().access_code_out(_svc().regenerate_access_code(s, cid)))


@bp.post("/drive/v1/access/validate")
def validate_drive_access():
    """Candidate (Hire login) presents the Drive Access ID → bound to that drive."""
    data = _parse(DriveAccessValidateIn, request.get_json(silent=True))
    uid = current_identity().user_id
    with _db().session() as s:
        result = _svc().validate_access(s, data.code, uid)
    result["grant"] = _mint_drive_grant(uid, result["drive_id"])
    return ok(result)


@bp.post("/drive/v1/access/exit")
def exit_drive_access():
    with _db().session() as s:
        _svc().clear_access_session(s, current_identity().user_id)
        return ok({"cleared": True})

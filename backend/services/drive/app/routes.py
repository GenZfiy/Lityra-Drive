"""HTTP layer for the Recruitment Drive Service."""
from __future__ import annotations

import time
from functools import wraps

import jwt
from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError
from sqlalchemy import select

from lare_common.auth_context import current_identity, require_permission, require_roles
from lare_common.errors import BadRequest, Forbidden, NotFound
from lare_common.responses import created, ok

from .schemas import (
    AdvanceIn, DriveAccessCodeIn, DriveAccessStatusIn, DriveAccessValidateIn, DriveIn,
    EligibilityIn, ParticipationDecisionIn, PpoIn, RegisterIn, RoleIn, RoundIn, ShortlistIn,
)
from .models import Drive, DriveAccessCode, DriveCompanyParticipation, DriveInstitutionParticipation
from .service import DriveService

bp = Blueprint("drive", __name__)

MANAGE = ("drive.drive.manage",)
READ = ("drive.drive.view",)

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


def _publish_drive_event(event_type: str, payload: dict) -> None:
    bus = current_app.extensions.get("bus")
    if not bus:
        return
    try:
        bus.publish(event_type, payload)
    except Exception:  # noqa: BLE001 — audit/notification transport cannot undo a committed change
        current_app.logger.exception("Could not publish drive event %s", event_type)


def _assert_drive_scope(drive, ident, session):
    if ident.has_role("super_admin"):
        return
    if "student" in ident.roles and not ident.has_permission("drive.drive.manage"):
        if request.headers.get("X-Drive-Id") != drive.id or drive.status != "open":
            raise Forbidden("Enter this drive using its access code")
        return
    if _svc().can_access_drive(session, drive, ident):
        return
    raise Forbidden("This drive is outside your assigned scope")


def _can_manage_access_code(session, drive, ident) -> bool:
    if ident.has_role("super_admin") or _svc().recruitment_access(session, drive, ident):
        return True
    if not ident.has_role("tpo", "college_admin", "dean", "principal"):
        return False
    college_ids = set(ident.college_ids or [])
    if drive.organizer_type == "college" and drive.organizer_id in college_ids:
        return True
    if not drive.host_college_id or drive.host_college_id not in college_ids:
        return False
    return session.execute(select(DriveInstitutionParticipation.id).where(
        DriveInstitutionParticipation.drive_id == drive.id,
        DriveInstitutionParticipation.college_id == drive.host_college_id,
        DriveInstitutionParticipation.status == "accepted",
        DriveInstitutionParticipation.attendance_allowed.is_(True))).first() is not None


@bp.before_request
def enforce_drive_record_scope():
    """Apply object scope centrally to every route carrying a drive identifier.

    Hiring staff are limited to drives they created unless they are platform
    administrators; college-scoped operators are limited to their bound college
    ids. Candidates must carry the gateway-verified Drive Access grant.
    """
    view_args = request.view_args or {}
    drive_id = view_args.get("did") or view_args.get("drive_id")
    if not drive_id:
        return None
    ident = current_identity()
    with _db().session() as session:
        drive = session.get(Drive, drive_id)
        if not drive:
            raise NotFound("Drive not found", code="drive_not_found")
        if request.endpoint != "drive.decide_participation":
            _assert_drive_scope(drive, ident, session)
        # College participation grants event coordination only. Candidate
        # evaluations, round outcomes, and offer-related data stay company-owned.
        path = request.path
        confidential = ("/registrations" in path or "/shortlist" in path or
                        "/advance" in path or "/funnel" in path or "/analytics" in path or
                        "/rounds/" in path or "/form/submissions" in path or
                        "/ppo-config" in path or "/seats" in path or "/hall-ticket/" in path or
                        "/joining/" in path)
        company_controlled = ("/roles" in path or "/eligibility" in path or "/rounds" in path or
                              "/workflow" in path or ("/form" in path and not path.endswith("/form/submit")) or "/schedule" in path or
                              "/ppo-config" in path or path.endswith("/open"))
        if ((confidential or company_controlled) and
                not _svc().recruitment_access(session, drive, ident)):
            raise Forbidden("Recruitment workflow and confidential data are controlled by the recruiting company")


@bp.put("/drive/v1/drives/<did>/workflow")
@require_permission(*MANAGE)
def set_workflow(did):
    body = request.get_json(silent=True) or {}
    stages = body.get("stages") or []
    with _db().session() as s:
        return ok(_svc().set_workflow(s, did, stages))


@bp.get("/drive/v1/drives/<did>/workflow")
@require_permission(*READ)
def get_workflow(did):
    with _db().session() as s:
        return ok(_svc().workflow(s, did))


@bp.delete("/drive/v1/drives/<did>/rounds/<int:order>")
@require_permission(*MANAGE)
def delete_round(did, order):
    """Delete a round mid-pipeline; later rounds shift up and candidates flow on."""
    with _db().session() as s:
        return ok(_svc().delete_round(s, did, order))


# ---------- round marks sheet (written auto + panel-scored rounds) ----------
@bp.get("/drive/v1/drives/<did>/rounds/<int:order>/scores")
@require_permission(*MANAGE)
def round_scores(did, order):
    with _db().session() as s:
        return ok(_svc().round_scores(s, did, order))


@bp.post("/drive/v1/drives/<did>/rounds/<int:order>/scores")
@require_permission(*MANAGE)
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
@require_permission(*MANAGE)
def add_round_candidate(did, order):
    ident = current_identity()
    b = request.get_json(silent=True) or {}
    if not b.get("candidate_id"):
        raise BadRequest("candidate_id required", code="candidate_id_required")
    with _db().session() as s:
        return created(_svc().add_round_candidate(s, did, order, b["candidate_id"], ident.user_id))


@bp.delete("/drive/v1/drives/<did>/rounds/<int:order>/candidates/<candidate_id>")
@require_permission(*MANAGE)
def remove_round_candidate(did, order, candidate_id):
    with _db().session() as s:
        return ok(_svc().remove_round_candidate(s, did, order, candidate_id))


@bp.post("/drive/v1/drives/<did>/rounds/<int:order>/publish")
@require_permission("drive.result.publish")
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
@require_permission("drive.result.publish")
def set_joining(did, candidate_id):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_joining_status(s, did, candidate_id, body.get("status", "")))


@bp.get("/drive/v1/search")
@require_permission(*READ)
def search():
    q = request.args.get("q", "").strip()
    with _db().session() as s:
        return ok(_svc().search(s, q, current_identity()) if q else [])


@bp.put("/drive/v1/drives/<did>/form")
@require_permission(*MANAGE)
def set_form(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_form(s, did, body.get("fields") or []))


@bp.get("/drive/v1/drives/<did>/form")
@require_permission(*READ)
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
@require_permission(*MANAGE)
def form_submissions(did):
    with _db().session() as s:
        return ok(_svc().form_submissions(s, did))


@bp.put("/drive/v1/drives/<did>/schedule")
@require_permission(*MANAGE)
def set_schedule(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().set_schedule(s, did, body))


@bp.get("/drive/v1/calendar")
@require_permission(*MANAGE)
def calendar():
    ident = current_identity()
    did = request.args.get("drive_id")
    with _db().session() as s:
        if did:
            _assert_drive_scope(_svc().get(s, did), ident, s)
            return ok(_svc().calendar(s, did))
        if ident.has_role("super_admin"):
            return ok(_svc().calendar(s))
        drives = _svc().accessible_drives(s, ident, None, 500)
        return ok([event for drive in drives for event in _svc().calendar(s, drive.id)])


@bp.post("/drive/v1/drives/<did>/seats/allocate")
@require_permission("drive.drive.manage")
def allocate_seats(did):
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().allocate_seats(s, did, body.get("labs") or []))


@bp.get("/drive/v1/drives/<did>/seats")
@require_permission(*READ)
def seats(did):
    with _db().session() as s:
        return ok(_svc().seat_map(s, did))


@bp.get("/drive/v1/drives/<did>/hall-ticket/<candidate_id>")
def hall_ticket(did, candidate_id):
    """Hall ticket PDF with reporting details + QR payload (req #17). Staff for
    anyone; a candidate only for themselves."""
    from lare_common.platform import feature_enabled
    ident = current_identity()
    if not (ident.has_permission("drive.drive.manage") or ident.user_id == candidate_id):
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
@require_permission(*MANAGE)
def create():
    ident = current_identity()
    data = _parse(DriveIn, request.get_json(silent=True))
    with _db().session() as s:
        drive = _svc().create(s, data, ident)
        result = {**_svc().out(drive), **_svc().organization_out(s, drive)}
    _publish_drive_event("drive.created", {"drive_id": result["id"], "drive_type": result["drive_type"],
        "organizer_type": result["organizer_type"], "organizer_id": result["organizer_id"],
        "actor_id": ident.user_id, "tenant_id": ident.tenant_id})
    return created(result)


@bp.get("/drive/v1/drives")
@require_permission(*READ)
def list_drives():
    ident = current_identity()
    status = request.args.get("status")
    limit = min(int(request.args.get("limit", 50)), 200)
    # A candidate who passed the Drive Access Gate is bound to exactly one drive
    # (the Gateway injects X-Drive-Id from their grant) — show only that drive.
    bound = request.headers.get("X-Drive-Id")
    with _db().session() as s:
        if "student" in ident.roles and not ident.has_permission("drive.drive.manage"):
            drives = _svc().list(s, "open", limit)
            drives = [drive for drive in drives if not (
                drive.organizer_type == "college" and
                (drive.workflow_config or {}).get("company_pipelines") and
                not drive.pipeline_company_id)]
        else:
            drives = _svc().accessible_drives(s, ident, status, limit)
        if bound:
            drives = [d for d in drives if d.id == bound]
        return ok([_svc().out(d) for d in drives])


@bp.get("/drive/v1/assigned-candidates")
@require_permission("drive.candidate.view")
def assigned_candidate_ids():
    with _db().session() as s:
        return ok(_svc().assigned_candidate_ids(s, current_identity()))


@bp.get("/drive/v1/drives/<did>/my-round")
@require_permission(*READ)
def my_round(did):
    """The calling candidate's current round + the drive pipeline (for gating
    which round's assessment is visible)."""
    with _db().session() as s:
        return ok(_svc().candidate_round(s, did, current_identity().user_id))


@bp.get("/drive/v1/opportunities")
@require_permission(*READ)
def opportunities():
    """Skills-to-Opportunity (Lityra Hire): open drives ranked by how well the
    candidate's drive-exam skills match the roles. A student sees their own; staff
    may pass ?candidate_id= to view any."""
    ident = current_identity()
    cid = request.args.get("candidate_id") or ident.user_id
    if not ident.has_permission("drive.candidate.view") \
            and cid != ident.user_id:
        raise Forbidden("You can only view your own opportunities.")
    bound = request.headers.get("X-Drive-Id")  # gated candidate → only their drive
    with _db().session() as s:
        return ok(_svc().match_opportunities(s, cid, bound_drive_id=bound))


@bp.get("/drive/v1/drives/<did>")
@require_permission(*READ)
def get_drive(did):
    ident = current_identity()
    with _db().session() as s:
        d = _svc().get(s, did)
        data = _svc().out(d)
        recruiter = _svc().recruitment_access(s, d, ident)
        if recruiter:
            data["roles"] = [_svc().role_out(r) for r in d.roles]
            data.update(_svc().organization_out(s, d))
            data["rounds"] = [
                {"id": row.id, "order": row.order, "type": row.type, "label": row.label,
                 "optional": row.optional, "config": row.config, "service_ref": row.service_ref}
                for row in _svc().rounds(s, did)]
        elif not ident.has_role("student"):
            # Coordination access supports hosting and student nominations, but
            # compensation, custom role details, and round configuration remain
            # visible only to the recruiting company.
            data["roles"] = [{"id": row.id, "title": row.title,
                              "positions": row.positions, "skills": row.skills or []}
                             for row in d.roles]
            organization = _svc().organization_out(s, d)
            data.update({key: organization[key] for key in (
                "drive_type", "organizer_type", "host_college_id", "adoption_status")})
            if d.organizer_type == "college" and d.organizer_id in (ident.college_ids or []):
                data["organizer_id"] = d.organizer_id
            data["institutions"] = [{key: row[key] for key in (
                "college_id", "status", "nomination_required", "attendance_allowed")}
                for row in organization["institutions"]]
        else:
            data["roles"] = [{"id": row.id, "title": row.title,
                              "positions": row.positions, "skills": row.skills or []}
                             for row in d.roles]
            data["rounds"] = [{"id": row.id, "order": row.order, "type": row.type,
                                "label": row.label, "optional": row.optional}
                               for row in _svc().rounds(s, did)]
        return ok(data)


@bp.post("/drive/v1/drives/<did>/institutions/invite")
@require_permission("drive.participation.manage")
def invite_institutions(did):
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    college_ids = body.get("college_ids")
    if not isinstance(college_ids, list) or not college_ids or len(college_ids) > 50:
        raise BadRequest("Provide between 1 and 50 college_ids", code="invalid_participants")
    with _db().session() as s:
        drive = _svc().get(s, did)
        company_owner = _svc().recruitment_access(s, drive, ident)
        college_owner = (drive.organizer_type == "college" and
                         drive.organizer_id in (ident.college_ids or []) and
                         ident.has_role("tpo", "college_admin", "dean", "super_admin"))
        if not company_owner and not college_owner:
            raise Forbidden("Only a drive organizer can invite colleges")
        if drive.drive_type in {"college_hosted", "college_adopted"} and not college_owner:
            raise BadRequest("Company-managed drives cannot invite colleges through this route", code="invalid_participant_type")
        rows = _svc().add_colleges(s, drive, [str(x) for x in college_ids], ident.user_id)
        drive.workflow_config = {**(drive.workflow_config or {}), "institution_participation_enabled": True}
    _publish_drive_event("drive.participant.invited", {"drive_id": did, "kind": "college",
        "participant_ids": [row["college_id"] for row in rows], "actor_id": ident.user_id,
        "drive_title": drive.title, "organizer_name": drive.company_name or "The drive organizer"})
    return created(rows)


@bp.post("/drive/v1/drives/<did>/companies/invite")
@require_permission("drive.participation.manage")
def invite_companies(did):
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    company_ids = body.get("company_ids")
    adopting = bool(body.get("adopting", False))
    if not isinstance(company_ids, list) or not company_ids or len(company_ids) > 50:
        raise BadRequest("Provide between 1 and 50 company_ids", code="invalid_participants")
    with _db().session() as s:
        drive = _svc().get(s, did)
        if not ident.college_ids or drive.organizer_type != "college" or drive.organizer_id not in ident.college_ids:
            raise Forbidden("Only the organizing college can invite recruiting companies")
        if adopting and drive.drive_type != "college_adopted":
            raise BadRequest("Adoption is only available for college-adopted drives", code="invalid_adoption")
        is_adoption = drive.drive_type == "college_adopted" or adopting
        rows = _svc().invite_companies(s, drive, [str(x) for x in company_ids], ident.user_id, is_adoption)
        drive.workflow_config = {**(drive.workflow_config or {}),
                                 "company_participation_enabled": True,
                                 "company_pipelines": True}
    _publish_drive_event("drive.participant.invited", {"drive_id": did, "kind": "company",
        "participant_ids": [row["company_id"] for row in rows], "adopting": is_adoption,
        "actor_id": ident.user_id, "drive_title": drive.title,
        "organizer_name": "The organizing college"})
    return created(rows)


@bp.post("/drive/v1/drives/<did>/participation/<kind>/<participant_id>")
def decide_participation(did, kind, participant_id):
    ident = current_identity()
    data = _parse(ParticipationDecisionIn, request.get_json(silent=True))
    if kind == "company":
        if (not ident.has_role("company_admin", "recruiter", "super_admin") or
                not ident.has_permission("drive.adoption.respond") or participant_id != ident.tenant_id):
            raise Forbidden("You may only respond for your own company")
    elif kind == "college":
        if (participant_id not in (ident.college_ids or []) or
                not ident.has_role("tpo", "college_admin", "principal", "super_admin") or
                not ident.has_permission("drive.participation.manage")):
            raise Forbidden("You may only respond for an assigned college")
    else:
        raise BadRequest("Participant type must be company or college", code="invalid_participant_type")
    with _db().session() as s:
        drive = _svc().get(s, did)
        result = _svc().set_participation(
            s, did, college_id=participant_id if kind == "college" else None,
            company_id=participant_id if kind == "company" else None,
            decision=data.decision, actor_id=ident.user_id)
    _publish_drive_event("drive.participation.decided", {**result, "actor_id": ident.user_id,
        "decision": data.decision, "note": data.note})
    return ok(result)


@bp.get("/drive/v1/invitations")
def list_participation_invitations():
    ident = current_identity()
    if not (ident.has_permission("drive.participation.manage") or
            ident.has_permission("drive.adoption.respond") or ident.has_role("super_admin")):
        raise Forbidden("Drive participation access is required")
    invitations = []
    with _db().session() as s:
        if ident.has_role("company_admin", "recruiter"):
            rows = s.execute(select(DriveCompanyParticipation, Drive).join(
                Drive, Drive.id == DriveCompanyParticipation.drive_id).where(
                    DriveCompanyParticipation.company_id == ident.tenant_id,
                    DriveCompanyParticipation.status == "invited")).all()
            for item, drive in rows:
                invitations.append({"drive_id": drive.id, "title": drive.title,
                    "drive_type": drive.drive_type, "kind": "company", "participant_id": item.company_id,
                    "role": item.participation_role, "status": item.status,
                    "company_name": drive.company_name, "venue": drive.venue})
        if ident.college_ids and ident.has_role("tpo", "college_admin", "principal"):
            rows = s.execute(select(DriveInstitutionParticipation, Drive).join(
                Drive, Drive.id == DriveInstitutionParticipation.drive_id).where(
                    DriveInstitutionParticipation.college_id.in_(ident.college_ids),
                    DriveInstitutionParticipation.status == "invited")).all()
            for item, drive in rows:
                invitations.append({"drive_id": drive.id, "title": drive.title,
                    "drive_type": drive.drive_type, "kind": "college", "participant_id": item.college_id,
                    "role": "host" if item.college_id == drive.host_college_id else "participant",
                    "status": item.status, "company_name": drive.company_name, "venue": drive.venue})
    return ok(invitations)


@bp.post("/drive/v1/drives/<did>/transition")
@require_permission(*MANAGE, "drive.approval.manage")
def transition_drive(did):
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    target = body.get("status")
    if target not in {"published", "open", "closed", "completed", "cancelled", "archived", "draft"}:
        raise BadRequest("Unsupported drive status", code="invalid_drive_status")
    with _db().session() as s:
        drive = _svc().get(s, did)
        college_owner = drive.organizer_type == "college" and drive.organizer_id in (ident.college_ids or [])
        company_owner = (drive.organizer_type in {"company", "joint"} and
                         drive.organizer_id == ident.tenant_id and
                         drive.tenant_id == ident.tenant_id and
                         ident.has_role("company_admin", "recruiter"))
        owner = ident.has_role("super_admin") or college_owner or company_owner
        if not owner:
            raise Forbidden("This role cannot manage the drive lifecycle")
        if drive.status == "pending_review" and target == "published":
            if not ident.has_role("super_admin") and (not ident.has_permission("drive.approval.manage") or not college_owner):
                raise Forbidden("Only an authorized college approver can publish this drive")
            if drive.drive_type == "college_adopted" and drive.adoption_status != "accepted":
                raise BadRequest("The adopting company must accept before publication", code="adoption_pending")
        updated = _svc().transition(s, did, target)
        result = _svc().out(updated)
    _publish_drive_event("drive.lifecycle.changed", {"drive_id": did, "status": result["status"],
        "actor_id": ident.user_id, "tenant_id": ident.tenant_id})
    return ok(result)


# Delete a drive and all its data. Restricted to admins (not recruiters).
@bp.delete("/drive/v1/drives/<did>")
@require_permission("drive.drive.delete")
def delete_drive(did):
    with _db().session() as s:
        return ok(_svc().delete(s, did))


@bp.post("/drive/v1/drives/<did>/roles")
@require_permission(*MANAGE)
def add_role(did):
    data = _parse(RoleIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().role_out(_svc().add_role(s, did, data)))


@bp.post("/drive/v1/drives/<did>/eligibility")
@require_permission(*MANAGE)
def set_eligibility(did):
    data = _parse(EligibilityIn, request.get_json(silent=True))
    with _db().session() as s:
        er = _svc().set_eligibility(s, did, data)
        return ok({"drive_id": did, "rule": er.rule})


@bp.post("/drive/v1/drives/<did>/rounds")
@require_permission(*MANAGE)
def add_round(did):
    data = _parse(RoundIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().round_out(_svc().add_round(s, did, data)))


@bp.post("/drive/v1/drives/<did>/open")
@require_permission(*MANAGE)
def open_drive(did):
    ident = current_identity()
    with _db().session() as s:
        drive = _svc().get(s, did)
        company_owner = (drive.organizer_type in {"company", "joint"} and
                         drive.organizer_id == ident.tenant_id and drive.tenant_id == ident.tenant_id and
                         ident.has_role("company_admin", "recruiter"))
        college_owner = drive.organizer_type == "college" and drive.organizer_id in (ident.college_ids or [])
        if not (ident.has_role("super_admin") or company_owner or college_owner):
            raise Forbidden("Only the drive organizer can open this event")
        return ok(_svc().out(_svc().open_drive(s, did)))


@bp.post("/drive/v1/drives/<did>/register")
@require_permission(*MANAGE)
def register(did):
    data = _parse(RegisterIn, request.get_json(silent=True))
    with _db().session() as s:
        drive = _svc().get(s, did)
        if (drive.organizer_type == "college" and
                (drive.workflow_config or {}).get("company_pipelines") and
                not drive.pipeline_company_id):
            raise BadRequest("Apply to a recruiting company's separate pipeline for this event",
                             code="company_pipeline_required")
        return created(_svc().register(s, did, data))


@bp.post("/drive/v1/drives/<did>/shortlist")
@require_permission(*MANAGE)
def shortlist(did):
    data = _parse(ShortlistIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().shortlist(s, did, data.candidate_ids))


@bp.post("/drive/v1/drives/<did>/advance")
@require_permission(*MANAGE)
def advance(did):
    data = _parse(AdvanceIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().advance(s, did, data.candidate_id))


@bp.get("/drive/v1/drives/<did>/registrations")
@require_permission(*MANAGE)
def registrations(did):
    with _db().session() as s:
        return ok(_svc().registrations(s, did))


@bp.get("/drive/v1/drives/<did>/funnel")
@require_permission(*MANAGE)
def funnel(did):
    with _db().session() as s:
        return ok(_svc().funnel(s, did))


@bp.get("/drive/v1/drives/<did>/analytics")
@require_permission("drive.data.export")
def analytics(did):
    with _db().session() as s:
        return ok(_svc().analytics(s, did))


@bp.get("/drive/v1/drives/<did>/rounds/<int:order>/export")
@require_permission("drive.access.manage")
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
@require_permission("drive.access.manage")
def create_drive_access_code():
    data = _parse(DriveAccessCodeIn, request.get_json(silent=True))
    with _db().session() as s:
        drive = _svc().get(s, data.drive_id)
        if not _can_manage_access_code(s, drive, current_identity()):
            raise Forbidden("Only the organizer, recruiting company, or assigned host can manage drive access codes")
        return created(_svc().access_code_out(
            _svc().create_access_code(s, data, current_identity().user_id)))


@bp.get("/drive/v1/access/codes")
@require_permission("drive.access.manage")
def list_drive_access_codes():
    drive_id = request.args.get("drive_id")
    ident = current_identity()
    with _db().session() as s:
        if drive_id:
            drive = _svc().get(s, drive_id)
            if not _can_manage_access_code(s, drive, ident):
                raise Forbidden("Drive access codes are outside your assigned scope")
            rows = _svc().list_access_codes(s, drive_id)
        else:
            visible_ids = [drive.id for drive in _svc().accessible_drives(s, ident, None, 500)
                           if _can_manage_access_code(s, drive, ident)]
            rows = s.execute(select(DriveAccessCode).where(
                DriveAccessCode.drive_id.in_(visible_ids)).order_by(
                    DriveAccessCode.created_at.desc())).scalars().all() if visible_ids else []
        return ok([_svc().access_code_out(ac) for ac in rows])


@bp.post("/drive/v1/access/codes/<cid>/status")
@require_permission("drive.access.manage")
def set_drive_access_status(cid):
    data = _parse(DriveAccessStatusIn, request.get_json(silent=True))
    with _db().session() as s:
        access_code = s.get(DriveAccessCode, cid)
        drive = _svc().get(s, access_code.drive_id) if access_code else None
        if not drive or not _can_manage_access_code(s, drive, current_identity()):
            raise Forbidden("Drive access code is outside your assigned scope")
        return ok(_svc().access_code_out(_svc().set_access_status(s, cid, data.status)))


@bp.post("/drive/v1/access/codes/<cid>/regenerate")
@require_permission("drive.access.manage")
def regenerate_drive_access_code(cid):
    with _db().session() as s:
        access_code = s.get(DriveAccessCode, cid)
        drive = _svc().get(s, access_code.drive_id) if access_code else None
        if not drive or not _can_manage_access_code(s, drive, current_identity()):
            raise Forbidden("Drive access code is outside your assigned scope")
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

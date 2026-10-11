"""HTTP layer for the Interview Service."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from flask import Blueprint, current_app, request
from urllib.error import HTTPError
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_permission
from lare_common.errors import BadRequest, Forbidden, NotFound, ServiceUnavailable
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient

from .schemas import AllocateIn, DecisionIn, RateIn, ScheduleIn
from .service import InterviewService

log = logging.getLogger("lare-interview")


def _notify_schedule(iv) -> None:
    """Best-effort: email the interview details to the candidate (their join link)
    and to the assigned interviewer. Runs after commit; never fails the request."""
    try:
        cli = ServiceClient("drive-interview", default_roles=["recruiter"],
                            default_permissions=["drive.candidate.view"])
        info = {}
        try:
            r = cli.get("drive-candidate", f"/drive/v1/candidates/resolve?ids={iv.candidate_id}")
            info = ((r or {}).get("data") or {}).get(iv.candidate_id) or {}
        except Exception:  # noqa: BLE001
            pass
        candidate_name = info.get("full_name") or "the candidate"
        company = "GenZify"
        try:
            d = cli.get("drive-core", f"/drive/v1/drives/{iv.drive_id}")
            company = ((d or {}).get("data") or {}).get("company_name") or company
        except Exception:  # noqa: BLE001
            pass
        common = {"stage": iv.stage, "mode": iv.mode, "slot": iv.slot or "to be confirmed",
                  "link": iv.link or "shared separately", "company": company}

        # 1) the candidate — always notified of their interview (with the join
        #    link when online; time/venue otherwise).
        cand_email = info.get("email")
        if cand_email:
            cli.post("lare-notify", "/notify/v1/send", {
                "user_id": iv.candidate_id, "template_key": "interview_scheduled",
                "channel": "email",
                "variables": {**common, "email": cand_email, "name": candidate_name},
            })
            log.info("emailed interview link to candidate %s", iv.candidate_id)

        # 2) every assigned interviewer in the panel
        for member in getattr(iv, "panel", []) or []:
            email = member.get("email")
            if not email:
                continue
            cli.post("lare-notify", "/notify/v1/send", {
                "user_id": email, "template_key": "interview_assigned",
                "channel": "email",
                "variables": {**common, "email": email,
                              "name": member.get("name") or "Interviewer",
                              "candidate": candidate_name},
            })
            log.info("emailed interview assignment to %s", email)
    except Exception:  # noqa: BLE001 — notification is best-effort
        log.warning("could not send interview notifications for %s", getattr(iv, "candidate_id", "?"))

bp = Blueprint("interview", __name__)

MANAGE = ("drive.interview.manage",)
PANEL = ("drive.interview.review",)
_DRIVE = ServiceClient("drive-interview")


def _assert_drive_scope(ident, drive_id):
    """Ask the Drive owner service to enforce the caller's signed scope."""
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


def _check_interview_assignment(session, ident, interview_id):
    """Interviewers may read or act only on interviews allocated to them."""
    iv = _svc().get(session, interview_id)
    if "interviewer" in ident.roles and not ident.has_permission("drive.interview.manage"):
        if iv.interviewer_id != ident.user_id:
            raise Forbidden("This interview is not assigned to you")
        return iv
    _assert_drive_scope(ident, iv.drive_id)
    return iv


def _svc() -> InterviewService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/interviews/schedule")
@require_permission(*MANAGE)
def schedule():
    data = _parse(ScheduleIn, request.get_json(silent=True))
    _assert_drive_scope(current_identity(), data.drive_id)
    # Build the interviewer panel: the list, plus the back-compat single field,
    # de-duplicated by email.
    panel, seen = [], set()
    for i in [*data.interviewers,
              SimpleNamespace(name=data.interviewer_name, email=data.interviewer_email)]:
        email = (getattr(i, "email", None) or "").strip().lower()
        if email and email not in seen:
            seen.add(email)
            panel.append({"name": getattr(i, "name", None), "email": email})

    with _db().session() as s:
        iv = _svc().schedule(s, data)
        out = _svc().out(iv)
        # Snapshot the fields the notifications need before the session closes.
        snap = SimpleNamespace(candidate_id=iv.candidate_id, drive_id=iv.drive_id,
                               stage=iv.stage, mode=iv.mode, link=iv.link, slot=iv.slot,
                               panel=panel)
    # Email the candidate (their join link) and every assigned interviewer.
    _notify_schedule(snap)
    return created({**out, "interviewers": panel})


@bp.post("/drive/v1/interviews/<iid>/allocate")
@require_permission(*MANAGE)
def allocate(iid):
    data = _parse(AllocateIn, request.get_json(silent=True))
    with _db().session() as s:
        _check_interview_assignment(s, current_identity(), iid)
        return ok(_svc().out(_svc().allocate(s, iid, data.interviewer_id)))


@bp.get("/drive/v1/interviews/<iid>/dossier")
@require_permission(*PANEL)
def dossier(iid):
    with _db().session() as s:
        _check_interview_assignment(s, current_identity(), iid)
        return ok(_svc().dossier(s, iid))


@bp.post("/drive/v1/interviews/<iid>/rate")
@require_permission(*PANEL)
def rate(iid):
    ident = current_identity()
    data = _parse(RateIn, request.get_json(silent=True))
    with _db().session() as s:
        _check_interview_assignment(s, ident, iid)
        return ok(_svc().rate(s, iid, ident.user_id, data))


@bp.post("/drive/v1/interviews/<iid>/decision")
@require_permission(*PANEL)
def decision(iid):
    ident = current_identity()
    data = _parse(DecisionIn, request.get_json(silent=True))
    with _db().session() as s:
        _check_interview_assignment(s, ident, iid)
        out = _svc().out(_svc().decide(s, iid, ident.user_id, data))
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("interview.decided", {
            "drive_id": out.get("drive_id"), "candidate_id": out.get("candidate_id"),
            "decision": out.get("decision"), "stage": out.get("stage"),
        })
    return ok(out)


@bp.get("/drive/v1/interviews/drive/<drive_id>")
@require_permission(*MANAGE)
def for_drive(drive_id):
    _assert_drive_scope(current_identity(), drive_id)
    with _db().session() as s:
        return ok(_svc().for_drive(s, drive_id))


@bp.get("/drive/v1/interviews/mine")
@require_permission(*PANEL)
def for_interviewer():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().for_interviewer(s, ident.user_id))

"""HTTP layer for the Interview Service."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import AllocateIn, DecisionIn, RateIn, ScheduleIn
from .service import InterviewService

log = logging.getLogger("lare-interview")


def _notify_schedule(iv) -> None:
    """Best-effort: email the interview details to the candidate (their join link)
    and to the assigned interviewer. Runs after commit; never fails the request."""
    try:
        from lare_common.service_client import ServiceClient
        cli = ServiceClient("drive-interview", default_roles=["recruiter"])
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

MANAGE = ("super_admin", "company_admin", "recruiter")
PANEL = ("super_admin", "company_admin", "recruiter")


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
@require_roles(*MANAGE)
def schedule():
    data = _parse(ScheduleIn, request.get_json(silent=True))
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
@require_roles(*MANAGE)
def allocate(iid):
    data = _parse(AllocateIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().out(_svc().allocate(s, iid, data.interviewer_id)))


@bp.get("/drive/v1/interviews/<iid>/dossier")
@require_roles(*PANEL)
def dossier(iid):
    with _db().session() as s:
        return ok(_svc().dossier(s, iid))


@bp.post("/drive/v1/interviews/<iid>/rate")
@require_roles(*PANEL)
def rate(iid):
    ident = current_identity()
    data = _parse(RateIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().rate(s, iid, ident.user_id, data))


@bp.post("/drive/v1/interviews/<iid>/decision")
@require_roles(*PANEL)
def decision(iid):
    ident = current_identity()
    data = _parse(DecisionIn, request.get_json(silent=True))
    with _db().session() as s:
        out = _svc().out(_svc().decide(s, iid, ident.user_id, data))
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("interview.decided", {
            "drive_id": out.get("drive_id"), "candidate_id": out.get("candidate_id"),
            "decision": out.get("decision"), "stage": out.get("stage"),
        })
    return ok(out)


@bp.get("/drive/v1/interviews/drive/<drive_id>")
@require_roles(*MANAGE)
def for_drive(drive_id):
    with _db().session() as s:
        return ok(_svc().for_drive(s, drive_id))

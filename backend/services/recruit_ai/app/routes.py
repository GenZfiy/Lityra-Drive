"""HTTP layer for the recruit-ai service (insights + calibration).

Evidence + decision-queue reads are best-effort east-west; insights regenerate
on read so they always reflect current state.
"""
from __future__ import annotations

from flask import Blueprint, current_app

from lare_common.auth_context import current_identity, require_roles
from lare_common.responses import ok
from lare_common.service_client import ServiceClient

from .service import RecruitAiService

bp = Blueprint("recruit_ai", __name__)

READ = ("super_admin", "company_admin", "recruiter", "college_admin", "trainer")

_client = ServiceClient("drive-recruit-ai", default_roles=["recruiter"])


def _svc() -> RecruitAiService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _queue(drive_id, uid):
    try:
        r = _client.get("drive-decision", f"/drive/v1/decisions/drive/{drive_id}/queue", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


def _conflicts(drive_id, uid):
    try:
        r = _client.get("drive-evidence", f"/drive/v1/evidence/drive/{drive_id}/conflicts", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


def _drive_evidence(drive_id, uid):
    try:
        r = _client.get("drive-evidence", f"/drive/v1/evidence/drive/{drive_id}", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


@bp.get("/drive/v1/insights/drive/<did>")
@require_roles(*READ)
def insights(did):
    ident = current_identity()
    queue = _queue(did, ident.user_id)
    conflicts = _conflicts(did, ident.user_id)
    with _db().session() as s:
        return ok(_svc().generate(s, did, queue, conflicts))


@bp.post("/drive/v1/insights/drive/<did>/generate")
@require_roles(*READ)
def generate(did):
    return insights(did)


@bp.get("/drive/v1/calibration/drive/<did>")
@require_roles(*READ)
def calibration(did):
    ident = current_identity()
    evidence = _drive_evidence(did, ident.user_id)
    with _db().session() as s:
        return ok(_svc().calibration(s, did, evidence))


@bp.get("/drive/v1/calibration/interviewers")
@require_roles(*READ)
def cross_calibration():
    with _db().session() as s:
        return ok(_svc().cross_calibration(s))

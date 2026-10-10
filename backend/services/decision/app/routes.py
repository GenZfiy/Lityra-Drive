"""HTTP layer for the Decision service.

Evidence + evaluation-model reads are best-effort east-west calls to the
evidence and competency services; if a peer is unavailable the decision still
records (assessment degrades gracefully to what evidence is reachable), matching
the platform's no-hard-dependency posture for read surfaces.
"""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient

from .schemas import DecisionIn
from .service import DecisionService

bp = Blueprint("decision", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter")
READ = ("super_admin", "company_admin", "recruiter", "college_admin", "trainer")

_client = ServiceClient("drive-decision", default_roles=["recruiter"])


def _svc() -> DecisionService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _candidate_evidence(cid, drive_id, uid):
    try:
        r = _client.get("drive-evidence", f"/drive/v1/evidence/candidate/{cid}?drive_id={drive_id}", user_id=uid)
        return ((r or {}).get("data") or {}).get("evidence", []) or []
    except Exception:  # noqa: BLE001 — best effort
        return []


def _drive_evidence(drive_id, uid):
    try:
        r = _client.get("drive-evidence", f"/drive/v1/evidence/drive/{drive_id}", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


def _model_weights(drive_id, uid):
    try:
        r = _client.get("drive-competency", f"/drive/v1/competency/models/{drive_id}", user_id=uid)
        return ((r or {}).get("data") or {}).get("weights", []) or []
    except Exception:  # noqa: BLE001
        return []


@bp.post("/drive/v1/decisions")
@require_roles(*MANAGE)
def record():
    try:
        body = DecisionIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        raise BadRequest("Invalid decision") from e
    ident = current_identity()
    evidence = _candidate_evidence(body.candidate_id, body.drive_id, ident.user_id)
    weights = _model_weights(body.drive_id, ident.user_id)
    assessment = _svc().assess(evidence, weights)
    with _db().session() as s:
        res = _svc().record(
            s, drive_id=body.drive_id, candidate_id=body.candidate_id,
            round_key=body.round_key, verdict=body.verdict, note=body.note,
            evidence_ids=body.evidence_ids, decided_by=ident.user_id, assessment=assessment)
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("decision.made", {
            "drive_id": body.drive_id, "candidate_id": body.candidate_id,
            "verdict": body.verdict, "confidence": assessment.get("confidence"),
        }, key=body.candidate_id)
    return created({**res, "assessment": assessment})


@bp.get("/drive/v1/decisions/drive/<did>")
@require_roles(*READ)
def for_drive(did):
    with _db().session() as s:
        return ok(_svc().for_drive(s, did))


@bp.get("/drive/v1/decisions/drive/<did>/queue")
@require_roles(*READ)
def queue(did):
    ident = current_identity()
    evidence = _drive_evidence(did, ident.user_id)
    weights = _model_weights(did, ident.user_id)
    with _db().session() as s:
        return ok(_svc().queue(s, did, evidence, weights))


@bp.get("/drive/v1/decisions/candidate/<cid>")
@require_roles(*READ)
def for_candidate(cid):
    drive_id = request.args.get("drive_id")
    ident = current_identity()
    evidence = _candidate_evidence(cid, drive_id, ident.user_id) if drive_id else []
    weights = _model_weights(drive_id, ident.user_id) if drive_id else []
    with _db().session() as s:
        decisions = _svc().for_candidate(s, cid, drive_id=drive_id)
    assessment = _svc().assess(evidence, weights) if evidence else None
    return ok({"decisions": decisions, "assessment": assessment})

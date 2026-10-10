"""HTTP layer for the Evidence Ledger service (append-only).

All under ``/drive/v1/evidence`` so the gateway routes the whole surface with a
single prefix and it never collides with drive-core (`/drive/v1/drives`) or
drive-candidate (`/drive/v1/candidates`).
"""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient

from .schemas import EvidenceIn
from .service import EvidenceService

bp = Blueprint("evidence", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter", "trainer")
READ = ("super_admin", "company_admin", "recruiter", "college_admin", "trainer")

_client = ServiceClient("drive-evidence", default_roles=["recruiter"])


def _svc() -> EvidenceService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


@bp.post("/drive/v1/evidence")
@require_roles(*MANAGE)
def append_evidence():
    try:
        body = EvidenceIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        raise BadRequest("Invalid evidence payload") from e
    ident = current_identity()
    with _db().session() as s:
        res = _svc().append(
            s, drive_id=body.drive_id, candidate_id=body.candidate_id,
            competency_key=body.competency_key, source_type=body.source_type,
            source_ref=body.source_ref, signal=body.signal,
            confidence=body.confidence, rationale=body.rationale,
            round_key=body.round_key, actor_id=ident.user_id,
        )
    # Publish after commit so downstream consumers never see uncommitted rows.
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("evidence.added", {
            "drive_id": body.drive_id, "candidate_id": body.candidate_id,
            "competency_key": body.competency_key, "signal": body.signal,
        })
        for c in res.get("conflicts", []):
            bus.publish("evidence.conflict.opened", c, key=body.candidate_id)
    return created(res)


@bp.get("/drive/v1/evidence/drive/<did>")
@require_roles(*READ)
def drive_ledger(did):
    with _db().session() as s:
        return ok(_svc().drive_ledger(s, did))


@bp.get("/drive/v1/evidence/drive/<did>/conflicts")
@require_roles(*READ)
def drive_conflicts(did):
    with _db().session() as s:
        return ok(_svc().conflicts(s, did))


@bp.post("/drive/v1/evidence/conflicts/<cid>/resolve")
@require_roles(*MANAGE)
def resolve_conflict(cid):
    with _db().session() as s:
        return ok(_svc().resolve_conflict(s, cid))


@bp.post("/drive/v1/evidence/backfill/<did>")
@require_roles(*MANAGE)
def backfill(did):
    ident = current_identity()
    try:
        r = _client.get("drive-core", f"/drive/v1/drives/{did}/rounds/1/scores", user_id=ident.user_id)
        data = (r or {}).get("data") or {}
        # round_scores returns {..., "scores": [ {candidate_id, percentage, ...} ]}
        rows = data.get("scores", []) if isinstance(data, dict) else (data or [])
    except Exception:  # noqa: BLE001 — best effort
        rows = []
    with _db().session() as s:
        res = _svc().backfill(s, did, rows)
    return ok(res)


@bp.get("/drive/v1/evidence/candidate/<cid>")
@require_roles(*READ)
def candidate_ledger(cid):
    drive_id = request.args.get("drive_id")
    with _db().session() as s:
        return ok(_svc().candidate(s, cid, drive_id=drive_id))

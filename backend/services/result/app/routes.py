"""HTTP layer for the Result & Offer Service.

`/verify/offer/<verify_id>` is PUBLIC. Publish + offer generation are high-stakes
(elevated roles; MFA enforced upstream at Auth/Gateway per SRS)."""
from __future__ import annotations

from urllib.error import HTTPError
from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_permission
from lare_common.errors import BadRequest, Forbidden, NotFound, ServiceUnavailable
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient

from .models import Offer
from .schemas import CompileIn, ExportIn, OfferIn, OfferStatusIn
from .service import ResultService

bp = Blueprint("result", __name__)

STAFF = ("drive.drive.manage",)
PUBLISH = ("drive.result.publish",)
_DRIVE = ServiceClient("drive-result")


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


def _svc() -> ResultService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/drive/v1/results/compile")
@require_permission(*STAFF)
def compile_results():
    data = _parse(CompileIn, request.get_json(silent=True))
    _assert_drive_scope(data.drive_id)
    with _db().session() as s:
        return ok(_svc().compile(s, data))


@bp.get("/drive/v1/results/<drive_id>")
@require_permission(*STAFF)
def results(drive_id):
    _assert_drive_scope(drive_id)
    published = request.args.get("published") == "true"
    with _db().session() as s:
        return ok(_svc().results(s, drive_id, published_only=published))


@bp.post("/drive/v1/results/<drive_id>/publish")
@require_permission(*PUBLISH)  # High-stakes publishing is a separate capability.
def publish(drive_id):
    _assert_drive_scope(drive_id)
    with _db().session() as s:
        summary = _svc().publish(s, drive_id)
        published = _svc().results(s, drive_id, published_only=True)
    # Notify each candidate + feed Analytics/Audit.
    bus = current_app.extensions.get("bus")
    if bus:
        for r in published:
            bus.publish("result.published", {
                "drive_id": drive_id, "candidate_id": r["candidate_id"],
                "outcome": r.get("outcome"), "rank": r.get("rank"),
            })
    return ok(summary)


@bp.post("/drive/v1/offers/generate")
@require_permission(*PUBLISH)
def generate_offer():
    data = _parse(OfferIn, request.get_json(silent=True))
    _assert_drive_scope(data.drive_id)
    with _db().session() as s:
        offer = _svc().generate_offer(s, data)
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("offer.created", {
            "drive_id": getattr(data, "drive_id", None), "candidate_id": offer["candidate_id"],
            "kind": offer.get("type"), "role_title": offer.get("role_title"),
            "verify_id": offer.get("verify_id"),
        })
    return created(offer)


@bp.post("/drive/v1/offers/<offer_id>/status")
@require_permission(*PUBLISH)
def offer_status(offer_id):
    data = _parse(OfferStatusIn, request.get_json(silent=True))
    with _db().session() as s:
        offer = s.get(Offer, offer_id)
        if not offer:
            raise NotFound("Offer not found", code="offer_not_found")
        _assert_drive_scope(offer.drive_id)
        return ok(_svc().set_offer_status(s, offer_id, data.status))


@bp.post("/drive/v1/results/<drive_id>/export")
@require_permission("drive.data.export")
def export(drive_id):
    data = _parse(ExportIn, request.get_json(silent=True))  # csv | excel | pdf
    _assert_drive_scope(drive_id)
    with _db().session() as s:
        blob, mime, filename = _svc().export(s, drive_id, data.format)
    return Response(blob, mimetype=mime,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@bp.get("/drive/v1/offers/<offer_id>/letter.pdf")
@require_permission(*PUBLISH)
def offer_letter(offer_id):
    with _db().session() as s:
        offer = s.get(Offer, offer_id)
        if not offer:
            raise NotFound("Offer not found", code="offer_not_found")
        _assert_drive_scope(offer.drive_id)
        blob, filename = _svc().offer_letter_pdf(s, offer_id)
    return Response(blob, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


# ---- PUBLIC offer verification ----
@bp.get("/verify/offer/<verify_id>")
def verify_offer(verify_id):
    with _db().session() as s:
        return ok(_svc().verify_offer(s, verify_id))

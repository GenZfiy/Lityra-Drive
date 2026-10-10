"""HTTP layer for the Result & Offer Service.

`/verify/offer/<verify_id>` is PUBLIC. Publish + offer generation are high-stakes
(elevated roles; MFA enforced upstream at Auth/Gateway per SRS)."""
from __future__ import annotations

from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import CompileIn, ExportIn, OfferIn, OfferStatusIn
from .service import ResultService

bp = Blueprint("result", __name__)

STAFF = ("super_admin", "company_admin", "recruiter")
PUBLISH = ("super_admin", "company_admin")


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
@require_roles(*STAFF)
def compile_results():
    data = _parse(CompileIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().compile(s, data))


@bp.get("/drive/v1/results/<drive_id>")
@require_roles(*STAFF)
def results(drive_id):
    published = request.args.get("published") == "true"
    with _db().session() as s:
        return ok(_svc().results(s, drive_id, published_only=published))


@bp.post("/drive/v1/results/<drive_id>/publish")
@require_roles(*PUBLISH)  # high-stakes: elevated role (MFA enforced at Auth)
def publish(drive_id):
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
@require_roles(*PUBLISH)
def generate_offer():
    data = _parse(OfferIn, request.get_json(silent=True))
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
@require_roles(*STAFF)
def offer_status(offer_id):
    data = _parse(OfferStatusIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().set_offer_status(s, offer_id, data.status))


@bp.post("/drive/v1/results/<drive_id>/export")
@require_roles(*STAFF)
def export(drive_id):
    data = _parse(ExportIn, request.get_json(silent=True))  # csv | excel | pdf
    with _db().session() as s:
        blob, mime, filename = _svc().export(s, drive_id, data.format)
    return Response(blob, mimetype=mime,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@bp.get("/drive/v1/offers/<offer_id>/letter.pdf")
@require_roles(*STAFF)
def offer_letter(offer_id):
    with _db().session() as s:
        blob, filename = _svc().offer_letter_pdf(s, offer_id)
    return Response(blob, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


# ---- PUBLIC offer verification ----
@bp.get("/verify/offer/<verify_id>")
def verify_offer(verify_id):
    with _db().session() as s:
        return ok(_svc().verify_offer(s, verify_id))

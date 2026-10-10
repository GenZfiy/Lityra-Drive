"""HTTP layer for the Notification Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import PreferenceIn, SendIn, TemplateIn
from .service import NotificationService

bp = Blueprint("notification", __name__)

ADMIN = ("super_admin", "company_admin")
# Internal senders: platform services present staff context.
SENDERS = ("super_admin", "company_admin", "trainer", "recruiter")


def _svc() -> NotificationService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/notify/v1/templates")
@require_roles(*ADMIN)
def upsert_template():
    data = _parse(TemplateIn, request.get_json(silent=True))
    with _db().session() as s:
        t = _svc().upsert_template(s, data)
        return created({"key": t.key, "channel": t.channel, "version": t.version})


@bp.get("/notify/v1/templates")
@require_roles(*ADMIN)
def list_templates():
    with _db().session() as s:
        return ok(_svc().list_templates(s))


@bp.get("/notify/v1/templates/variables")
@require_roles(*ADMIN)
def template_variables():
    return ok(_svc().variables_catalog())


@bp.post("/notify/v1/templates/preview")
@require_roles(*ADMIN)
def preview_template():
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().preview_template(
            s, body.get("key", ""), body.get("channel", "email"),
            body.get("variables") or {}))


@bp.post("/notify/v1/send")
@require_roles(*SENDERS)
def send():
    data = _parse(SendIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().send(s, data))


@bp.get("/notify/v1/inbox")
def inbox():
    ident = current_identity()
    unread = request.args.get("unread") == "true"
    with _db().session() as s:
        return ok(_svc().inbox(s, ident.user_id, unread_only=unread))


@bp.post("/notify/v1/inbox/<nid>/read")
def mark_read(nid):
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().mark_read(s, ident.user_id, nid))


@bp.get("/notify/v1/preferences")
def get_preferences():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().preferences(s, ident.user_id))


@bp.put("/notify/v1/preferences")
def set_preference():
    ident = current_identity()
    data = _parse(PreferenceIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().set_preference(s, ident.user_id, data.channel, data.enabled))

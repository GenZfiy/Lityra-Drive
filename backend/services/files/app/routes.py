"""HTTP layer for the File & Storage Service.

Upload/download endpoints are authenticated by the signed token itself (the
pre-signed URL model), so they don't require a platform JWT."""
from __future__ import annotations

from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import UploadUrlIn
from .service import FilesService

bp = Blueprint("files", __name__)


def _svc() -> FilesService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/files/v1/upload-url")
def upload_url():
    ident = current_identity()
    data = _parse(UploadUrlIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().create_upload_url(s, ident.user_id, data))


# Token-authenticated (pre-signed) — no platform JWT required.
@bp.put("/files/v1/upload/<token>")
def upload(token):
    with _db().session() as s:
        return ok(_svc().store_upload(s, token, request.get_data()))


@bp.post("/files/v1/<file_id>/complete")
def complete(file_id):
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().complete(s, ident.user_id, file_id))


@bp.get("/files/v1/<file_id>/download-url")
def download_url(file_id):
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().create_download_url(s, ident.roles, ident.user_id, file_id))


# Token-authenticated (pre-signed) — no platform JWT required.
@bp.get("/files/v1/download/<token>")
def download(token):
    with _db().session() as s:
        data, mime, filename = _svc().read_download(s, token)
    headers = {}
    if filename:
        headers["Content-Disposition"] = f"attachment; filename={filename}"
    return Response(data, mimetype=mime, headers=headers)


@bp.get("/files/v1/<file_id>/meta")
def meta(file_id):
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().meta(s, ident.roles, ident.user_id, file_id))


@bp.delete("/files/v1/<file_id>")
def delete(file_id):
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().delete(s, ident.user_id, file_id))

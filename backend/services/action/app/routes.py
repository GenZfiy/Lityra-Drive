"""HTTP layer for the Action (attention) service.

GET recomputes from live cross-service state (best-effort east-west to evidence
+ decision) so the queue is always current; resolution is persisted user state.
"""
from __future__ import annotations

import json
import time

from flask import Blueprint, Response, current_app, request, stream_with_context

from lare_common.auth_context import current_identity, require_roles
from lare_common.responses import ok
from lare_common.service_client import ServiceClient

from .service import ActionService

bp = Blueprint("action", __name__)

MANAGE = ("super_admin", "company_admin", "recruiter")
READ = ("super_admin", "company_admin", "recruiter", "college_admin", "trainer")

_client = ServiceClient("drive-action", default_roles=["recruiter"])


def _svc() -> ActionService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _conflicts(drive_id, uid):
    try:
        r = _client.get("drive-evidence", f"/drive/v1/evidence/drive/{drive_id}/conflicts", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


def _queue(drive_id, uid):
    try:
        r = _client.get("drive-decision", f"/drive/v1/decisions/drive/{drive_id}/queue", user_id=uid)
        return (r or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return []


@bp.get("/drive/v1/actions/drive/<did>")
@require_roles(*READ)
def list_actions(did):
    ident = current_identity()
    conflicts = _conflicts(did, ident.user_id)
    queue = _queue(did, ident.user_id)
    try:
        with _db().session() as s:
            return ok(_svc().recompute(s, did, conflicts, queue))
    except Exception:  # noqa: BLE001 — degrade to empty rather than 500 the surface
        return ok([])


@bp.get("/drive/v1/actions/drive/<did>/stream")
@require_roles(*READ)
def stream(did):
    """Server-Sent-Events push of the live attention queue. Bounded to ~60s per
    connection (the client reconnects) so a streaming request never pins a worker
    indefinitely — the deliberate trade-off vs. a persistent socket."""
    ident = current_identity()
    uid = ident.user_id
    db, svc = _db(), _svc()

    def gen():
        last = None
        for _ in range(5):  # ~60s window (5 × 12s)
            try:
                conflicts = _conflicts(did, uid)
                queue = _queue(did, uid)
                with db.session() as s:
                    actions = svc.recompute(s, did, conflicts, queue)
                payload = json.dumps(actions)
            except Exception:  # noqa: BLE001 — never let the stream 500; emit empty
                payload = "[]"
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            else:
                yield ": heartbeat\n\n"
            time.sleep(12)

    # NB: do NOT set a "Connection" header — it's a hop-by-hop header that WSGI
    # servers (waitress/gunicorn) reject with an AssertionError (PEP 3333).
    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.post("/drive/v1/actions/<aid>/resolve")
@require_roles(*MANAGE)
def resolve(aid):
    ident = current_identity()
    status = (request.get_json(silent=True) or {}).get("status", "resolved")
    if status not in ("resolved", "dismissed"):
        status = "resolved"
    with _db().session() as s:
        return ok(_svc().resolve(s, aid, ident.user_id, status=status))

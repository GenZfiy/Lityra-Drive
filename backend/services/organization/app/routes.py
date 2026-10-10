"""HTTP layer for the Organization Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient

from .schemas import OrgIn, OrgUpdate
from .service import OrgService

bp = Blueprint("organization", __name__)

SUPER = ("super_admin",)
ADMIN = ("super_admin", "company_admin")


_SEARCH = ServiceClient("platform-org", timeout=4)
# service name -> search path (each returns [{type,id,title,subtitle,status}])
_SEARCH_TARGETS = {
    "drive-core": "/drive/v1/search",
    "drive-candidate": "/drive/v1/candidates/search",
    "drive-questionbank": "/drive/v1/questions/search",
}


def _svc() -> OrgService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.post("/org/v1/organizations")
@require_roles(*SUPER)
def create():
    data = _parse(OrgIn, request.get_json(silent=True))
    with _db().session() as s:
        return created(_svc().out(_svc().create(s, data)))


@bp.get("/org/v1/organizations")
@require_roles(*ADMIN)
def list_orgs():
    with _db().session() as s:
        return ok(_svc().list(s))


@bp.get("/org/v1/organizations/<org_id>")
@require_roles(*ADMIN)
def get_org(org_id):
    with _db().session() as s:
        return ok(_svc().out(_svc().get(s, org_id)))


@bp.put("/org/v1/organizations/<org_id>")
@require_roles(*ADMIN)
def update_org(org_id):
    data = _parse(OrgUpdate, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().out(_svc().update(s, org_id, data)))


@bp.delete("/org/v1/organizations/<org_id>")
@require_roles(*SUPER)
def delete_org(org_id):
    with _db().session() as s:
        return ok(_svc().soft_delete(s, org_id))


# Public: resolve tenant branding by custom domain (drives white-label login).
@bp.get("/org/v1/resolve")
def resolve():
    domain = request.args.get("domain", "")
    if not domain:
        raise BadRequest("domain is required", code="domain_required")
    with _db().session() as s:
        o = _svc().by_domain(s, domain)
        return ok({"tenant_id": o.tenant_id, "name": o.name, "slug": o.slug,
                   "branding": o.branding, "timezone": o.timezone})


# Global search (req #27): fan out to per-service search, merge, degrade
# gracefully (a down service just contributes nothing).
@bp.get("/org/v1/search")
def global_search():
    ident = current_identity()
    q = request.args.get("q", "").strip()
    if not q:
        return ok({"query": "", "results": []})
    import urllib.parse
    qs = urllib.parse.quote(q)
    results, sources = [], {}
    for svc, path in _SEARCH_TARGETS.items():
        try:
            resp = _SEARCH.get(svc, f"{path}?q={qs}", roles=ident.roles, user_id=ident.user_id)
            hits = (resp or {}).get("data") or []
            results.extend(hits)
            sources[svc] = len(hits)
        except Exception:  # noqa: BLE001 — partial results are fine
            sources[svc] = "unavailable"
    return ok({"query": q, "count": len(results), "sources": sources, "results": results})


# The caller's own org config (for the authenticated tenant).
@bp.get("/org/v1/me")
def my_org():
    ident = current_identity()
    with _db().session() as s:
        o = _svc().by_tenant(s, ident.tenant_id)
        return ok(_svc().out(o) if o else None)

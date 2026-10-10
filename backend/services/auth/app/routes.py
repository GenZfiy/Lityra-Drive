"""HTTP layer for the Auth Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError
from sqlalchemy import select

from lare_common.auth_context import current_identity, require_permission, require_roles
from lare_common.errors import BadRequest, NotFound, Unauthorized
from lare_common.internal import verify_service_token
from lare_common.responses import created, ok

from .models import User
from .schemas import (
    AdminUserCreateIn, AssignRoleIn, EmailVerifyIn, LoginIn, OtpRequestIn,
    OtpVerifyIn, PasswordForgotIn, PasswordResetIn, RefreshIn, RegisterIn,
    RoleCloneIn, RoleCreateIn, RoleUpdateIn,
)
from .service import AuthService

bp = Blueprint("auth", __name__)


def _svc() -> AuthService:
    return current_app.extensions["auth_service"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        data = model.model_validate(payload or {})
        allowed_product = getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined")
        requested_product = getattr(data, "product", None)
        if allowed_product in ("learn", "hire") and requested_product and requested_product != allowed_product:
            raise BadRequest("This authentication service is for another product", code="wrong_product")
        return data
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


def _require_product_user(session, user_id):
    allowed_product = getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined")
    user = session.get(User, user_id)
    if not user or (allowed_product in ("learn", "hire") and user.product != allowed_product):
        raise NotFound("User not found", code="user_not_found")


# Public JWKS for RS256 verification (prod). Empty key set under dev HS256.
@bp.get("/.well-known/jwks.json")
def jwks():
    from lare_common.security import public_jwks
    cfg = current_app.config["LARE"]
    keys = public_jwks(cfg.JWT_PUBLIC_KEY) if cfg.JWT_ALG.startswith("RS") else {"keys": []}
    from flask import jsonify
    return jsonify(keys)


@bp.post("/register")
def register():
    data = _parse(RegisterIn, request.get_json(silent=True))
    with _db().session() as s:
        user = _svc().register(s, data.email, data.password, data.full_name, data.product)
        # Self-registration on a campus platform defaults to the student role.
        _svc().assign_role(s, user.id, "student", None)
        # Issue an email-verification token (delivered via Notification in prod).
        verify_token = _svc().request_email_verification(s, user.id)
        s.flush()
        out = _svc().user_out(s, user)
    _deliver("email_verify", data.email, verify_token)
    resp = {**out}
    if current_app.config["LARE"].DEBUG:
        resp["dev_email_verify_token"] = verify_token
    return created(resp)


def _audit(action: str, entity_type: str, entity_id: str | None, **meta) -> None:
    """Emit an administrative action to the bus; the audit service appends it to
    the tamper-evident log, attributed to the acting admin. Never blocks the
    request — a missing bus (e.g. in tests) is a silent no-op."""
    try:
        bus = current_app.extensions.get("bus")
        if not bus:
            return
        actor = current_identity().user_id
        bus.publish(action, {
            "actor_id": actor, "actor_type": "user",
            "entity_type": entity_type, "entity_id": entity_id, **meta,
        })
    except Exception:  # noqa: BLE001
        pass


def _deliver(purpose: str, to: str, secret: str) -> None:
    """Best-effort out-of-band delivery of a secret via the Notification service.
    Never blocks auth; in dev the token is also returned in the response."""
    try:
        from lare_common.service_client import ServiceClient
        # /notify/v1/send is guarded by require_roles(SENDERS); present a sender
        # role so this platform-initiated security email isn't rejected (403).
        ServiceClient("auth").post("lare-notify", "/notify/v1/send", {
            "user_id": to, "template_key": purpose, "channel": "email",
            "variables": {"email": to, "code": secret, "token": secret},
        }, roles=["super_admin"])
    except Exception:  # noqa: BLE001
        pass


# ---- OTP (passwordless / step-up) ----
@bp.post("/internal/drive-user")
def provision_drive_user():
    # Internal-only: create a passwordless Hire identity, but do not issue a
    # session. Public registration must first verify control of the email by OTP.
    try:
        verify_service_token(request.headers.get("X-Internal-Token", ""))
    except Exception as e:  # noqa: BLE001
        raise Unauthorized("invalid internal token") from e
    if getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined") == "learn":
        raise Unauthorized("Hire identity provisioning is unavailable in Learn")
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    if not email:
        raise BadRequest("email required", code="email_required")
    with _db().session() as s:
        return ok(_svc().provision_drive_user(s, email, body.get("full_name")))


@bp.post("/otp/request")
def otp_request():
    data = _parse(OtpRequestIn, request.get_json(silent=True))
    with _db().session() as s:
        code = _svc().request_otp(s, data.email, data.product)
    if code:
        _deliver("otp", data.email, code)
    resp = {"sent": True}  # uniform response (no user enumeration)
    if code and current_app.config["LARE"].DEBUG:
        resp["dev_code"] = code
    return ok(resp)


@bp.post("/otp/verify")
def otp_verify():
    data = _parse(OtpVerifyIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().verify_otp(s, data.email, data.code, data.device, data.product))


# ---- password reset ----
@bp.post("/password/forgot")
def password_forgot():
    data = _parse(PasswordForgotIn, request.get_json(silent=True))
    with _db().session() as s:
        token = _svc().request_password_reset(s, data.email, data.product)
    if token:
        _deliver("password_reset", data.email, token)
    resp = {"sent": True}
    if token and current_app.config["LARE"].DEBUG:
        resp["dev_reset_token"] = token
    return ok(resp)


@bp.post("/password/reset")
def password_reset():
    data = _parse(PasswordResetIn, request.get_json(silent=True))
    with _db().session() as s:
        _svc().reset_password(s, data.token, data.new_password,
                              getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined"))
    return ok({"reset": True})


# ---- email verification ----
@bp.post("/email/verify/request")
def email_verify_request():
    ident = current_identity()
    with _db().session() as s:
        token = _svc().request_email_verification(s, ident.user_id)
    resp = {"sent": True}
    if current_app.config["LARE"].DEBUG:
        resp["dev_email_verify_token"] = token
    return ok(resp)


@bp.post("/email/confirm")
def email_confirm():
    data = _parse(EmailVerifyIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().verify_email(s, data.token,
                                      getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined")))


@bp.post("/login")
def login():
    data = _parse(LoginIn, request.get_json(silent=True))
    with _db().session() as s:
        tokens = _svc().login(s, data.email, data.password, data.device, data.product)
    return ok(tokens)


@bp.post("/refresh")
def refresh():
    data = _parse(RefreshIn, request.get_json(silent=True))
    with _db().session() as s:
        tokens = _svc().refresh(s, data.refresh_token,
                                getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined"))
    return ok(tokens)


@bp.post("/logout")
def logout():
    data = _parse(RefreshIn, request.get_json(silent=True))
    with _db().session() as s:
        _svc().logout(s, data.refresh_token,
                      getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined"))
    return ok({"logged_out": True})


@bp.get("/flags")
def flags():
    # Feature flags (req #30) for the caller's tenant — drives conditional UI.
    from lare_common.platform import all_flags
    ident = current_identity()
    return ok(all_flags(ident.tenant_id))


@bp.get("/me")
def me():
    ident = current_identity()
    with _db().session() as s:
        user = s.get(User, ident.user_id)
        if not user:
            raise NotFound("User not found", code="user_not_found")
        # Include effective permissions + scope so the SPA can drive conditional
        # UI (which is cosmetic — the backend still enforces every action).
        return ok(_svc().user_out(s, user, with_permissions=True))


# ---- RBAC administration (granular-permission gated) ----
@bp.post("/roles/assign")
@require_permission("auth.role.assign")
def assign_role():
    data = _parse(AssignRoleIn, request.get_json(silent=True))
    with _db().session() as s:
        _require_product_user(s, data.user_id)
        _svc().assign_role(s, data.user_id, data.role, data.college_id,
                           data.branch_id, data.cohort_id)
    _audit("admin.role.assigned", "user", data.user_id, role=data.role,
           college_id=data.college_id, branch_id=data.branch_id, cohort_id=data.cohort_id)
    return ok({"assigned": True})


@bp.post("/roles/unassign")
@require_permission("auth.role.assign")
def unassign_role():
    data = _parse(AssignRoleIn, request.get_json(silent=True))
    with _db().session() as s:
        _require_product_user(s, data.user_id)
        _svc().remove_role(s, data.user_id, data.role, data.college_id)
    _audit("admin.role.unassigned", "user", data.user_id, role=data.role,
           college_id=data.college_id)
    return ok({"unassigned": True})


@bp.get("/permissions")
@require_permission("auth.role.manage", "auth.role.assign")
def list_permissions():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().list_permissions(s, product=ident.product))


@bp.get("/roles")
@require_permission("auth.role.manage", "auth.role.assign")
def list_roles():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().list_roles(s, product=ident.product))


@bp.post("/roles")
@require_permission("auth.role.manage")
def create_role():
    data = _parse(RoleCreateIn, request.get_json(silent=True))
    ident = current_identity()
    with _db().session() as s:
        out = _svc().create_role(s, data.name, data.description,
                                 data.scope_level, data.permissions,
                                 product=ident.product)
    _audit("admin.role.created", "role", out.get("id"), name=out.get("name"),
           scope_level=out.get("scope_level"), permissions=out.get("permissions"))
    return created(out)


@bp.post("/roles/<role_id>/clone")
@require_permission("auth.role.manage")
def clone_role(role_id):
    data = _parse(RoleCloneIn, request.get_json(silent=True))
    ident = current_identity()
    with _db().session() as s:
        out = _svc().clone_role(s, role_id, data.name, data.description,
                                product=ident.product)
    _audit("admin.role.cloned", "role", out.get("id"), name=out.get("name"),
           source_role_id=role_id)
    return created(out)


@bp.patch("/roles/<role_id>")
@require_permission("auth.role.manage")
def update_role(role_id):
    data = _parse(RoleUpdateIn, request.get_json(silent=True))
    ident = current_identity()
    with _db().session() as s:
        out = _svc().update_role(
            s, role_id, description=data.description, scope_level=data.scope_level,
            is_active=data.is_active, permission_codes=data.permissions,
            product=ident.product)
    _audit("admin.role.updated", "role", role_id, name=out.get("name"),
           scope_level=out.get("scope_level"), is_active=out.get("is_active"),
           permissions=out.get("permissions"))
    return ok(out)


@bp.delete("/roles/<role_id>")
@require_permission("auth.role.manage")
def delete_role(role_id):
    ident = current_identity()
    with _db().session() as s:
        _svc().delete_role(s, role_id, product=ident.product)
    _audit("admin.role.deleted", "role", role_id)
    return ok({"deleted": True})


@bp.get("/users")
@require_roles("super_admin", "company_admin", "college_admin", "recruiter")
def list_users():
    # `ids=a,b,c` resolves a specific set (used by Drive to label candidates by
    # name/email instead of raw UUIDs); otherwise lists up to `limit`.
    ids = [i for i in (request.args.get("ids", "").split(",")) if i]
    limit = min(int(request.args.get("limit", 50)), 200)
    with _db().session() as s:
        stmt = select(User)
        allowed_product = getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined")
        if allowed_product in ("learn", "hire"):
            stmt = stmt.where(User.product == allowed_product)
        stmt = stmt.where(User.id.in_(ids)) if ids else stmt.limit(limit)
        rows = s.execute(stmt).scalars().all()
        return ok([_svc().user_out(s, u) for u in rows], meta={"count": len(rows)})


# ---- User administration (Super Admin portal) ----
@bp.post("/admin/users")
@require_permission("auth.user.manage")
def admin_create_user():
    data = _parse(AdminUserCreateIn, request.get_json(silent=True))
    with _db().session() as s:
        user = _svc().register(s, data.email, data.password, data.full_name, data.product)
        if data.role:
            _svc().assign_role(s, user.id, data.role, data.college_id,
                               data.branch_id, data.cohort_id)
        s.flush()
        out = _svc().admin_user_out(s, user)
    _audit("admin.user.created", "user", out.get("id"), email=data.email,
           product=data.product, role=data.role)
    return created(out)


@bp.get("/admin/users")
@require_permission("auth.user.manage", "auth.user.view")
def admin_list_users():
    q = request.args.get("q") or None
    status = request.args.get("status") or None
    product = getattr(current_app.config["LARE"], "AUTH_ALLOWED_PRODUCT", "combined")
    if product not in ("learn", "hire"):
        product = request.args.get("product") or None
    limit = min(int(request.args.get("limit", 100)), 500)
    with _db().session() as s:
        rows = _svc().list_admin_users(s, q, status, product, limit)
        return ok([_svc().admin_user_out(s, u) for u in rows], meta={"count": len(rows)})


@bp.get("/admin/users/<uid>")
@require_permission("auth.user.manage", "auth.user.view")
def admin_get_user(uid):
    with _db().session() as s:
        u = s.get(User, uid)
        if not u:
            raise NotFound("User not found", code="user_not_found")
        _require_product_user(s, uid)
        return ok(_svc().admin_user_out(s, u))


@bp.post("/admin/users/<uid>/status")
@require_permission("auth.user.manage")
def admin_set_status(uid):
    status = (request.get_json(silent=True) or {}).get("status", "")
    ident = current_identity()
    with _db().session() as s:
        _require_product_user(s, uid)
        u = _svc().set_user_status(s, uid, status, actor_id=ident.user_id)
        s.flush()
        out = _svc().admin_user_out(s, u)
    _audit("admin.user.status_changed", "user", uid, status=status, email=out.get("email"))
    return ok(out)

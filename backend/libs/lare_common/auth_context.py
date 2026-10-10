"""Request authentication context + RBAC guard usable by every service.

Two supported modes:
  1. Behind the API Gateway: the Gateway verifies the JWT and injects trusted
     headers (X-User-Id, X-Roles, X-Tenant-Id, X-College-Ids). Services trust
     these on the private network.
  2. Direct (dev / service without gateway): decode the Bearer JWT locally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps

from flask import current_app, g, request

from .errors import Forbidden, Unauthorized
from .security import decode_token


@dataclass
class Identity:
    user_id: str
    roles: list[str] = field(default_factory=list)
    tenant_id: str = "lare"
    college_ids: list[str] = field(default_factory=list)
    # Effective permission codes, resolved from the user's roles at login and
    # carried in the token / X-Permissions header. RBAC is enforced on THESE,
    # not on role names — a custom role with the right permission works too.
    permissions: list[str] = field(default_factory=list)
    # Data-visibility ceiling: platform > college > branch > section > self.
    scope_level: str = "self"
    # Concrete hierarchy slices the scope is exercised over.
    branch_ids: list[str] = field(default_factory=list)
    cohort_ids: list[str] = field(default_factory=list)
    product: str | None = None

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def scope(self) -> "Scope":
        # super_admin sees everything regardless of bindings.
        level = "platform" if "super_admin" in self.roles else self.scope_level
        return Scope(level=level, user_id=self.user_id,
                     college_ids=self.college_ids, branch_ids=self.branch_ids,
                     cohort_ids=self.cohort_ids)

    def has_permission(self, *codes: str) -> bool:
        # super_admin is the platform owner — it holds every permission implicitly
        # so a newly-added permission code is never accidentally locked away.
        if "super_admin" in self.roles:
            return True
        perms = set(self.permissions)
        return any(c in perms for c in codes)


# Ordered widest → narrowest; used to compare a role's reach against a required
# scope. A holder at a wider tier satisfies a requirement for a narrower one.
_SCOPE_ORDER = ["platform", "college", "branch", "section", "self"]


def scope_rank(level: str) -> int:
    try:
        return _SCOPE_ORDER.index(level)
    except ValueError:
        return len(_SCOPE_ORDER)  # unknown = narrowest


@dataclass
class Scope:
    """A user's data-visibility window, applied to any read query so callers
    only ever see rows inside their slice of the institution hierarchy.

    Usage (in a service that owns a table with the relevant columns):

        stmt = select(Learner)
        stmt = identity.scope.apply(stmt,
                    college_col=Learner.college_id,
                    branch_col=Learner.branch_id,
                    cohort_col=Learner.cohort_id,
                    user_col=Learner.user_id)

    Enforcement is at the query layer, per the spec — the frontend never decides
    what a user can see.
    """
    level: str
    user_id: str
    college_ids: list[str] = field(default_factory=list)
    branch_ids: list[str] = field(default_factory=list)
    cohort_ids: list[str] = field(default_factory=list)

    @property
    def unrestricted(self) -> bool:
        return self.level == "platform"

    def allows_college(self, college_id: str | None) -> bool:
        if self.unrestricted:
            return True
        return bool(college_id) and college_id in self.college_ids

    def can_see(self, *, college_id=None, branch_id=None,
                cohort_id=None, user_id=None) -> bool:
        """Single-record check mirroring `apply` — use it to authorise a fetch
        by id before returning the row."""
        if self.level == "platform":
            return True
        if self.level == "self":
            return bool(user_id) and user_id == self.user_id
        if self.level == "college":
            return bool(college_id) and college_id in self.college_ids
        if self.level == "branch":
            return bool(branch_id) and branch_id in self.branch_ids
        if self.level == "section":
            return bool(cohort_id) and cohort_id in self.cohort_ids
        return False

    def apply(self, query, *, college_col=None, branch_col=None,
              cohort_col=None, user_col=None):
        """Return `query` narrowed to this scope. Platform scope is unrestricted;
        every narrower level filters on the column matching its granularity,
        degrading to college only (never wider) when that column is absent."""
        if self.level == "platform":
            return query

        if self.level == "self":
            col = user_col if user_col is not None else college_col
            if col is user_col and user_col is not None:
                return query.where(user_col == self.user_id)
            # No per-user column to filter on → expose nothing.
            return self._deny(query, college_col, branch_col, cohort_col)

        by_level = {
            "college": (college_col, self.college_ids),
            "branch": (branch_col, self.branch_ids),
            "section": (cohort_col, self.cohort_ids),
        }
        col, ids = by_level.get(self.level, (None, None))
        if col is not None:
            return query.where(col.in_(ids or []))
        # Column for the user's granularity isn't on this table. Degrade to
        # college (still within their reach); if not even that, deny.
        if college_col is not None:
            return query.where(college_col.in_(self.college_ids or []))
        return self._deny(query, branch_col, cohort_col)

    @staticmethod
    def _deny(query, *cols):
        for c in cols:
            if c is not None:
                return query.where(c.in_([]))  # empty IN → no rows
        return query.where(False)


def _from_headers() -> Identity | None:
    uid = request.headers.get("X-User-Id")
    if not uid:
        return None
    roles = [r for r in (request.headers.get("X-Roles", "").split(",")) if r]
    colleges = [c for c in (request.headers.get("X-College-Ids", "").split(",")) if c]
    perms = [p for p in (request.headers.get("X-Permissions", "").split(",")) if p]
    branches = [b for b in (request.headers.get("X-Branch-Ids", "").split(",")) if b]
    cohorts = [c for c in (request.headers.get("X-Cohort-Ids", "").split(",")) if c]
    return Identity(
        user_id=uid,
        roles=roles,
        tenant_id=request.headers.get("X-Tenant-Id", "lare"),
        college_ids=colleges,
        permissions=perms,
        scope_level=request.headers.get("X-Scope-Level", "self"),
        branch_ids=branches,
        cohort_ids=cohorts,
        product=request.headers.get("X-Product") or None,
    )


def _from_bearer() -> Identity | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    cfg = current_app.config["LARE"]
    try:
        claims = decode_token(
            auth[7:],
            alg=cfg.JWT_ALG,
            verify_key=cfg.verify_key,
            issuer=cfg.JWT_ISSUER,
            audience=cfg.JWT_AUDIENCE,
        )
    except Exception as exc:  # noqa: BLE001
        raise Unauthorized("Invalid or expired token") from exc
    if claims.get("type") != "access":
        raise Unauthorized("Not an access token")
    return Identity(
        user_id=claims["sub"],
        roles=claims.get("roles", []),
        tenant_id=claims.get("tenant_id", "lare"),
        college_ids=claims.get("college_ids", []),
        permissions=claims.get("permissions", []),
        scope_level=claims.get("scope_level", "self"),
        branch_ids=claims.get("branch_ids", []),
        cohort_ids=claims.get("cohort_ids", []),
        product=claims.get("product"),
    )


def current_identity() -> Identity:
    ident = _from_headers() or _from_bearer()
    if ident is None:
        raise Unauthorized("Authentication required")
    g.identity = ident
    return ident


def current_scope() -> "Scope":
    """The caller's data-visibility window. Apply it to read queries."""
    return current_identity().scope


def manageable_branch_scopes(session, identity: "Identity | None" = None):
    """Which module/content audiences (branch_scope values) a user may ASSIGN.

    Returns ``None`` when unrestricted — platform-level operators (super_admin /
    company_admin) can target any branch, the grouped categories, or "all".
    Otherwise a set of the exact branch codes the user is bound to: faculty get
    their assigned branch(es); college-scoped roles (principal / dean / tpo /
    college_admin) get every branch of their college. Reads institution.branches
    (one DB, LMS-internal); guarded so a dev/sqlite DB simply yields an empty set.
    """
    from sqlalchemy import text
    ident = identity or current_identity()
    if ident.scope.level == "platform":
        return None
    try:
        if ident.branch_ids:
            rows = session.execute(text(
                "SELECT code FROM institution.branches WHERE id = ANY(:ids)"),
                {"ids": list(ident.branch_ids)}).all()
        elif ident.college_ids:
            rows = session.execute(text(
                "SELECT code FROM institution.branches WHERE college_id = ANY(:ids)"),
                {"ids": list(ident.college_ids)}).all()
        else:
            rows = []
        return {r[0] for r in rows}
    except Exception:  # noqa: BLE001 — institution schema unavailable (dev/sqlite)
        return set()


def require_branch_scope(session, branch_scope: str, identity: "Identity | None" = None) -> None:
    """Raise Forbidden if the caller may not author for this audience."""
    allowed = manageable_branch_scopes(session, identity)
    if allowed is not None and branch_scope not in allowed:
        raise Forbidden("You can only author content for your assigned branches")


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_identity()
        return fn(*args, **kwargs)
    return wrapper


def require_roles(*roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ident = current_identity()
            if not ident.has_role(*roles):
                raise Forbidden("Insufficient role")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(*codes: str):
    """Gate an endpoint on granular permission codes (ANY of the given codes).

    This is the primary RBAC guard — enforce on permissions, not role names, so
    custom roles and re-permissioned built-ins work without code changes. The
    spec is explicit: every API and service must enforce here; frontend hiding
    is never sufficient.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ident = current_identity()
            if not ident.has_permission(*codes):
                raise Forbidden("Missing required permission")
            return fn(*args, **kwargs)
        return wrapper
    return decorator

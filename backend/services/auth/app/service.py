"""Auth business logic: registration, login, token issue/rotation, RBAC.

Implements refresh-token rotation with reuse detection (AU-2): each refresh
issues a new token in the same family and revokes the old one; presenting an
already-rotated (revoked) token revokes the whole family.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import (
    BadRequest, Conflict, Forbidden, NotFound, TooManyRequests, Unauthorized,
)
from lare_common.security import (
    create_access_token, hash_password, hash_token, new_id, random_token,
    verify_password,
)

import secrets

from .config import AuthConfig
from .models import (
    Permission, RefreshToken, Role, User, UserRole, VerificationToken,
    role_permissions,
)


def _permission_product(code: str) -> str | None:
    """Map product-specific permission namespaces; shared platform grants return None."""
    if code.startswith("drive."):
        return "hire"
    if code.startswith(("institution.", "academic.", "lms.", "training.")):
        return "learn"
    return None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AuthService:
    def __init__(self, cfg: AuthConfig):
        self.cfg = cfg

    # ---------- helpers ----------
    _SCOPE_ORDER = ["platform", "college", "branch", "section", "self"]

    def _product(self) -> str | None:
        product = getattr(self.cfg, "AUTH_ALLOWED_PRODUCT", "combined")
        return product if product in ("learn", "hire") else None

    def _role_names(self, s: Session, user: User) -> list[str]:
        rows = s.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id, Role.product == user.product)
        ).scalars().all()
        return sorted(set(rows))

    def _effective(self, s: Session, user: User) -> tuple[list[str], str]:
        """Union of permission codes across the user's ACTIVE roles, plus the
        widest scope_level any of those roles grants. This is what the token
        carries so every service can enforce RBAC without a DB lookup."""
        roles = s.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id, Role.product == user.product,
                   Role.is_active.is_(True))
        ).scalars().all()
        if not roles:
            return [], "self"
        role_ids = [r.id for r in roles]
        codes = s.execute(
            select(Permission.code)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .where(role_permissions.c.role_id.in_(role_ids))
        ).scalars().all()
        widest = min((r.scope_level for r in roles),
                     key=lambda lv: self._SCOPE_ORDER.index(lv)
                     if lv in self._SCOPE_ORDER else len(self._SCOPE_ORDER))
        return sorted(set(codes)), widest

    def _college_ids(self, s: Session, user: User) -> list[str]:
        rows = s.execute(
            select(UserRole.college_id).where(
                UserRole.user_id == user.id, UserRole.college_id.is_not(None)
            )
        ).scalars().all()
        return sorted({r for r in rows if r})

    def _scope_bindings(self, s: Session, user: User) -> tuple[list[str], list[str], list[str]]:
        """The concrete hierarchy slices this user's role grants are pinned to:
        (college_ids, branch_ids, cohort_ids). Empty college_ids for a
        platform-scoped user means "all colleges" — the scope helper treats an
        empty binding set at platform level as unrestricted."""
        rows = s.execute(
            select(UserRole.college_id, UserRole.branch_id, UserRole.cohort_id)
            .where(UserRole.user_id == user.id)
        ).all()
        colleges = sorted({r[0] for r in rows if r[0]})
        branches = sorted({r[1] for r in rows if r[1]})
        cohorts = sorted({r[2] for r in rows if r[2]})
        return colleges, branches, cohorts

    def _issue_tokens(self, s: Session, user: User, device: str | None,
                      family_id: str | None = None) -> dict:
        roles = self._role_names(s, user)
        permissions, scope_level = self._effective(s, user)
        colleges, branches, cohorts = self._scope_bindings(s, user)
        access = create_access_token(
            subject=user.id,
            roles=roles,
            tenant_id=user.tenant_id,
            college_ids=colleges,
            permissions=permissions,
            scope_level=scope_level,
            branch_ids=branches,
            cohort_ids=cohorts,
            alg=self.cfg.JWT_ALG,
            signing_key=self.cfg.signing_key,
            issuer=self.cfg.JWT_ISSUER,
            audience=self.cfg.JWT_AUDIENCE,
            ttl_minutes=self.cfg.ACCESS_TOKEN_TTL_MIN,
            # Product scope — the Gateway uses this to keep a Learn session out of
            # Hire and vice versa. The two products are separate accounts.
            extra={"product": getattr(user, "product", "learn")},
        )
        raw_refresh = random_token()
        rt = RefreshToken(
            id=new_id(),
            user_id=user.id,
            family_id=family_id or new_id(),
            token_hash=hash_token(raw_refresh),
            device=device,
            expires_at=_utcnow() + timedelta(days=self.cfg.REFRESH_TOKEN_TTL_DAYS),
        )
        s.add(rt)
        return {
            "access_token": access,
            "refresh_token": raw_refresh,
            "expires_in": self.cfg.ACCESS_TOKEN_TTL_MIN * 60,
        }

    # ---------- use cases ----------
    def register(self, s: Session, email: str, password: str,
                 full_name: str | None, product: str = "learn") -> User:
        # Accounts are per-product: the same email may register once for Learn and
        # once for Hire, each with its own password. Uniqueness is (email, product).
        exists = s.execute(
            select(User).where(User.email == email.lower(), User.product == product)
        ).scalar_one_or_none()
        if exists:
            raise Conflict("Email already registered", code="email_taken")
        user = User(
            id=new_id(),
            email=email.lower(),
            product=product,
            password_hash=hash_password(password, rounds=self.cfg.BCRYPT_ROUNDS),
            full_name=full_name,
            tenant_id=self.cfg.DEFAULT_TENANT_ID,
        )
        s.add(user)
        s.flush()
        return user

    def provision_drive_user(self, s: Session, email: str, full_name: str | None) -> dict:
        """Create a passwordless Hire identity without issuing a session.

        The public candidate registration flow must prove email ownership with an
        OTP before it can obtain access tokens. Existing accounts are never
        returned to a public registration caller.
        """
        email = email.lower().strip()
        # Campus Drive registration is a Lityra Hire account.
        user = s.execute(
            select(User).where(User.email == email, User.product == "hire")
        ).scalar_one_or_none()
        if user is not None:
            raise Conflict("A Lityra Hire account already exists for this email",
                           code="account_exists")
        user = User(
            id=new_id(), email=email, product="hire",
            password_hash=hash_password(secrets.token_urlsafe(24),
                                        rounds=self.cfg.BCRYPT_ROUNDS),
            full_name=full_name, tenant_id=self.cfg.DEFAULT_TENANT_ID,
            email_verified=False, status="active",
        )
        s.add(user)
        s.flush()
        self.assign_role(s, user.id, "student", None)
        s.flush()
        return {"user_id": user.id, "email": user.email,
                "full_name": user.full_name}

    def login(self, s: Session, email: str, password: str, device: str | None,
              product: str = "learn") -> dict:
        user = s.execute(
            select(User).where(User.email == email.lower(), User.product == product)
        ).scalar_one_or_none()
        # Uniform failure to avoid user enumeration.
        if not user:
            raise Unauthorized("Invalid credentials", code="invalid_credentials")

        if user.locked_until and _lock_active(user.locked_until):
            raise TooManyRequests("Account temporarily locked", code="account_locked")

        if user.status != "active":
            raise Forbidden("Account is not active", code="account_inactive")

        if not verify_password(password, user.password_hash):
            user.failed_attempts += 1
            if user.failed_attempts >= self.cfg.MAX_LOGIN_ATTEMPTS:
                user.locked_until = _utcnow() + timedelta(minutes=self.cfg.LOCKOUT_MINUTES)
                user.failed_attempts = 0
            raise Unauthorized("Invalid credentials", code="invalid_credentials")

        user.failed_attempts = 0
        user.locked_until = None
        return self._issue_tokens(s, user, device)

    def refresh(self, s: Session, raw_refresh: str, allowed_product: str | None = None) -> dict:
        token_hash = hash_token(raw_refresh)
        rt = s.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        ).scalar_one_or_none()
        if not rt:
            raise Unauthorized("Invalid refresh token", code="invalid_refresh")

        user = s.get(User, rt.user_id)
        # Reject cross-product use before reuse detection has any side effect on
        # the token family. This keeps accidental wrong-origin requests isolated.
        if allowed_product in ("learn", "hire") and (not user or user.product != allowed_product):
            raise Unauthorized("Refresh token belongs to another product", code="wrong_product")

        # Reuse detection: a revoked token presented again → revoke the family.
        # Persist the revocation before raising, otherwise the session context
        # manager rolls it back on the exception and the sibling token survives.
        if rt.revoked_at is not None:
            self._revoke_family(s, rt.family_id)
            s.commit()
            raise Unauthorized("Refresh token reuse detected", code="refresh_reuse")

        if not rt.is_active:
            raise Unauthorized("Refresh token expired", code="refresh_expired")

        if not user or user.status != "active":
            raise Unauthorized("User not active", code="account_inactive")

        rt.revoked_at = _utcnow()  # rotate: revoke old, mint new in same family
        return self._issue_tokens(s, user, rt.device, family_id=rt.family_id)

    def logout(self, s: Session, raw_refresh: str,
               allowed_product: str | None = None) -> None:
        rt = s.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
        ).scalar_one_or_none()
        if rt and allowed_product in ("learn", "hire"):
            user = s.get(User, rt.user_id)
            if not user or user.product != allowed_product:
                raise Unauthorized("Refresh token belongs to another product", code="wrong_product")
        if rt and rt.revoked_at is None:
            rt.revoked_at = _utcnow()

    def assign_role(self, s: Session, user_id: str, role_name: str,
                    college_id: str | None, branch_id: str | None = None,
                    cohort_id: str | None = None) -> None:
        user = s.get(User, user_id)
        if not user:
            raise Conflict("Unknown user", code="unknown_user")
        role = s.execute(select(Role).where(Role.name == role_name,
                                            Role.product == user.product)).scalar_one_or_none()
        if not role:
            raise Conflict("Unknown role", code="unknown_role")
        exists = s.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.college_id.is_(college_id) if college_id is None
                else UserRole.college_id == college_id,
            )
        ).scalar_one_or_none()
        if exists:
            # Keep the finer bindings current even if the (user,role,college) row
            # already exists — an admin may be narrowing the scope.
            exists.branch_id, exists.cohort_id = branch_id, cohort_id
            return
        s.add(UserRole(id=new_id(), user_id=user_id, role_id=role.id,
                       college_id=college_id, branch_id=branch_id, cohort_id=cohort_id))

    # ---------- OTP / password reset / email verification ----------
    def _issue_verification(self, s: Session, user: User, purpose: str,
                            ttl_min: int, numeric: bool) -> str:
        # Invalidate prior unconsumed tokens of the same purpose.
        for t in s.execute(
            select(VerificationToken).where(
                VerificationToken.user_id == user.id,
                VerificationToken.purpose == purpose,
                VerificationToken.consumed_at.is_(None))
        ).scalars().all():
            t.consumed_at = _utcnow()
        raw = f"{secrets.randbelow(900000) + 100000}" if numeric else random_token()
        s.add(VerificationToken(
            id=new_id(), user_id=user.id, purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=_utcnow() + timedelta(minutes=ttl_min)))
        s.flush()
        return raw

    def _consume_verification(self, s: Session, purpose: str, raw: str,
                              user_id: str | None = None,
                              allowed_product: str | None = None) -> User:
        q = select(VerificationToken).where(
            VerificationToken.purpose == purpose,
            VerificationToken.token_hash == hash_token(raw),
            VerificationToken.consumed_at.is_(None))
        if user_id:
            q = q.where(VerificationToken.user_id == user_id)
        vt = s.execute(q).scalar_one_or_none()
        if not vt:
            raise Unauthorized("Invalid or used token", code="invalid_token")
        # Check the product before consuming a single-use token. Otherwise a
        # token presented to the wrong product can be burned by an attacker or
        # by a user following a stale cross-product link.
        user = s.get(User, vt.user_id)
        if not user:
            raise Unauthorized("User not found", code="user_not_found")
        if allowed_product in ("learn", "hire") and user.product != allowed_product:
            raise Unauthorized("Token belongs to another product", code="wrong_product")
        exp = vt.expires_at.replace(tzinfo=timezone.utc) if vt.expires_at.tzinfo is None else vt.expires_at
        if exp < _utcnow():
            raise Unauthorized("Token expired", code="token_expired")
        vt.consumed_at = _utcnow()
        return user

    def request_otp(self, s: Session, email: str, product: str = "learn") -> str | None:
        """Issue a 6-digit login OTP. Returns the code (delivered via
        Notification in prod; returned in dev for testing). No user enumeration."""
        user = s.execute(
            select(User).where(User.email == email.lower(), User.product == product)
        ).scalar_one_or_none()
        if not user:
            return None
        return self._issue_verification(s, user, "otp", ttl_min=10, numeric=True)

    def verify_otp(self, s: Session, email: str, code: str, device: str | None,
                   product: str = "learn") -> dict:
        user = s.execute(
            select(User).where(User.email == email.lower(), User.product == product)
        ).scalar_one_or_none()
        if not user:
            raise Unauthorized("Invalid credentials", code="invalid_credentials")
        if user.status != "active":
            raise Forbidden("Account is not active", code="account_inactive")
        self._consume_verification(s, "otp", code, user_id=user.id)
        # A successfully redeemed code proves control of this email address.
        user.email_verified = True
        return self._issue_tokens(s, user, device)

    def request_password_reset(self, s: Session, email: str, product: str = "learn") -> str | None:
        user = s.execute(
            select(User).where(User.email == email.lower(), User.product == product)
        ).scalar_one_or_none()
        if not user:
            return None  # silent: no enumeration
        return self._issue_verification(s, user, "password_reset", ttl_min=30, numeric=False)

    def reset_password(self, s: Session, token: str, new_password: str,
                       allowed_product: str | None = None) -> None:
        user = self._consume_verification(s, "password_reset", token,
                                          allowed_product=allowed_product)
        user.password_hash = hash_password(new_password, rounds=self.cfg.BCRYPT_ROUNDS)
        user.failed_attempts = 0
        user.locked_until = None
        # Revoke all refresh families on password change (security best practice).
        for rt in s.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        ).scalars().all():
            rt.revoked_at = _utcnow()

    def request_email_verification(self, s: Session, user_id: str) -> str:
        user = s.get(User, user_id)
        if not user:
            raise Unauthorized("User not found", code="user_not_found")
        return self._issue_verification(s, user, "email_verify", ttl_min=60 * 24, numeric=False)

    def verify_email(self, s: Session, token: str,
                     allowed_product: str | None = None) -> dict:
        user = self._consume_verification(s, "email_verify", token,
                                          allowed_product=allowed_product)
        user.email_verified = True
        return self.user_out(s, user)

    def _revoke_family(self, s: Session, family_id: str) -> None:
        tokens = s.execute(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
        ).scalars().all()
        for t in tokens:
            t.revoked_at = _utcnow()

    def user_out(self, s: Session, user: User, *, with_permissions: bool = False) -> dict:
        out = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "email_verified": user.email_verified,
            "mfa_enabled": user.mfa_enabled,
            "tenant_id": user.tenant_id,
            "product": getattr(user, "product", "learn"),
            "roles": self._role_names(s, user),
        }
        if with_permissions:
            perms, scope = self._effective(s, user)
            out["permissions"] = perms
            out["scope_level"] = scope
            out["college_ids"] = self._college_ids(s, user)
        return out

    # ---------- user administration ----------
    def role_assignments(self, s: Session, user: User) -> list[dict]:
        """Each of a user's role grants with the hierarchy slice it's bound to —
        what the admin UI shows and edits."""
        rows = s.execute(
            select(UserRole, Role).join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user.id, Role.product == user.product)
        ).all()
        return [{
            "role": role.name, "role_id": role.id, "scope_level": role.scope_level,
            "college_id": ur.college_id, "branch_id": ur.branch_id,
            "cohort_id": ur.cohort_id,
        } for ur, role in rows]

    def admin_user_out(self, s: Session, user: User) -> dict:
        out = self.user_out(s, user)
        out["assignments"] = self.role_assignments(s, user)
        out["created_at"] = user.created_at.isoformat() if user.created_at else None
        return out

    def list_admin_users(self, s: Session, q: str | None, status: str | None,
                         product: str | None, limit: int) -> list[User]:
        stmt = select(User)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(func.lower(User.email).like(like)
                              | func.lower(User.full_name).like(like))
        if status:
            stmt = stmt.where(User.status == status)
        if product:
            stmt = stmt.where(User.product == product)
        stmt = stmt.order_by(User.created_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars().all())

    def set_user_status(self, s: Session, user_id: str, status: str,
                        actor_id: str | None = None) -> User:
        if status not in ("active", "disabled"):
            raise BadRequest("Status must be active or disabled", code="bad_status")
        user = s.get(User, user_id)
        if not user:
            raise NotFound("User not found", code="user_not_found")
        if actor_id and user_id == actor_id and status == "disabled":
            raise BadRequest("You cannot suspend your own account", code="self_suspend")
        user.status = status
        if status == "disabled":
            # Kill active sessions so a suspension takes effect immediately.
            for t in s.execute(
                select(RefreshToken).where(RefreshToken.user_id == user_id,
                                           RefreshToken.revoked_at.is_(None))
            ).scalars().all():
                t.revoked_at = _utcnow()
        return user

    # ---------- RBAC administration ----------
    def _role_out(self, s: Session, role: Role) -> dict:
        n_users = s.execute(
            select(func.count(UserRole.id)).where(UserRole.role_id == role.id)
        ).scalar() or 0
        return {
            "id": role.id,
            "name": role.name,
            "product": role.product,
            "description": role.description,
            "scope_level": role.scope_level,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "permissions": sorted(p.code for p in role.permissions),
            "user_count": int(n_users),
        }

    def list_roles(self, s: Session, product: str | None = None) -> list[dict]:
        stmt = select(Role)
        product = product or self._product()
        if product:
            stmt = stmt.where(Role.product == product)
        roles = s.execute(stmt.order_by(Role.is_system.desc(), Role.name)).scalars().all()
        return [self._role_out(s, r) for r in roles]

    def list_permissions(self, s: Session, product: str | None = None) -> list[dict]:
        product = product or self._product()
        rows = s.execute(select(Permission).order_by(Permission.domain, Permission.code)).scalars().all()
        return [{"code": p.code, "description": p.description, "domain": p.domain}
                for p in rows if not product or _permission_product(p.code) in (None, product)]

    def _resolve_perms(self, s: Session, codes: list[str],
                       product: str | None = None) -> list[Permission]:
        codes = [c for c in dict.fromkeys(codes or []) if c]
        if not codes:
            return []
        found = s.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
        missing = set(codes) - {p.code for p in found}
        if missing:
            raise BadRequest(f"Unknown permission(s): {', '.join(sorted(missing))}",
                             code="unknown_permission")
        if product in ("learn", "hire"):
            wrong_product = {p.code for p in found
                             if _permission_product(p.code) not in (None, product)}
            if wrong_product:
                raise BadRequest(
                    f"Permission(s) belong to another product: {', '.join(sorted(wrong_product))}",
                    code="wrong_product_permission")
        return list(found)

    _VALID_SCOPES = ("platform", "college", "branch", "section", "self")

    def create_role(self, s: Session, name: str, description: str | None,
                    scope_level: str, permission_codes: list[str],
                    product: str | None = None) -> dict:
        name = (name or "").strip().lower().replace(" ", "_")
        product = product or self._product() or "learn"
        if product not in ("learn", "hire"):
            raise BadRequest("Invalid product", code="invalid_product")
        if not name:
            raise BadRequest("Role name is required", code="name_required")
        if scope_level not in self._VALID_SCOPES:
            raise BadRequest("Invalid scope level", code="invalid_scope")
        if s.execute(select(Role).where(Role.name == name,
                                        Role.product == product)).scalar_one_or_none():
            raise Conflict("A role with that name already exists", code="role_exists")
        role = Role(id=new_id(), name=name, product=product, description=description,
                    scope_level=scope_level, is_system=False, is_active=True)
        role.permissions = self._resolve_perms(s, permission_codes, product=product)
        s.add(role)
        s.flush()
        return self._role_out(s, role)

    def clone_role(self, s: Session, source_id: str, new_name: str,
                   description: str | None, product: str | None = None) -> dict:
        src = s.get(Role, source_id)
        product = product or self._product()
        if not src or (product and src.product != product):
            raise NotFound("Source role not found", code="role_not_found")
        return self.create_role(
            s, new_name, description or f"Copy of {src.name}",
            src.scope_level, [p.code for p in src.permissions], product=src.product)

    def update_role(self, s: Session, role_id: str, *, description=None,
                    scope_level=None, is_active=None, permission_codes=None,
                    product: str | None = None) -> dict:
        role = s.get(Role, role_id)
        product = product or self._product()
        if not role or (product and role.product != product):
            raise NotFound("Role not found", code="role_not_found")
        if description is not None:
            role.description = description
        if scope_level is not None:
            if scope_level not in self._VALID_SCOPES:
                raise BadRequest("Invalid scope level", code="invalid_scope")
            # A built-in role's scope ceiling is part of the platform contract.
            if role.is_system and scope_level != role.scope_level:
                raise BadRequest("Cannot change a system role's scope", code="system_role")
            role.scope_level = scope_level
        if is_active is not None:
            if role.is_system and not is_active:
                raise BadRequest("System roles cannot be deactivated", code="system_role")
            role.is_active = bool(is_active)
        if permission_codes is not None:
            # Permissions are always re-assignable — even for system roles.
            role.permissions = self._resolve_perms(s, permission_codes, product=role.product)
        s.flush()
        return self._role_out(s, role)

    def delete_role(self, s: Session, role_id: str, product: str | None = None) -> None:
        role = s.get(Role, role_id)
        product = product or self._product()
        if not role or (product and role.product != product):
            raise NotFound("Role not found", code="role_not_found")
        if role.is_system:
            raise BadRequest("Built-in roles cannot be deleted", code="system_role")
        n_users = s.execute(
            select(func.count(UserRole.id)).where(UserRole.role_id == role.id)
        ).scalar() or 0
        if n_users:
            raise Conflict(f"{n_users} user(s) still hold this role; reassign them first",
                           code="role_in_use")
        s.delete(role)

    def remove_role(self, s: Session, user_id: str, role_name: str,
                    college_id: str | None) -> None:
        user = s.get(User, user_id)
        role = s.execute(select(Role).where(Role.name == role_name,
                                            Role.product == (user.product if user else ""))).scalar_one_or_none()
        if not role:
            return
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        stmt = stmt.where(UserRole.college_id.is_(None) if college_id is None
                          else UserRole.college_id == college_id)
        for ur in s.execute(stmt).scalars().all():
            s.delete(ur)


def _lock_active(locked_until: datetime) -> bool:
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > _utcnow()

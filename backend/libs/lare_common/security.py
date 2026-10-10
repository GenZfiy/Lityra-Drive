"""Password hashing and JWT issue/verify helpers.

- Passwords: bcrypt (cost from config).
- Tokens: PyJWT; HS256 in dev, RS256 in production (keys from config).
- Refresh tokens: opaque random strings; only their SHA-256 hash is stored.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt


# ---------- passwords ----------

def hash_password(password: str, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- opaque tokens (refresh, otp, verify links) ----------

def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- JWT ----------

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    *,
    subject: str,
    roles: list[str],
    tenant_id: str,
    college_ids: list[str],
    alg: str,
    signing_key: str,
    issuer: str,
    audience: str,
    ttl_minutes: int,
    permissions: list[str] | None = None,
    scope_level: str = "self",
    branch_ids: list[str] | None = None,
    cohort_ids: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    iat = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "roles": roles,
        # Effective permission codes (union across the user's roles), so any
        # service can enforce RBAC from the token alone — no DB round-trip.
        "permissions": permissions or [],
        # Widest data-visibility tier the user's roles grant, plus the concrete
        # hierarchy bindings that tier is exercised over (data-scope isolation).
        "scope_level": scope_level,
        "tenant_id": tenant_id,
        "college_ids": college_ids,
        "branch_ids": branch_ids or [],
        "cohort_ids": cohort_ids or [],
        "iss": issuer,
        "aud": audience,
        "iat": iat,
        "exp": iat + timedelta(minutes=ttl_minutes),
        "jti": new_id(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, signing_key, algorithm=alg)


def decode_token(
    token: str, *, alg: str, verify_key: str, issuer: str, audience: str
) -> dict[str, Any]:
    return jwt.decode(
        token,
        verify_key,
        algorithms=[alg],
        issuer=issuer,
        audience=audience,
    )


# ---------- JWKS (prod RS256 key distribution) ----------

def public_jwks(public_key_pem: str | None, kid: str = "lare-1") -> dict[str, Any]:
    """Build a JWKS document from an RSA public key PEM.

    Requires `cryptography` (pulled in by PyJWT[crypto]) — used only in the
    RS256 production path. Returns an empty key set if no key is configured or
    the crypto backend is unavailable, so the endpoint never 500s in dev."""
    if not public_key_pem:
        return {"keys": []}
    try:
        import json as _json

        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from jwt.algorithms import RSAAlgorithm

        key = load_pem_public_key(public_key_pem.encode("utf-8"))
        jwk = _json.loads(RSAAlgorithm.to_jwk(key))
        jwk.update({"use": "sig", "alg": "RS256", "kid": kid})
        return {"keys": [jwk]}
    except Exception:  # noqa: BLE001
        return {"keys": []}

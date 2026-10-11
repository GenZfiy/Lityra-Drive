"""Environment-driven configuration base (12-factor).

Each service subclasses BaseConfig and overrides SERVICE_NAME / defaults.
Secrets always come from the environment, never from code.
"""
from __future__ import annotations

import os


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _read_key(direct_env: str, file_env: str) -> str | None:
    """RS256 key: from the PEM directly (``direct_env``) or a file path
    (``file_env``). The file form keeps multi-line PEMs out of .env."""
    val = os.getenv(direct_env)
    if val:
        return val
    path = os.getenv(file_env)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    return None


class BaseConfig:
    # Identity of the running service
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "lare-service")
    ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = _bool("DEBUG", ENV != "production")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///service.sqlite3")
    DB_SCHEMA: str | None = os.getenv("DB_SCHEMA") or None  # ignored on sqlite
    SQL_ECHO: bool = _bool("SQL_ECHO", False)

    # JWT
    # Dev default = HS256 for zero-setup. Production sets JWT_ALG=RS256 and
    # provides JWT_PRIVATE_KEY / JWT_PUBLIC_KEY (PEM) so the Gateway can verify
    # offline via JWKS.
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-insecure-change-me")

    # RS256 keys: PEM directly (JWT_*_KEY) or a file path (JWT_*_KEY_FILE).
    JWT_PRIVATE_KEY: str | None = _read_key("JWT_PRIVATE_KEY", "JWT_PRIVATE_KEY_FILE")
    JWT_PUBLIC_KEY: str | None = _read_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_FILE")
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "lare-auth")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "lare-platform")
    # 4h access token so a full exam/drive session never expires mid-use (a
    # 15-min token forced a refresh every few minutes — one flaky refresh over a
    # tunnel would bounce the student to login mid-exam). Refresh token = 7 days.
    ACCESS_TOKEN_TTL_MIN: int = _int("ACCESS_TOKEN_TTL_MIN", 240)
    REFRESH_TOKEN_TTL_DAYS: int = _int("REFRESH_TOKEN_TTL_DAYS", 7)

    # Passwords / lockout
    BCRYPT_ROUNDS: int = _int("BCRYPT_ROUNDS", 12)
    MAX_LOGIN_ATTEMPTS: int = _int("MAX_LOGIN_ATTEMPTS", 5)
    LOCKOUT_MINUTES: int = _int("LOCKOUT_MINUTES", 15)

    # CORS
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
    ]

    # Multi-tenant default
    DEFAULT_TENANT_ID: str = os.getenv("DEFAULT_TENANT_ID", "lare")

    # Redis (cache / rate-limit / event bus). Empty = degrade to in-memory / HTTP.
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Event bus backend: "auto" (redis if reachable else http), "redis", "http",
    # or "memory" (in-process, for tests). HTTP fan-out uses the same trusted
    # east-west calls the Gateway already strips on public ingress.
    EVENT_BUS_BACKEND: str = os.getenv("EVENT_BUS_BACKEND", "auto")
    EVENT_STREAM: str = os.getenv("EVENT_STREAM", "lare:events")

    # East-west (service-to-service) auth. Internal calls carry a short-lived
    # HS256 token signed with this shared secret so a service can trust a caller
    # even though the Gateway is not in the internal path.
    INTERNAL_JWT_SECRET: str = os.getenv("INTERNAL_JWT_SECRET", "dev-internal-secret-change-me")
    INTERNAL_TOKEN_TTL_SEC: int = _int("INTERNAL_TOKEN_TTL_SEC", 60)

    @property
    def signing_key(self) -> str:
        return self.JWT_PRIVATE_KEY if self.JWT_ALG.startswith("RS") else self.JWT_SECRET

    @property
    def verify_key(self) -> str:
        return self.JWT_PUBLIC_KEY if self.JWT_ALG.startswith("RS") else self.JWT_SECRET

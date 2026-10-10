import os

from lare_common.config import BaseConfig


class AuthConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-auth")
    AUTH_ALLOWED_PRODUCT = os.getenv("AUTH_ALLOWED_PRODUCT", "combined").lower()
    # 'auth' is a Supabase-reserved schema — use lare_auth to avoid the collision.
    DB_SCHEMA = os.getenv("DB_SCHEMA", "lare_auth") or None
    JWT_ISSUER = os.getenv("JWT_ISSUER", "lare-auth")
    # Default dev DB is local SQLite; override with Supabase Postgres in prod.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///auth.sqlite3")

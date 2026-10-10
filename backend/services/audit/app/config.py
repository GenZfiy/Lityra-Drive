import os

from lare_common.config import BaseConfig


class AuditConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-audit")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///audit.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "shared_audit") or None

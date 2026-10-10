import os

from lare_common.config import BaseConfig


class OrgConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "platform-org")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///organization.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "platform_org") or None

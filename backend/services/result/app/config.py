import os

from lare_common.config import BaseConfig


class ResultConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-result")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///result.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_result") or None

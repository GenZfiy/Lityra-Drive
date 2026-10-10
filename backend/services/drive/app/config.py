import os

from lare_common.config import BaseConfig


class DriveConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-core")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///drive.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_core") or None

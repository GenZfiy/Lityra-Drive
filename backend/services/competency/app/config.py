import os

from lare_common.config import BaseConfig


class CompetencyConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-competency")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///competency.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_competency") or None

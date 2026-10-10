import os

from lare_common.config import BaseConfig


class CandidateConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-candidate")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///candidate.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_candidate") or None

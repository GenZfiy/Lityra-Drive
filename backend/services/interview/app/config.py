import os

from lare_common.config import BaseConfig


class InterviewConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-interview")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///interview.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_interview") or None

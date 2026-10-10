import os

from lare_common.config import BaseConfig


class ExamConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-exam-engine")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exam.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_exam") or None

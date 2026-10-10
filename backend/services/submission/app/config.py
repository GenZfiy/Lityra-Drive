import os

from lare_common.config import BaseConfig


class SubmissionConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-submission")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///submission.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_submission") or None

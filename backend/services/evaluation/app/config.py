import os

from lare_common.config import BaseConfig


class EvaluationConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-evaluation")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///evaluation.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_evaluation") or None

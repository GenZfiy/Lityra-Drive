import os

from lare_common.config import BaseConfig


class QuestionBankConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-questionbank")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///questionbank.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_questionbank") or None

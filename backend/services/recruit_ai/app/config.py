import os

from lare_common.config import BaseConfig


class RecruitAiConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-recruit-ai")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recruit_ai.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_recruit_ai") or None
    READY_CONFIDENCE = float(os.getenv("RECRUIT_AI_READY_CONFIDENCE", "75"))
    COVERAGE_FLOOR = float(os.getenv("RECRUIT_AI_COVERAGE_FLOOR", "60"))

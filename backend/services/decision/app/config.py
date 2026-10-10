import os

from lare_common.config import BaseConfig


class DecisionConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-decision")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///decision.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_decision") or None
    # Signal spread (0..100) above which a competency's evidence is "divergent".
    AGREEMENT_SPREAD = float(os.getenv("DECISION_AGREEMENT_SPREAD", "25"))

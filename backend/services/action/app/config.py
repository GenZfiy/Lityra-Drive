import os

from lare_common.config import BaseConfig


class ActionConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-action")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///action.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_action") or None
    # Coverage below this (percent of the evaluation model) raises a "thin evidence" action.
    COVERAGE_FLOOR = float(os.getenv("ACTION_COVERAGE_FLOOR", "60"))
    # Decision confidence at/above this flags a candidate as ready to decide.
    READY_CONFIDENCE = float(os.getenv("ACTION_READY_CONFIDENCE", "75"))

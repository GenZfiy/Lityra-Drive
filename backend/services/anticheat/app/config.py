import os

from lare_common.config import BaseConfig


class AntiCheatConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-anticheat")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///anticheat.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_anticheat") or None
    # Default violation weight threshold that triggers auto-submit.
    # Auto-submit when the weighted violation score crosses this. Aligned to ~5
    # flags: the dominant flag (tab_switch=20) crosses 100 in 5 events, matching
    # the client's 5-flag guard. Raise via env to be more lenient.
    AUTOSUBMIT_THRESHOLD = int(os.getenv("AUTOSUBMIT_THRESHOLD", "100"))
    # Exam Engine endpoint the auto-submit event is delivered to (east-west).
    EXAM_ENGINE_URL = os.getenv("EXAM_URL", "http://127.0.0.1:8013")

import os

from lare_common.config import BaseConfig


def _bool(name, default):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


class CodingConfig(BaseConfig):
    # Shared PLATFORM code-execution engine — used independently by LMS practice
    # and Hire coding rounds. It belongs to neither product. (DB_SCHEMA keeps its
    # original name to avoid a data migration; only the service label changed.)
    SERVICE_NAME = os.getenv("SERVICE_NAME", "platform-coding")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///coding.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_coding") or None
    # Executor mode: 'subprocess' (dev), 'sandbox' (prod: nsjail/bubblewrap),
    # or 'disabled'. 'sandbox' is fatal in production if no sandbox binary exists.
    EXEC_ENABLED = _bool("EXEC_ENABLED", True)
    EXEC_MODE = os.getenv("EXEC_MODE", "sandbox" if os.getenv("APP_ENV") == "production" else "subprocess")
    EXEC_TIMEOUT_SEC = int(os.getenv("EXEC_TIMEOUT_SEC", "5"))

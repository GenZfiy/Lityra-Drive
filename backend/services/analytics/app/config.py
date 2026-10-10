import os

from lare_common.config import BaseConfig


class AnalyticsConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-analytics")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///analytics.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "shared_analytics") or None

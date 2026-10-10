import os

from lare_common.config import BaseConfig


class NotificationConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-notify")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///notification.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "shared_notify") or None
    # Email provider: 'null' (dev, logs only), 'smtp', or 'brevo'.
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "null")
    # SMS/WhatsApp provider: 'null' (dev) or 'twilio'.
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "null")

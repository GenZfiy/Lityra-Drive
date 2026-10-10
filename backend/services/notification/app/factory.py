from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database
from lare_common.events import setup_event_subscriber

from .config import NotificationConfig
from .events import register_handlers
from .routes import bp
from .service import NotificationService, ensure_default_templates


def build_app():
    cfg = NotificationConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    svc = NotificationService(email_provider=cfg.EMAIL_PROVIDER, sms_provider=cfg.SMS_PROVIDER)
    ensure_default_templates(db)  # password_reset / otp / email_verify must exist
    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = svc
    setup_event_subscriber(app, cfg, db, svc, register_handlers)
    return app

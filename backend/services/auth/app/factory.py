"""Compose the Auth Flask app: config, DB, service, blueprints."""
from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database
from lare_common.events import setup_event_publisher

from .config import AuthConfig
from .routes import bp
from .service import AuthService


def build_app() -> "flask.Flask":  # noqa: F821
    cfg = AuthConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    app = create_app(cfg, blueprints=[(bp, "/auth/v1")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["auth_service"] = AuthService(cfg)
    # Publisher so administrative actions (role changes, suspensions, permission
    # edits) are emitted to the bus and captured by the tamper-evident audit log.
    app.extensions["bus"] = setup_event_publisher(app, cfg)
    return app

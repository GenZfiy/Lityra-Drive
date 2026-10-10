from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database

from .client import build_client
from .config import AIConfig
from .routes import bp
from .service import AIService


def build_app():
    cfg = AIConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    client = build_client(cfg)
    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = AIService(client)
    app.extensions["ai_mode"] = client.mode
    return app

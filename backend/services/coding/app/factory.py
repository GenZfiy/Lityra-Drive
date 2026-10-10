from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database

from .config import CodingConfig
from .executor import build_executor
from .routes import bp
from .service import CodingService


def build_app():
    cfg = CodingConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)
    executor = build_executor(cfg.EXEC_MODE if cfg.EXEC_ENABLED else "disabled")

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = CodingService(executor, timeout_sec=cfg.EXEC_TIMEOUT_SEC)
    return app

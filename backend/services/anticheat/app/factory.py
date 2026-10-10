from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database

from .config import AntiCheatConfig
from .notify import make_exam_autosubmit_trigger
from .routes import bp
from .service import AntiCheatService


def build_app():
    cfg = AntiCheatConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = AntiCheatService(
        threshold=cfg.AUTOSUBMIT_THRESHOLD,
        on_auto_submit=make_exam_autosubmit_trigger(cfg.EXAM_ENGINE_URL),
    )
    return app

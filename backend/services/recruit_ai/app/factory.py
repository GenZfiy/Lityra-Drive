from __future__ import annotations

from lare_common.ai import build_client
from lare_common.app_factory import create_app
from lare_common.db import Database

from .config import RecruitAiConfig
from .routes import bp
from .service import RecruitAiService


def build_app():
    cfg = RecruitAiConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    # build_client() reads AI_* env; returns a StubClient when no key is set,
    # so narration degrades cleanly to deterministic 'derived' insights.
    svc = RecruitAiService(ready_confidence=cfg.READY_CONFIDENCE, coverage_floor=cfg.COVERAGE_FLOOR, ai=build_client())
    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = svc
    return app

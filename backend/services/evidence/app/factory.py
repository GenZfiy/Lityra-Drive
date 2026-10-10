from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database
from lare_common.events import setup_event_subscriber

from .config import EvidenceConfig
from .events import register_handlers
from .routes import bp
from .service import EvidenceService


def build_app():
    cfg = EvidenceConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    svc = EvidenceService(conflict_delta=cfg.CONFLICT_DELTA)
    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = svc
    # Subscribe to evaluation.completed so evidence is recorded automatically as
    # assessments are graded. The returned bus also publishes evidence.* events.
    setup_event_subscriber(app, cfg, db, svc, register_handlers)
    return app

from __future__ import annotations

from lare_common.app_factory import create_app
from lare_common.db import Database

from .config import FilesConfig
from .routes import bp
from .service import FilesService
from .storage import LocalStorage


def build_app():
    cfg = FilesConfig()
    db = Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)
    # 'local' dev backend; production swaps in SupabaseStorage.
    storage = LocalStorage(cfg.STORAGE_DIR)

    def ready() -> bool:
        try:
            with db.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    app = create_app(cfg, blueprints=[(bp, "")], ready_check=ready)
    app.extensions["db"] = db
    app.extensions["svc"] = FilesService(
        storage, secret=cfg.JWT_SECRET,
        upload_ttl_min=cfg.UPLOAD_TOKEN_TTL_MIN,
        download_ttl_min=cfg.DOWNLOAD_TOKEN_TTL_MIN)
    return app

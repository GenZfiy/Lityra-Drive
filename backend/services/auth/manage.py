"""CLI: init-db | seed | run  (dev conveniences; prod uses Alembic + Gunicorn)."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import AuthConfig  # noqa: E402
from app.factory import build_app  # noqa: E402
from app.seed import seed  # noqa: E402
from lare_common.db import Database  # noqa: E402


def _db(cfg: AuthConfig) -> Database:
    return Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA)


def cmd_init_db():
    cfg = AuthConfig()
    import app.models  # noqa: F401  (register models on Base.metadata)
    db = _db(cfg)
    db.create_all()
    # Keep built-in roles and permissions synchronized during normal startup.
    # This never creates an admin account; that remains an explicit `seed` action.
    seed(db, cfg, create_admin=False)
    print("[init-db] tables created successfully")


def cmd_seed():
    cfg = AuthConfig()
    import app.models  # noqa: F401
    db = _db(cfg)
    db.create_all()
    seed(db, cfg)


def cmd_run():
    app = build_app()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8001")), debug=True)


def cmd_serve():
    from lare_common.serve import serve
    serve(build_app(), host="127.0.0.1", port=int(os.getenv("PORT", "8001")))


COMMANDS = {"init-db": cmd_init_db, "seed": cmd_seed, "run": cmd_run, "serve": cmd_serve}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python manage.py [init-db|seed|run]")
        raise SystemExit(1)
    COMMANDS[sys.argv[1]]()

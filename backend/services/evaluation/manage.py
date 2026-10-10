"""CLI: init-db | serve | run."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.config import EvaluationConfig  # noqa: E402
from app.factory import build_app  # noqa: E402
from lare_common.db import Database  # noqa: E402


def cmd_init_db():
    cfg = EvaluationConfig()
    import app.models  # noqa: F401
    Database(cfg.DATABASE_URL, echo=cfg.SQL_ECHO, schema=cfg.DB_SCHEMA).create_all()
    print("[init-db] tables created successfully")


def cmd_serve():
    from lare_common.serve import serve
    serve(build_app(), host="127.0.0.1", port=int(os.getenv("PORT", "8017")))


def cmd_run():
    build_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "8017")), debug=True)


COMMANDS = {"init-db": cmd_init_db, "serve": cmd_serve, "run": cmd_run}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python manage.py [init-db|serve|run]")
        raise SystemExit(1)
    COMMANDS[sys.argv[1]]()
